# Instagram AI Agent — Architecture (Phased)

**Project:** Instagram AI Agent for a jewelry business
**Scope:** Answer FAQs, provide accurate pricing/quotes, and book consultations with the owner/specialist on a calendar.
**Explicitly out of scope (for now):** e-commerce, online checkout, in-app payments.
**Audience:** Technical implementer and business owner.

> This document is organized in **phases** (what to build, in order) and **sections** (the parts of the system). Read Section A for the big picture, then follow the phases. Section G is the production hardening checklist.

---

## Section A — System overview

### A.1 What the agent does (the loop)

```
                         ┌───────────────────────────────────────────┐
  Instagram DM           │                 YOUR SERVER                │
  from customer          │                                           │
        │                │   1. Webhook receiver (verify + queue)    │
        ▼                │              │                            │
  ┌───────────┐  push    │              ▼                            │
  │   Meta    │────────► │   2. Agent worker (Claude)                │
  │ Graph API │          │        │                                  │
  └───────────┘          │        │  calls tools as needed:          │
        ▲                │        ├─► search_faq()                   │
        │                │        ├─► lookup_price()                 │
        │  Send API      │        ├─► book_consultation()            │
        │◄───────────────│        └─► escalate_to_human()            │
  reply to customer      │        │                                  │
                         │        ▼                                  │
                         │   3. Reply via Instagram Send API         │
                         │   4. Persist conversation + booking + log │
                         └───────────────────────────────────────────┘
                                   │            │             │
                              ┌────▼───┐  ┌─────▼─────┐  ┌────▼─────┐
                              │Catalog │  │ Knowledge │  │ Calendar │
                              │ + price│  │  base/FAQ │  │(Calendly/│
                              │  data  │  │           │  │ Google)  │
                              └────────┘  └───────────┘  └──────────┘
```

### A.2 The core principle: the agent is orchestration, not knowledge

The LLM (Claude) decides **what to do** and **how to phrase it**, but it must **never invent facts** — especially prices. Every price and every booking comes from a **tool call** backed by real data. The system prompt enforces: *"Only state a price returned by `lookup_price`. If none is found, do not guess — offer to book a consultation."* This single rule is what makes an AI agent safe for a high-value business like jewelry.

### A.3 Components at a glance

| # | Component | Responsibility | POC choice |
|---|---|---|---|
| 1 | **Webhook receiver** | Accept + verify Meta deliveries, ack fast | FastAPI endpoint |
| 2 | **Agent worker** | Run the Claude agent loop with tools | Claude API (Anthropic SDK) |
| 3 | **Sender** | Send replies via Instagram Send API | httpx client |
| 4 | **Catalog / pricing** | Source of truth for pieces & prices | JSON/SQLite + `lookup_price` |
| 5 | **Knowledge base** | FAQ / policies | Markdown in prompt (RAG later) |
| 6 | **Calendar** | Show availability, create bookings | Calendly link → API |
| 7 | **Datastore** | Conversations, bookings, audit log | SQLite → Postgres |
| 8 | **Admin/handoff** | Human takeover, review | Log + flag → inbox UI later |

### A.4 Recommended stack

- **Language/framework:** Python 3.11+ with **FastAPI** (best LLM tooling ecosystem).
- **LLM:** **Claude** via the Anthropic SDK, using **tool use** (function calling). Use a Sonnet-class model for the balance of cost/latency/quality; escalate to an Opus-class model only if reasoning demands it. *(Confirm exact current model IDs and pricing from the `claude-api` reference before wiring the client — do not hard-code from memory.)*
- **HTTP client:** `httpx`.
- **Datastore:** SQLite for the POC → PostgreSQL for production.
- **Queue (production):** Redis / RQ or a cloud queue; inline processing is acceptable for the POC.
- **Dev tunnel:** ngrok / cloudflared to expose the webhook to Meta during development.
- **Deploy:** a container host — Render / Railway / Fly.io for speed; AWS/GCP for scale.

---

## Section B — Data model (the foundation)

Design these before writing agent logic; everything depends on them.

### B.1 Catalog / pricing record
Each pictured piece is one record:
```
Item {
  id, sku
  title                      # "Classic Solitaire Ring"
  description
  category                   # ring / necklace / earrings / bracelet
  metal, purity              # 18K yellow gold, etc.
  stone, carat
  size / dimensions
  price          | null      # fixed price, or null if quote-required
  price_type                 # "fixed" | "quote_required"
  currency
  in_stock                   # bool
  instagram_media_ids[]      # links this record to the IG post(s) showing it
  image_urls[]
  updated_at
}
```

### B.2 Conversation & message log
```
Conversation { id, ig_user_id, status(open/booked/escalated/closed),
               created_at, last_msg_at }
Message      { id, conversation_id, direction(in/out), text,
               referenced_media_id | null, tool_calls_json, created_at }
```

