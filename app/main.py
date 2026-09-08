"""FastAPI entry point for the Instagram AI agent POC.

Run locally:  uvicorn app.main:app --reload --port 8000
Then expose with ngrok/cloudflared and point the Meta webhook at /webhook.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI

from . import db, webhooks
from .config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    db.init_db()

    app = FastAPI(title="Instagram AI Agent (Jewelry) — POC")
    app.include_router(webhooks.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "business": settings.business_name}

    return app


app = create_app()
