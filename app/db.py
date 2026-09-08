"""Minimal SQLite persistence for the POC.

Tables: conversations, messages, bookings, leads, escalations. Deliberately
small and dependency-free (stdlib sqlite3). Swap for Postgres + a real ORM in
production (see docs/02-architecture.md, Section G).
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    ig_user_id TEXT PRIMARY KEY,
    status     TEXT NOT NULL DEFAULT 'open',
    created_at REAL NOT NULL,
    last_msg_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ig_user_id    TEXT NOT NULL,
    direction     TEXT NOT NULL,            -- 'in' | 'out'
    text          TEXT NOT NULL,
    referenced_media_id TEXT,
    created_at    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS bookings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ig_user_id    TEXT NOT NULL,
    name          TEXT,
    contact       TEXT,
    interest      TEXT,
    consult_type  TEXT,
    created_at    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS escalations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ig_user_id    TEXT NOT NULL,
    reason        TEXT,
    created_at    REAL NOT NULL
);
"""


def _db_path() -> Path:
    path = Path(get_settings().database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def touch_conversation(ig_user_id: str) -> None:
    now = time.time()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO conversations (ig_user_id, status, created_at, last_msg_at)
                   VALUES (?, 'open', ?, ?)
                   ON CONFLICT(ig_user_id) DO UPDATE SET last_msg_at = excluded.last_msg_at""",
            (ig_user_id, now, now),
        )


def set_conversation_status(ig_user_id: str, status: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE conversations SET status = ? WHERE ig_user_id = ?",
            (status, ig_user_id),
        )


def log_message(
    ig_user_id: str,
    direction: str,
    text: str,
    referenced_media_id: str | None = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO messages (ig_user_id, direction, text, referenced_media_id, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
            (ig_user_id, direction, text, referenced_media_id, time.time()),
        )


def get_history(ig_user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return recent messages oldest-first, shaped for the Claude messages array."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT direction, text FROM messages
                   WHERE ig_user_id = ? ORDER BY id DESC LIMIT ?""",
            (ig_user_id, limit),
        ).fetchall()
    rows = list(reversed(rows))
    return [
        {"role": "assistant" if r["direction"] == "out" else "user", "content": r["text"]}
        for r in rows
    ]


def save_booking(
    ig_user_id: str, name: str, contact: str, interest: str, consult_type: str
) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO bookings (ig_user_id, name, contact, interest, consult_type, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
            (ig_user_id, name, contact, interest, consult_type, time.time()),
        )


def save_escalation(ig_user_id: str, reason: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO escalations (ig_user_id, reason, created_at) VALUES (?, ?, ?)",
            (ig_user_id, reason, time.time()),
        )
