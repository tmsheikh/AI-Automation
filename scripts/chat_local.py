"""Local REPL to talk to the agent without Instagram or Meta.

Useful for Phase 2/3 development: exercises the real Claude agent loop, tools,
catalog, and SQLite — everything except the Instagram transport.

Usage:  python -m scripts.chat_local
(Requires ANTHROPIC_API_KEY or `ant auth login`.)
"""
from __future__ import annotations

from app import agent, db

TEST_USER = "local-test-user"


def main() -> None:
    db.init_db()
    print("Local agent chat. Type 'quit' to exit.\n")
    while True:
        try:
            text = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in {"quit", "exit"}:
            break
        if not text:
            continue
        db.touch_conversation(TEST_USER)
        db.log_message(TEST_USER, "in", text)
        reply = agent.generate_reply(TEST_USER, text)
        print(f"bot > {reply}\n")


if __name__ == "__main__":
    main()