### B.3 Booking record
```
Booking { id, conversation_id, customer_name, contact(phone/email),
          interest(item/service), consult_type(in-store/video/call),
          slot_start, slot_end, calendar_event_id, status, created_at }
```

### B.4 Lead / customer (you don't own the IG relationship — capture contact!)
```
Lead { id, ig_user_id, name, phone, email, interest, source, created_at }
```

### B.5 Audit log (compliance + debugging)
Every quote given, every booking, every escalation, every tool call — persisted with timestamps.

---

## Section C — The agent's tools (its capabilities)

The agent is defined by the tools you give it. For this scope, exactly four:

### C.1 `search_faq(query) → answer`
Returns store info / policies / process. **POC:** the FAQ is a curated document injected into the system prompt (small enough to fit). **Later:** vector search (RAG) when the knowledge grows.

### C.2 `lookup_price(item_reference) → {price | quote_required | not_found}`
The **safety-critical** tool. Resolves which piece the customer means, then returns the catalog price or a `quote_required`/`not_found` signal. **The agent may only state prices this tool returns.**

Handling *"which item?"* (the image→product problem):
- If the DM is a **story reply** or **post share**, the webhook payload includes a **media reference** → map it via `instagram_media_ids`.
- If it's a **cold text DM** ("how much is the gold one?"), the agent **asks a clarifying question** or asks the customer to **share/link the post**. It must not guess.

### C.3 `book_consultation(name, contact, interest, consult_type, slot) → confirmation`
Creates the calendar booking.
- **POC (Phase 3a):** agent shares your **Calendly/Cal.com link** and captures the lead details in the DB.
- **Upgrade (Phase 3b):** agent fetches real open slots via the **Calendly API** (or **Google Calendar** free/busy), lets the customer pick inside the DM, and creates the event directly, returning a confirmation.

### C.4 `escalate_to_human(reason) → flag`
Flags the conversation for a person and tells the customer a specialist will follow up. Triggered by: negotiation, complex custom requests, complaints, low confidence, or explicit customer request.

---

## Section D — The agent brain (prompt & policy)

The system prompt is where most quality lives. It must specify:

