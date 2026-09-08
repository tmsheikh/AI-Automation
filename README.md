# Instagram AI Agent (Jewelry) — POC

An AI agent that answers Instagram DMs for a jewelry business: **FAQs**,
**accurate fixed pricing**, and **booking consultations** with the owner/specialist
via Calendly. No e-commerce / no payments.

> **Full docs:**
> - `docs/01-instagram-business-account-setup.md` — Meta/Instagram account & app setup (do this first).
> - `docs/02-architecture.md` — phased architecture and production hardening.

## What's in this POC

| Piece | File |
|---|---|
| FastAPI app + health check | `app/main.py` |
| Webhook (verify + signed receive) | `app/webhooks.py` |
| Claude agent loop (manual tool-use) | `app/agent.py` |
| The four tools | `app/tools.py` |
| Fixed-price catalog + lookup | `app/catalog.py`, `data/catalog.json` |
| FAQ knowledge base | `data/faq.md` |
| Instagram Send API + token exchange | `app/instagram.py` |
| SQLite persistence | `app/db.py` |
| System prompt (persona + guardrails) | `prompts/system_prompt.md` |
| Local chat (no Instagram needed) | `scripts/chat_local.py` |
| Guardrail tests | `tests/test_tools.py` |

The agent has exactly four tools: `search_faq`, `lookup_price`,
`book_consultation`, `escalate_to_human`. **The prime rule** (enforced in the
system prompt and the tool layer): the agent only ever states a price returned by
`lookup_price` — it never invents one, and pivots to a consultation for
custom/unknown pieces.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in values

# Run the guardrail tests (no API key needed):
pytest -q

# Talk to the agent locally (needs ANTHROPIC_API_KEY or `ant auth login`):
python -m scripts.chat_local

# Run the webhook server:
uvicorn app.main:app --reload --port 8000
```

## Connecting to Instagram (dev)

1. Complete `docs/01-...` through **test users**.
2. Expose the server: `ngrok http 8000` (or `cloudflared tunnel`).
3. In the Meta app dashboard, set the webhook **Callback URL** to
   `https://<your-tunnel>/webhook` and the **Verify Token** to your
   `WEBHOOK_VERIFY_TOKEN`; subscribe to the **`messages`** field.
4. DM the business account from a tester account → the agent replies.

Without Instagram/Meta credentials set, the app still runs: replies are logged
instead of sent, so you can develop the agent against `scripts/chat_local.py`.

## Configuration

All config is via environment (`.env`); see `.env.example`. Notable:
- `CLAUDE_MODEL` — defaults to `claude-opus-5`. For a high-volume DM workload you
  can set `claude-sonnet-5` to cut cost; measure answer quality first.
- `CALENDLY_SCHEDULING_URL` — the link the agent shares to book consultations.
- Secrets (`META_APP_SECRET`, `INSTAGRAM_ACCESS_TOKEN`, `ANTHROPIC_API_KEY`)
  live only in `.env` (git-ignored) — never commit them.

## Where this POC stops (and production begins)

Inline webhook processing, SQLite, a Calendly *link* (not API slot-picking), and
no queue/monitoring. See `docs/02-architecture.md` §E (phases 4b–6) and §G for
the path to production.
