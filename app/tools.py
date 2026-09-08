"""The agent's four tools: definitions (JSON schema) + executor.

Design note: the tools return plain strings that get handed back to Claude as
tool_result content. `lookup_price` is deliberately strict — it never returns a
fabricated number, and signals `quote_required` / `not_found` so the agent can
pivot to a consultation instead of guessing.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import catalog, db
from .config import get_settings

_FAQ_PATH = Path(__file__).resolve().parent.parent / "data" / "faq.md"


# --------------------------------------------------------------------------- #
# Tool schemas (sent to the Claude API)
# --------------------------------------------------------------------------- #
def tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "search_faq",
            "description": (
                "Look up store information and policies (hours, location, custom "
                "process, certification, sizing, care, warranty, shipping, "
                "returns, payment, booking). Use for any non-price question about "
                "the studio."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What the customer is asking about.",
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "lookup_price",
            "description": (
                "Get the price and details of a specific catalog piece. This is "
                "the ONLY approved source of prices — never state a price this "
                "tool did not return. Provide either the item id/sku, the piece "
                "name, or a referenced Instagram media id. Returns the fixed "
                "price, or a signal that the item needs a quote or was not found."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "item_reference": {
                        "type": "string",
                        "description": "Item id, sku, or the piece name.",
                    },
                    "media_id": {
                        "type": "string",
                        "description": "Instagram media id the customer referenced, if any.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
        {
            "name": "book_consultation",
            "description": (
                "Give the customer a link to book a consultation with the "
                "owner/specialist, and record the lead. Collect the customer's "
                "name, a contact (phone or email), their interest, and the "
                "consultation type before calling."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "contact": {
                        "type": "string",
                        "description": "Phone or email so the studio can follow up.",
                    },
                    "interest": {
                        "type": "string",
                        "description": "Piece or service the customer is interested in.",
                    },
                    "consult_type": {
                        "type": "string",
                        "enum": ["in-store", "video", "phone"],
                    },
                },
                "required": ["name", "contact", "interest", "consult_type"],
                "additionalProperties": False,
            },
        },
        {
            "name": "escalate_to_human",
            "description": (
                "Flag this conversation for a human specialist (negotiation, "
                "complex custom work, complaints, or explicit request for a "
                "person). Tell the customer a specialist will follow up."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                },
                "required": ["reason"],
                "additionalProperties": False,
            },
        },
    ]


# --------------------------------------------------------------------------- #
# Tool executors
# --------------------------------------------------------------------------- #
def _search_faq(query: str) -> str:
    # POC: the whole FAQ is small enough to hand back. Swap for real retrieval
    # (RAG) when the knowledge base grows. `query` is logged implicitly via the
    # message trail; here we just return the source of truth.
    return _FAQ_PATH.read_text()


def _lookup_price(item_reference: str = "", media_id: str = "") -> str:
    settings = get_settings()
    item = None
    if media_id:
        item = catalog.find_by_media_id(media_id)
    if item is None and item_reference:
        item = catalog.find_by_reference(item_reference)

    if item is None:
        return (
            "not_found: No matching catalog item. Do NOT guess a price. Ask the "
            "customer which piece they mean (by name or by sharing the post), or "
            "offer a consultation.\n\nAvailable pieces:\n"
            + catalog.catalog_summary()
        )

    if item.get("price_type") == "quote_required" or item.get("price") is None:
        return (
            f"quote_required: '{item['title']}' is priced after a consultation. "
            "Do NOT state a number. Offer to book a consultation for a precise quote."
        )

    stock = "in stock" if item.get("in_stock") else "made to order (currently not in stock)"
    return (
        f"fixed_price: {item['title']} — {settings.business_currency} "
        f"{item['price']:.2f}. Details: {item['metal']}, {item['stone']}, "
        f"size {item['size']}. Availability: {stock}. "
        "You may state this exact price."
    )


def _book_consultation(
    ig_user_id: str, name: str, contact: str, interest: str, consult_type: str
) -> str:
    settings = get_settings()
    db.save_booking(ig_user_id, name, contact, interest, consult_type)
    db.set_conversation_status(ig_user_id, "booked")
    return (
        f"booking_recorded: Share this link so {name} can pick a time: "
        f"{settings.calendly_scheduling_url}\n"
        f"(Recorded: {consult_type} consultation about '{interest}', contact {contact}.)"
    )


def _escalate_to_human(ig_user_id: str, reason: str) -> str:
    db.save_escalation(ig_user_id, reason)
    db.set_conversation_status(ig_user_id, "escalated")
    # In production, also notify staff (Slack/email). See docs/02-architecture.md §E Phase 5.
    return (
        "escalated: A human specialist has been notified. Let the customer know "
        "someone from the team will follow up shortly."
    )


def execute_tool(name: str, tool_input: dict[str, Any], ig_user_id: str) -> tuple[str, bool]:
    """Dispatch a tool call. Returns (result_text, is_error)."""
    try:
        if name == "search_faq":
            return _search_faq(tool_input.get("query", "")), False
        if name == "lookup_price":
            return (
                _lookup_price(
                    item_reference=tool_input.get("item_reference", ""),
                    media_id=tool_input.get("media_id", ""),
                ),
                False,
            )
        if name == "book_consultation":
            return (
                _book_consultation(
                    ig_user_id,
                    name=tool_input["name"],
                    contact=tool_input["contact"],
                    interest=tool_input["interest"],
                    consult_type=tool_input["consult_type"],
                ),
                False,
            )
        if name == "escalate_to_human":
            return _escalate_to_human(ig_user_id, tool_input.get("reason", "")), False
        return f"Unknown tool: {name}", True
    except Exception as exc:  # noqa: BLE001 — surface tool errors back to the model
        return f"Tool '{name}' failed: {exc}", True
