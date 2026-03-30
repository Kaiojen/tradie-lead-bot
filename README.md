# Tradie Lead Bot

> **Never miss a job while you're on the tools.**

An automated enquiry inbox built for Australian tradies. When a customer fills out the web form, the system instantly replies by SMS and sends you a job alert — all while you're on-site.

---

## What it does

1. Customer submits a quote request via an embedded web form
2. Lead is saved to the database immediately (before any external calls)
3. A background worker qualifies the enquiry with AI (GPT-4o mini)
4. Customer receives an SMS auto-reply
5. Tradie receives an SMS job alert with suburb, service, and urgency
6. Tradie manages all enquiries from a web Inbox (New / Follow Up / Done)

If AI fails, a raw SMS alert is still sent. If SMS fails, the Inbox flags it with a Retry button.

---

## Architecture

Three independently deployed services:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Web (Next.js) │     │   API (FastAPI)  │     │ Worker (Python) │
│                 │────▶│                 │────▶│                 │
│  Landing page   │     │  REST endpoints │     │  process_lead   │
│  Inbox UI       │     │  Auth (JWT)     │     │  send_sms       │
│  Setup wizard   │     │  Webhooks       │     │  Watchdog       │
└─────────────────┘     └────────┬────────┘     └────────┬────────┘
                                  │                        │
                         ┌────────▼────────────────────────▼────────┐
                         │              Supabase (Postgres)          │
                         │  leads · processing_jobs · messages       │
                         │  audit_logs · templates · subscriptions   │
                         └───────────────────────────────────────────┘
```

| Layer      | Technology                    |
|------------|-------------------------------|
| Frontend   | Next.js 15, React 19, TypeScript |
| Backend    | FastAPI, Python 3.12, SQLAlchemy async |
| Worker     | Python async process (asyncio) |
| Database   | Supabase (Postgres) with RLS  |
| Auth       | Supabase Auth (magic link + password) |
| Queue      | `processing_jobs` table (Postgres) |
| AI         | OpenAI GPT-4o mini            |
| SMS        | Twilio Messaging Service      |
| Billing    | Paddle                        |
| Deploy     | Render (3 services)           |
| Monitoring | Sentry + structured JSON logs |

---

## Project structure

```
tradie-lead-bot/
├── apps/
│   ├── api/                    # FastAPI backend
│   │   └── app/
│   │       ├── core/           # Rate limiting, errors, middleware
│   │       ├── dependencies/   # Auth (JWT), DB session
│   │       ├── routers/        # public, enquiries, account, webhooks
│   │       └── services/       # Business logic per domain
│   ├── web/                    # Next.js frontend
│   │   └── app/
│   │       ├── (authenticated)/# Protected pages (Inbox, Setup, Settings…)
│   │       ├── f/[token]/      # Public lead capture form
│   │       ├── login/          # Auth page
│   │       ├── pricing/        # Pricing page
│   │       └── page.tsx        # Landing page
│   └── worker/                 # Background job processor
│       └── app/main.py         # WorkerService + watchdog
├── shared/
│   └── python/tradie_shared/   # Models, schemas, enums, security, logging
├── migrations/                 # SQL migrations (run in order)
├── tests/                      # API, security, and worker tests
├── infra/render/               # render.yaml (3-service deploy)
├── requirements/               # api.txt, worker.txt, dev.txt
└── docs/                       # Architecture and spec documents
```

---

## API endpoints

### Public
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/leads/ingest` | Submit a new enquiry (rate-limited per IP) |
| `GET`  | `/health` | Health check |

### Enquiries (authenticated)
| Method | Path | Description |
|--------|------|-------------|
| `GET`    | `/api/enquiries` | List enquiries with status filter + pagination |
| `GET`    | `/api/enquiries/{id}` | Enquiry detail (decrypts PII) |
| `PATCH`  | `/api/enquiries/{id}/status` | Move to New / Follow Up / Done |
| `POST`   | `/api/enquiries/{id}/reprocess` | Re-queue AI qualification (owner only) |
| `POST`   | `/api/enquiries/{id}/retry` | Retry failed SMS |
| `GET`    | `/api/enquiries/{id}/notes` | List notes |
| `POST`   | `/api/enquiries/{id}/notes` | Add a note |

