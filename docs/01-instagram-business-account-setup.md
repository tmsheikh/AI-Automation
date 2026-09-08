# Instagram Business Account & Meta App Setup Guide

**Project:** Instagram AI Agent (Jewelry) — FAQ answering, pricing/quotes, and consultation booking
**Audience:** Business owner + technical implementer
**Purpose:** Everything you must set up on the Instagram / Meta side *before* any agent code can send or receive DMs.

> ⚠️ **Read this first.** The only production-legitimate way to auto-answer Instagram DMs is the official **Instagram Platform API** from Meta. Scraping or unofficial "private API" libraries violate Meta's Terms and will get the account permanently banned. Everything below uses the official path.
>
> ⏳ **Start early.** The long pole in this whole project is **Meta App Review** (getting permission to message real customers). You can build and test the entire agent against *test users* while review is pending, so kick off the account setup and review process on day one.

---

## Part 0 — Vocabulary (so the steps make sense)

| Term | What it means |
|---|---|
| **Instagram Professional account** | A Business or Creator account (not a personal one). Required for any API access. |
| **Meta app** | A project you register at developers.facebook.com. It holds your API credentials and permissions. |
| **Graph API** | Meta's REST API. Instagram messaging is exposed through it. |
| **Webhook** | A public HTTPS URL Meta calls to *push* incoming DMs to your server in real time. |
| **Access token** | The credential your server uses to call the API (e.g., to send a reply). |
| **Permission / scope** | A specific capability you request, e.g. `instagram_business_manage_messages`. |
| **Standard vs Advanced Access** | *Standard* = works only with people who have a role on your app (test/dev/admin). *Advanced* = works with the general public. Advanced requires App Review. |
| **App Review** | Meta's approval process (with a screencast demo) to unlock Advanced Access for messaging permissions. |

---

## Part 1 — Convert / create the Instagram account

You need a **Professional** Instagram account.

1. Open the Instagram mobile app and log into the account you'll use for the business (or create a new one).
2. Go to **Profile → ☰ menu → Settings and privacy**.
3. Find **Account type and tools → Switch to professional account**.
4. Choose **Business** (recommended for a store) — you'll pick a category such as *Jewelry/Watches*.
5. Complete the business profile: contact email, phone, address, hours.