1. **Persona & tone** — warm, concise, knowledgeable jewelry consultant; the brand voice.
2. **The prime directive on pricing** — *only* quote from `lookup_price`; never invent, estimate off-catalog, or negotiate on your own; offer a consultation instead.
3. **Goal orientation** — help genuinely, and steer qualified interest toward **booking a consultation** (the agent's success metric).
4. **Escalation rules** — when to call `escalate_to_human`.
5. **Disambiguation behavior** — how to ask which piece the customer means.
6. **Contact capture** — collect name + phone/email during booking (you can't re-message freely after 24h).
7. **Guardrails** — stay on-topic (jewelry/store); don't make guarantees about authenticity/value beyond the knowledge base; comply with the 24-hour messaging window.
8. **Handoff transparency** — tell the customer when a human will take over.

Keep the prompt **versioned in the repo** so you can iterate and A/B test.

---

## Section E — Build phases (do them in this order)

### Phase 0 — Prerequisites & scaffolding
- Complete **Doc 1** (Instagram/Meta setup) at least through *test users*.
- Repo scaffold: FastAPI app, config/secrets loading (`.env`, never committed), SQLite, logging.
- Health-check endpoint; deployable skeleton.
- **Exit criteria:** app runs locally and is reachable via ngrok.

### Phase 1 — Prove the pipe (echo bot)
- Implement webhook **GET verify** (echo challenge) + **POST receive** with `X-Hub-Signature-256` verification.
- Parse an incoming DM; reply with a hard-coded echo via the **Send API**.
- Exchange short-lived token → **long-lived token**; store it.
- **Exit criteria:** a tester DMs the account and gets an automated reply. *This de-risks the entire integration before any AI.*

### Phase 2 — FAQ agent
- Wire the **Claude client** with tool use.
- Implement `search_faq` (FAQ doc in prompt).
- Add the system prompt (Section D) and **per-conversation memory** (load history from DB).
- Swap the echo for real agent replies.
- **Exit criteria:** agent correctly answers the top ~15 store FAQs.

### Phase 3 — Pricing & quotes (the careful phase)
- Build the **catalog** data (Section B.1) and `lookup_price`.
- Implement **image→product mapping** from story-reply/post-share payloads + the disambiguation fallback.
- Enforce the **never-guess** guardrail (test it hard — try to make it hallucinate a price and confirm it refuses).
- **Exit criteria:** agent quotes correct catalog prices, and for unknown/custom items it *declines to guess* and pivots to booking.

### Phase 4 — Consultation booking
- **3a:** `book_consultation` via Calendly link + capture lead details.
- **3b:** upgrade to API-driven slot selection + event creation (Calendly or Google Calendar).
- Send confirmation; mark conversation `booked`.
- **Exit criteria:** a full DM conversation ends in a real calendar booking with the customer's contact captured.

### Phase 5 — Human handoff & operations
- `escalate_to_human` + a simple admin view (even just a filtered DB list / Slack/email alert) of flagged conversations.
- Handle the **24-hour window** (human agent tag for late follow-ups).
- **Exit criteria:** flagged conversations reliably reach a human.

### Phase 6 — Hardening & launch (see Section G)
- Move to Postgres + a real queue; add monitoring, retries, rate limiting, security review.
- Complete **App Review** and switch to **Live**.
- **Exit criteria:** running on production infra, messaging real customers.

---

## Section F — Key data & control flows

### F.1 Inbound message flow
1. Meta `POST`s to webhook → verify signature → return **200 immediately** (Meta retries on non-200; slow responses cause duplicates).
2. Enqueue the event (or process inline for POC).
3. Worker loads conversation history + resolves any referenced media.
4. Call Claude with system prompt + history + tools.
5. If Claude calls a tool → execute → feed result back → loop until it produces a reply.
6. Send reply via Send API; persist inbound, outbound, and all tool calls.

### F.2 Pricing flow (the guarded path)
`customer asks price` → resolve item (media ref or clarify) → `lookup_price` →
- **fixed price** → state it, offer consultation to see it in person
- **quote_required** → gather details, offer consultation for a precise quote
- **not_found / ambiguous** → ask which piece, or offer consultation
→ *never* a guessed number.

### F.3 Booking flow
`intent to talk to specialist` → collect name + contact + interest + consult type → offer slots (link or API) → confirm → create event → save `Booking` + `Lead` → confirmation message.

### F.4 Escalation flow
trigger detected → `escalate_to_human` → flag conversation, notify staff (Slack/email) → tell customer a specialist will reply → (if >24h later) use human agent tag.

---

## Section G — Production hardening checklist

**Security**
- [ ] Verify `X-Hub-Signature-256` on every webhook delivery
- [ ] Secrets in a manager (not git); rotate the app secret/token
- [ ] Long-lived token **refresh** job before expiry
- [ ] Privacy policy live; store only necessary PII; retention policy
- [ ] Input sanitization; treat DM content as untrusted

**Reliability**
- [ ] Fast webhook ack + async queue (Redis/RQ or cloud)
- [ ] Idempotency / dedupe (Meta can redeliver)
- [ ] Retries with backoff on Send API failures
- [ ] Respect Meta rate limits; throttle
- [ ] Postgres with backups

**Quality & safety**
- [ ] Automated **eval set** for pricing accuracy + hallucination resistance (run on every prompt change)
- [ ] Confidence-based escalation; log every quote for audit
- [ ] Prompt/version control; changelog
- [ ] Fallback message if the LLM/API errors ("a specialist will get back to you")

**Observability**
- [ ] Structured logging + request tracing
- [ ] Dashboards: DM volume, deflection rate, bookings created, escalations, latency, cost per conversation
- [ ] Alerting on webhook failures / token expiry / error spikes

**Business/operational**
- [ ] Keep the **catalog & prices up to date** (a stale price is a real-world liability) — a simple admin/spreadsheet-sync process
- [ ] Staff process for escalations & bookings
- [ ] Clear disclosure that customers are chatting with an AI assistant (and how to reach a human)

---

## Section H — What to decide before Phase 3

Two decisions shape the code and should be locked before pricing/booking work:

1. **Pricing model** — `fixed price list` (recommended for POC) vs `formula-based` (metal weight × live rate + making + stone) vs `quote-on-request`. Start fixed; a wrong auto-quote on a high-value piece is worse than none.
2. **Calendar tool** — **Calendly/Cal.com** (fastest) vs **Google Calendar API** (more control). Start with a Calendly link, upgrade to API-driven slots.

---

## Appendix — Suggested repository layout

```
AI-Automation/
├── docs/
│   ├── 01-instagram-business-account-setup.md
│   └── 02-architecture.md
├── app/
│   ├── main.py                 # FastAPI app + routes
│   ├── webhooks/               # verify + receive + signature check
│   ├── agent/                  # Claude client, system prompt, loop
│   ├── tools/                  # search_faq, lookup_price, book_consultation, escalate
│   ├── instagram/              # Send API client, token management
│   ├── calendar/               # Calendly / Google Calendar integration
│   ├── data/                   # models, DB access
│   └── config.py               # env/secrets loading
├── data/
│   ├── catalog.json            # sample jewelry catalog
│   └── faq.md                  # knowledge base
├── prompts/
│   └── system_prompt.md        # versioned agent prompt
├── tests/
│   └── evals/                  # pricing-accuracy & no-hallucination checks
├── .env.example                # documents required secrets (no real values)
├── requirements.txt
└── README.md
```
