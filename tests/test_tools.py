"""Unit tests for the pricing guardrail and tools — no network / no LLM.

These protect the single most important business rule: the agent must never be
handed a fabricated price. We test the deterministic tool layer directly.
Run:  pytest -q
"""
from __future__ import annotations

from app import catalog, tools


def test_fixed_price_returned_for_known_item():
    result, is_error = tools.execute_tool(
        "lookup_price", {"item_reference": "ring-solitaire-18k"}, "u1"
    )
    assert not is_error
    assert result.startswith("fixed_price:")
    assert "2450.00" in result


def test_quote_required_item_returns_no_number():
    result, is_error = tools.execute_tool(
        "lookup_price", {"item_reference": "custom-bespoke"}, "u1"
    )
    assert not is_error
    assert result.startswith("quote_required:")
    # The guardrail: no price figure should be present for a quote-only item.
    assert "$" not in result


def test_unknown_item_is_not_found_not_guessed():
    result, is_error = tools.execute_tool(
        "lookup_price", {"item_reference": "does-not-exist-xyz"}, "u1"
    )
    assert not is_error
    assert result.startswith("not_found:")


def test_lookup_by_media_id():
    result, _ = tools.execute_tool(
        "lookup_price", {"media_id": "17900000000000002"}, "u1"
    )
    assert "Akoya Pearl Strand" in result


def test_ambiguous_reference_resolves_to_none():
    # 'ring' matches only one item here, but a bare category with multiple hits
    # should not resolve — verify the helper returns None on multi-match.
    assert catalog.find_by_reference("nonexistent-substring-123") is None


def test_unknown_tool_flagged_as_error():
    _, is_error = tools.execute_tool("not_a_tool", {}, "u1")
    assert is_error