### Account & Setup
| Method | Path | Description |
|--------|------|-------------|
| `GET`   | `/api/me` | Current user |
| `GET`   | `/api/account` | Account settings |
| `PATCH` | `/api/account` | Update business profile / hours |
| `GET`   | `/api/setup` | Setup state + embed code |
| `POST`  | `/api/setup/business-basics` | Step 1 |
| `POST`  | `/api/setup/your-number` | Step 2 |
| `POST`  | `/api/setup/auto-reply` | Step 3 |
| `POST`  | `/api/setup/test-drive` | Step 4 — sends real SMS |
| `POST`  | `/api/setup/complete` | Step 5 |
| `GET`   | `/api/templates` | List SMS templates |
| `PATCH` | `/api/templates/{id}` | Update template content |
| `POST`  | `/api/templates/{id}/send-test` | Send test SMS |
| `GET`   | `/api/team` | List team members |
| `POST`  | `/api/team/invite` | Invite staff (owner only) |
| `DELETE`| `/api/team/{id}` | Remove member (owner only) |
| `GET`   | `/api/subscription` | Subscription status (owner only) |
| `POST`  | `/api/subscription/portal` | Open Paddle billing portal |
| `POST`  | `/api/subscription/cancel` | Cancel at period end |
| `POST`  | `/api/support` | Submit support request |

### Webhooks
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/webhooks/twilio` | Delivery status callbacks (HMAC validated) |
| `POST` | `/webhooks/paddle` | Billing events (HMAC SHA-256 validated) |

---

## Database schema

16 tables across 4 migrations:

```
users                   ← synced from Supabase Auth via trigger
accounts                ← business profile, hours, onboarding state
account_memberships     ← owner / staff roles (RBAC)
lead_sources            ← web form tokens (one per account)
leads                   ← enquiries (PII encrypted, phone/email hashed)
lead_events             ← immutable event timeline per lead
lead_notes              ← team notes per enquiry
processing_jobs         ← async job queue (process_lead, send_sms)
templates               ← SMS auto-reply content (per account)
messages                ← outbound SMS records
message_attempts        ← per-attempt logs for every send
delivery_status_events  ← Twilio webhook callbacks
subscriptions           ← Paddle subscription state
billing_events          ← processed Paddle events (idempotent)
billing_events_unresolved ← unmatched Paddle events
audit_logs              ← all critical actions (immutable)
```

Row-Level Security is enabled on all tables. Every query is scoped by `account_id`.

---

## Security model

- **Auth**: Supabase JWT validated on every API request (HS256)
- **RBAC**: `owner` and `staff` roles enforced via `require_owner` dependency
- **Multi-tenancy**: All queries filter by `account_id`; RLS as second layer
- **PII encryption**: `customer_phone` and `customer_email` encrypted at rest with Fernet (AES-128-CBC)
- **PII hashing**: Phone and email HMAC-SHA256 hashed for duplicate detection without decrypting
- **Webhook validation**: Twilio HMAC + timestamp; Paddle HMAC SHA-256 + timestamp (5-min window)
- **Rate limiting**: Per-IP for public endpoints; per-user for API and manual actions (Postgres sliding window)
- **Secrets**: All keys via environment variables — never in code

---

## Worker behaviour

The worker runs as a separate process and polls `processing_jobs` continuously:

```
loop:
  watchdog()          ← re-queues jobs with expired locks
  job = claim()       ← SELECT FOR UPDATE SKIP LOCKED
  handle(job)
    process_lead:
      1. Run AI qualification (OpenAI)
      2. Check for duplicates (phone hash window)
      3. Build customer SMS + tradie alert
      4. Queue send_sms job
      (if AI fails → raw SMS fallback still queued)
    send_sms:
      1. Send each queued/failed message via Twilio
      2. Record MessageAttempt
      3. On failure → raise RetryableJobError
  on RetryableJobError:
    backoff = 2^attempts seconds
    schedule retry (max 3 attempts)
    on max_attempts → status = "failed" (dead-letter)
```

---

## Setup (5 steps)

1. **Business Basics** — business name + trade type
2. **Your Number** — mobile number for job alerts
3. **Your Auto-Reply** — customise the SMS sent to customers
4. **Test Drive** — sends a real SMS to verify the connection
5. **Connect** — embed code + Google Business link to capture leads

---

## Local development

### Prerequisites

- Python 3.12+
- Node.js 20+
- A Supabase project
- Twilio account (Messaging Service)
- OpenAI API key

### 1. Clone and configure

```bash
git clone https://github.com/Kaiojen/tradie-lead-bot.git
cd tradie-lead-bot
cp .env.example .env
# Fill in all values in .env
```

### 2. Generate encryption keys

```python
# Run once to generate the Fernet key
from cryptography.fernet import Fernet
import secrets
print("APP_ENCRYPTION_KEY=" + Fernet.generate_key().decode())
print("APP_HASH_KEY=" + secrets.token_hex(32))
```

### 3. Run migrations

Run `migrations/0001_initial_schema.sql` through `migrations/0004_lead_notes_rls_hardening.sql` in order against your Supabase database (SQL editor or `psql`).

### 4. Install and start the API

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements/api.txt
PYTHONPATH=. uvicorn apps.api.app.main:app --reload --port 8000
```

