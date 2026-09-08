"""Instagram webhook: GET verification + POST receiver with signature check.

Meta pushes incoming DMs here. We verify the X-Hub-Signature-256 HMAC so nobody
can spoof messages, ack fast with 200, then process. For the POC we process
inline; production should enqueue (see docs/02-architecture.md §F.1 / §G).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, Request, Response

from . import agent, db, instagram
from .config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/webhook")
async def verify_webhook(request: Request) -> Response:
    """Meta calls this once to verify the endpoint. Echo hub.challenge."""
    settings = get_settings()
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == settings.webhook_verify_token
    ):
        challenge = params.get("hub.challenge", "")
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


def _valid_signature(body: bytes, header: str | None) -> bool:
    settings = get_settings()
    if not settings.meta_app_secret:
        logger.warning("META_APP_SECRET not set — skipping signature check (dev only).")
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.meta_app_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header.split("=", 1)[1])


@router.post("/webhook")
async def receive_webhook(request: Request) -> Response:
    body = await request.body()
    if not _valid_signature(body, request.headers.get("X-Hub-Signature-256")):
        logger.warning("Rejected webhook with invalid signature.")
        return Response(status_code=403)

    payload = await request.json()
    # Ack fast; then handle. (POC processes inline — small volume.)
    try:
        _handle_payload(payload)
    except Exception:  # noqa: BLE001 — never let a handler error break the 200 ack
        logger.exception("Error handling webhook payload")
    return Response(status_code=200)


def _extract_messages(payload: dict[str, Any]) -> list[tuple[str, str, str | None]]:
    """Pull (sender_id, text, referenced_media_id) tuples from the webhook body.

    Instagram messaging webhooks arrive as entry[].messaging[] events. We ignore
    echoes (messages we sent) and non-text events for the POC.
    """
    out: list[tuple[str, str, str | None]] = []
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            message = event.get("message")
            if not message or message.get("is_echo"):
                continue
            sender_id = event.get("sender", {}).get("id")
            text = message.get("text")
            if not sender_id or not text:
                continue
            # A story reply / post share carries a reference we can map to a piece.
            referenced_media_id = None
            for att in message.get("attachments", []) or []:
                payload_obj = att.get("payload", {})
                referenced_media_id = payload_obj.get("id") or referenced_media_id
            reply_to = message.get("reply_to", {})
            if reply_to.get("story"):
                referenced_media_id = reply_to["story"].get("id", referenced_media_id)
            out.append((sender_id, text, referenced_media_id))
    return out


def _handle_payload(payload: dict[str, Any]) -> None:
    for sender_id, text, media_id in _extract_messages(payload):
        db.touch_conversation(sender_id)
        db.log_message(sender_id, "in", text, referenced_media_id=media_id)
        reply = agent.generate_reply(sender_id, text, referenced_media_id=media_id)
        instagram.send_text_message(sender_id, reply)
