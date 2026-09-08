"""Loads the fixed-price jewelry catalog and provides lookup helpers.

The catalog is the single source of truth for prices. `lookup_price` (in
tools.py) is the ONLY sanctioned way for the agent to obtain a price — the agent
is instructed never to invent one.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"


@lru_cache
def _load() -> dict[str, Any]:
    with _CATALOG_PATH.open() as f:
        return json.load(f)


def all_items() -> list[dict[str, Any]]:
    return _load()["items"]


def find_by_media_id(media_id: str) -> dict[str, Any] | None:
    for item in all_items():
        if media_id in item.get("instagram_media_ids", []):
            return item
    return None


def find_by_reference(reference: str) -> dict[str, Any] | None:
    """Best-effort resolve an item from a free-text reference or id/sku.

    Intentionally simple for the POC: exact id/sku match, then a case-insensitive
    substring match against the title. Ambiguity is handled by the agent asking a
    clarifying question, not by guessing here.
    """
    ref = reference.strip().lower()
    if not ref:
        return None
    for item in all_items():
        if ref == item["id"].lower() or ref == item["sku"].lower():
            return item
    matches = [it for it in all_items() if ref in it["title"].lower()]
    return matches[0] if len(matches) == 1 else None


def catalog_summary() -> str:
    """A compact, price-free list of pieces to help the agent disambiguate."""
    lines = []
    for it in all_items():
        lines.append(f"- {it['title']} ({it['category']}, {it['metal']}) [id: {it['id']}]")
    return "\n".join(lines)