### 5. Start the worker

```bash
# In a second terminal (same venv)
pip install -r requirements/worker.txt
PYTHONPATH=. python -m apps.worker.app.main
```

### 6. Start the frontend

```bash
cd apps/web
npm install
npm run dev
# Open http://localhost:3000
```

---

## Running tests

```bash
pip install -r requirements/dev.txt
pytest
```

Key test files:

| File | Covers |
|------|--------|
| `tests/api/test_enquiries.py` | Message delivery flag logic |
| `tests/api/test_twilio_webhooks.py` | Twilio HMAC + stale date rejection |
| `tests/api/test_paddle_webhooks.py` | Paddle signature, subscription snapshot, account status mapping |
| `tests/api/test_account_services.py` | Billing portal, subscription serialisation |
| `tests/api/test_auth_context.py` | JWT auth + owner role enforcement |
| `tests/security/test_shared_security.py` | Fernet encryption, HMAC hashing, phone/email masking |
| `tests/security/test_multi_tenant_isolation_live_db.py` | Cross-account data isolation |
| `tests/worker/test_alerts.py` | Tradie alert body (AI + fallback) |

---

## Deployment (Render)

Three services defined in `infra/render/render.yaml`:

| Service | Type | Start command |
|---------|------|---------------|
| `tradie-lead-bot-web` | Node web | `npm run start` |
| `tradie-lead-bot-api` | Python web | `uvicorn apps.api.app.main:app` |
| `tradie-lead-bot-worker` | Python worker | `python -m apps.worker.app.main` |

Set all environment variables from `.env.example` in the Render dashboard for each service.

---

## Environment variables

| Variable | Required by | Description |
|----------|-------------|-------------|
| `DATABASE_URL` | api, worker | `postgresql+asyncpg://...` |
| `SUPABASE_JWT_SECRET` | api | From Supabase project settings |
| `SUPABASE_URL` | api | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | api | For admin operations |
| `APP_ENCRYPTION_KEY` | api, worker | Fernet key (base64, 32 bytes) |
| `APP_HASH_KEY` | api, worker | HMAC secret for phone/email hashing |
| `TWILIO_ACCOUNT_SID` | api, worker | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | api, worker | Twilio auth token |
| `TWILIO_MESSAGING_SERVICE_SID` | worker | Twilio messaging service |
| `OPENAI_API_KEY` | worker | GPT-4o mini access |
| `PADDLE_WEBHOOK_SECRET` | api | Paddle webhook signing secret |
| `SENTRY_DSN` | api, worker | Optional error tracking |
| `NEXT_PUBLIC_API_BASE_URL` | web | Full URL to the API service |
| `NEXT_PUBLIC_SUPABASE_URL` | web | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | web | Supabase anon key |

---

## Billing flow

1. Tradie signs up → 14-day trial starts (no card required)
2. Trial ends → Paddle checkout linked from Subscription page
3. Paddle sends webhooks → `billing_events` table updated
4. `account.status` transitions: `trial` → `active` → `suspended` → `cancelled`
5. Inbox shows banners for payment issues and expired trials

---

## Spec documents

Full planning documents are in the `docs/` folder:

| File | Content |
|------|---------|
| `01_arquitetura_final.md` | System architecture and module contracts |
| `02_semantica_final.md` | UI vocabulary and terminology rules |
| `03_fluxo_paginas.md` | Page flow and UI states |
| `04_criterios_seguranca.md` | Security requirements |
| `05_brief_tecnico_final.md` | Database schema and technical brief |
| `06_checklist_prelaunch.md` | Pre-launch checklist |

---

## Sprint status

**Sprint 1 — complete.** Core system is fully functional end-to-end.

Sprint 2 priorities:
1. Billing/trial banners visible on all pages (not just Inbox)
2. 3 niche-specific Auto-Reply templates in Setup Step 3
3. FAQ sections on landing page and Support page
4. External monitoring/alerting for stuck jobs and webhook failures
5. `Turn On / Turn Off` toggle for individual templates