**Checklist**
- [ ] Account is set to **Business** (or Creator)
- [ ] Business contact details filled in
- [ ] You have the Instagram login credentials handy
- [ ] Two-factor authentication enabled (protect the account — it's now a business asset)

---

## Part 2 — Choose your integration path

Meta offers **two** ways to build Instagram messaging. Pick one now; it changes which permissions and login flow you use.

### Option A — Instagram API with **Instagram Login** ✅ *Recommended for this project*
- The Instagram professional account logs in directly. **No Facebook Page required.**
- Simpler for an Instagram-only use case (which is exactly ours).
- Uses permissions prefixed `instagram_business_*`.
- This is Meta's current recommended path for standalone Instagram messaging.

### Option B — Instagram API with **Facebook Login**
- Requires the Instagram account to be **linked to a Facebook Page**.
- Makes sense if you also manage a Facebook Page / run Meta Ads through the same app, or use Business Manager heavily.
- Uses permissions prefixed `instagram_manage_*` / `pages_*`.

> **Decision for this POC: use Option A (Instagram Login).** The rest of this document follows Option A and notes Option B differences where they matter.
>
> 📌 *If you already run a linked Facebook Page and Business Manager, tell the implementer — Option B may fit your existing setup better.*

**If you choose Option B**, additionally:
- [ ] Create or identify the **Facebook Page** for the business
- [ ] Link the Instagram account to that Page (Instagram app → Settings → *Accounts Center* / *Linked accounts*)
- [ ] You'll be admin of both

---

## Part 3 — Create the Meta Developer app

1. Go to **https://developers.facebook.com/** and log in with the Facebook account that will own the app.
2. Complete **developer registration** if prompted (accept terms, verify account).
3. Click **My Apps → Create App**.
4. For **use case**, choose the one that exposes Instagram messaging:
   - Select **"Other" → Business** app type if prompted, *or* the **Instagram** use case if offered directly. (Meta's wizard wording changes; the goal is an app that can add the **Instagram** product with messaging.)
5. Name the app (e.g., `JewelryDM-Agent`), set the contact email, create it.
6. In the app dashboard, **Add the Instagram product** (look for *"Instagram" → Set up*).

**Checklist**
- [ ] Meta developer account verified
- [ ] App created
- [ ] **Instagram** product added to the app
- [ ] Noted your **App ID** and **App Secret** (Settings → Basic) — treat the secret like a password

---

## Part 4 — Connect the Instagram account to the app

Under the **Instagram** product in your app dashboard:

1. Find the **API setup with Instagram login** section (Option A).
2. Click to **generate an access token** — this launches the Instagram login/authorization flow.
3. Log in with your **Instagram professional account** and **grant the requested permissions** (see Part 5).
4. Copy the generated token and note the **Instagram account ID** shown.

> For **Option B**, you instead connect through the Facebook Login flow and select the linked Page + Instagram account.

**Checklist**
- [ ] Instagram account authorized against the app
- [ ] Short-lived access token generated (you'll exchange it for a long-lived one in code — see Doc 2)
- [ ] Instagram account ID recorded

---

## Part 5 — Request the right permissions (scopes)

For **Option A (Instagram Login)**, the agent needs:

| Permission | Why |
|---|---|
| `instagram_business_basic` | Read basic account/profile and media info |
| `instagram_business_manage_messages` | **The core one** — read and send DMs |
| `instagram_business_manage_comments` | *(Optional)* reply to comments / handle comment-to-DM flows |

For **Option B (Facebook Login)**, the equivalents are `instagram_basic`, `instagram_manage_messages`, `pages_manage_metadata`, `pages_read_engagement`.

**Standard Access** (granted immediately) lets these work **only** with users who have a **role on your app** (you and any testers you add). That is enough to build and demo the entire POC.

**Advanced Access** (needed to message *real* customers) requires **App Review** — see Part 8.

**Checklist**
- [ ] Messaging permission added to the app's requested scopes
- [ ] Confirmed Standard Access is active for testing

---

## Part 6 — Set up Webhooks (how DMs reach your server)

Meta pushes incoming DMs to a public HTTPS endpoint you host.

1. In the app dashboard, open **Webhooks** (or the *Webhooks* section under the Instagram product).
2. You'll provide:
   - **Callback URL** — your server's public HTTPS endpoint (during development, use an **ngrok** or **cloudflared** tunnel to expose your laptop; in production, your deployed server URL).
   - **Verify token** — any secret string you make up; your server must echo Meta's challenge using it to prove ownership.
3. Click **Verify and Save**. Meta sends a `GET` with a challenge; your endpoint must return it (handled by the agent code in Doc 2).
4. **Subscribe to the `messages` field** on the Instagram object (also `messaging_postbacks` if you use quick-reply buttons; `comments` if handling comments).

> Webhook deliveries are signed with your **App Secret** (`X-Hub-Signature-256` header). Your server must verify this signature so nobody can spoof fake DMs. (Implementation is in Doc 2.)

**Checklist**
- [ ] Public HTTPS callback URL available (ngrok for dev)
- [ ] Verify token chosen and stored as a secret
- [ ] Webhook verified & saved in the dashboard
- [ ] Subscribed to the **`messages`** field

---

## Part 7 — Add test users (build the POC without App Review)

While in **Development mode / Standard Access**:

1. App dashboard → **App Roles / Roles**.
2. Add the people who will test as **Testers** (or Admins/Developers). They must **accept** the invite from *their* Meta/Instagram notifications.
3. Those accounts can now DM the business account and the agent can reply — end to end — **before** App Review.

**Checklist**
- [ ] At least one tester account added and invite accepted
- [ ] Confirmed a test DM reaches your webhook and gets a reply

---

## Part 8 — App Review & going live (the long pole)

To message the **general public**, submit for **Advanced Access** on the messaging permission.

**What Meta typically requires:**
1. **App fully configured** — icon, privacy policy URL, category, valid business contact.
2. **Business verification** — verify your business entity in **Meta Business Manager** (may require business documents; this itself can take days). Often required before Advanced Access is granted.
3. **A screencast** clearly demonstrating: a real user sends a DM → your app receives it → your app replies. Reviewers must see the exact permission in use.
4. **Written justification** for why you need `instagram_business_manage_messages` (e.g., "We provide automated customer support and appointment booking for our jewelry business's Instagram DMs.").
5. Submit and wait — **review can take from a few days to a couple of weeks**; expect possible back-and-forth / rejections requiring resubmission.

**Requirements you should prepare in advance (do these while building):**
- [ ] **Privacy Policy** page hosted at a public URL (required — must explain data handling)
- [ ] **Terms of Service** page (recommended)
- [ ] Business verification documents ready (registration, utility bill, etc.)
- [ ] App icon + descriptions
- [ ] Screencast recorded once the POC works with a test user

**Going live**
- [ ] App switched from **Development** to **Live** mode
- [ ] Advanced Access approved for the messaging permission
- [ ] Production webhook URL (not ngrok) configured
- [ ] Long-lived / refreshable token flow in place (see Doc 2)

---

## Part 9 — The messaging rules you must design around

These platform rules directly shape the agent's behavior (covered in Doc 2, but decide-aware now):

1. **24-hour standard messaging window** — you may freely reply to a user within **24 hours** of *their* last message. This is fine for our reactive Q&A + booking flow.
2. **Outside 24 hours** — you cannot send arbitrary messages. The **human agent tag** allows a follow-up up to **7 days** for human-handled support; message tags / templates cover specific cases. Don't design a POC that relies on unsolicited outbound messaging.
3. **No spam / no unsolicited promotional blasts** — violates policy and risks the account.
4. **Rate limits** apply — batch/throttle in production.

---

## Part 10 — Credentials you'll end up with (hand these to the implementer)

Collect these into a secure secrets store (never commit them to git):

| Credential | Where it comes from |
|---|---|
| `APP_ID` | App → Settings → Basic |
| `APP_SECRET` | App → Settings → Basic |
| `INSTAGRAM_ACCOUNT_ID` | From the Instagram authorization step |
| `ACCESS_TOKEN` (long-lived) | Generated + exchanged (Doc 2) |
| `WEBHOOK_VERIFY_TOKEN` | A string you invented in Part 6 |

---

## Setup completion checklist (one glance)

- [ ] Instagram account is **Professional (Business)**
- [ ] Integration path chosen (**Option A – Instagram Login** recommended)
- [ ] *(Option B only)* Facebook Page linked
- [ ] Meta developer account verified
- [ ] Meta app created + **Instagram product added**
- [ ] Instagram account authorized to the app
- [ ] Messaging permission requested (`instagram_business_manage_messages`)
- [ ] Webhook verified + subscribed to `messages`
- [ ] Tester(s) added and accepted
- [ ] End-to-end test DM works in Development mode
- [ ] Privacy Policy + business verification prepared
- [ ] App Review submitted for Advanced Access
- [ ] Switched to Live mode after approval

---

### A note on accuracy
Meta changes its dashboard wording, wizard flow, and exact permission names fairly often. The **concepts** above (professional account → app → Instagram product → authorize → permissions → webhooks → test users → App Review) are stable; if a button label differs from this doc, match it by *intent*. Always cross-check against the official docs: **https://developers.facebook.com/docs/instagram-platform/** (Instagram Platform) and the *Instagram messaging* / *Webhooks* sections there.
