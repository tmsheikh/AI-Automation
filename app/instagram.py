"""Instagram Graph API helpers: send replies and (dev) token exchange.

Uses httpx2 (the HTTP library the anthropic 1.x SDK is built on) to avoid a
second HTTP dependency. See docs/01-instagram-business-account-setup.md.
"""
from __future__ import annotations

import logging

import httpx2 as httpx

from .config import get_settings

logger = logging.getLogger(__name__)


def send_text_message(recipient_id: str, text: str) -> bool:
    """Send a text DM via the Instagram Send API.

    Returns True on success. In production, add retries with backoff and respect
    rate limits (see docs/02-architecture.md §G).
    """
    settings = get_settings()
    if not settings.instagram_access_token or not settings.instagram_account_id:
        logger.warning("Instagram credentials not set — skipping send (dev mode). Reply was: %s", text)
        return False

    url = f"{settings.graph_base_url}/{settings.instagram_account_id}/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
    }
    params = {"access_token": settings.instagram_access_token}
    try:
        resp = httpx.post(url, params=params, json=payload, timeout=15.0)
        if resp.status_code >= 400:
            logger.error("Send API error %s: %s", resp.status_code, resp.text)
            return False
        return True
    except httpx.HTTPError as exc:  # network-level failure
        logger.error("Send API request failed: %s", exc)
        return False


def exchange_for_long_lived_token(short_lived_token: str, app_secret: str) -> str | None:
    """Dev helper: exchange a short-lived token for a long-lived one.

    Run once during setup; store the result in INSTAGRAM_ACCESS_TOKEN. Long-lived
    tokens still expire (~60 days) — schedule a refresh job for production.
    """
    settings = get_settings()
    url = f"{settings.graph_base_url}/access_token"
    params = {
        "grant_type": "ig_exchange_token",
        "client_secret": app_secret,
        "access_token": short_lived_token,
    }
    try:
        resp = httpx.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        return resp.json().get("access_token")
    except httpx.HTTPError as exc:
        logger.error("Token exchange failed: %s", exc)
        return None
