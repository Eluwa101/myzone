# MyShop backend (Phase 1-4)

FastAPI + SQLAlchemy + Postgres, MVC-style: `models/` (ORM), `schemas/`
(validation), `controllers/` (business logic — the single source of truth
for both the REST API and, later, the agent's tools), `routes/` (thin HTTP
layer).

## Setup

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # mac/linux: .venv/bin/pip
cp .env.example .env                            # edit JWT_SECRET
```

Start Postgres (from the repo root):

```bash
docker compose up -d
```

Apply migrations and run:

```bash
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

## Tests

Tests run against an in-memory SQLite DB (no Postgres needed):

```bash
.venv/Scripts/python -m pytest
```

To verify the real configured database (whatever `DATABASE_URL` in `.env`
points to) end to end, run the smoke test. It creates a throwaway org,
exercises signup/login/customer/transaction/summary, and deletes everything
it created:

```bash
.venv/Scripts/python scripts/smoke_test.py
```

## What's here (Phase 1 scope)

- Multi-tenant auth (signup creates an org + owner user, JWT login)
- Customer CRUD with dedup detection (phone/email/name matching), duplicate
  groups, merge
- Transactions per customer, auto-recomputed customer status + "already
  bought" interest cleanup
- CSV import (flexible header aliasing, auto-merges duplicates) and export
- Dashboard summary (status counts, sales by currency, monthly trend, top
  customers, interest rollup)
- RLS enabled on every table (Supabase's Data API is otherwise auto-exposed
  to `anon`/`authenticated` for anything in `public` - this app doesn't use
  that API at all, only the `postgres` role, which bypasses RLS)

## What's here (Phase 2 scope)

The agent/tools layer (`app/agent/`) - add `GROQ_API_KEY` and/or
`GOOGLE_API_KEY` to `.env` to use it (same Groq→Gemini fallback as
`src/agent.py`; at least one is required).

- `app/agent/tools.py`: tools the model can call, each validated by its
  function's type hints and routed through the *same* controllers the REST
  API uses - one code path for agent writes and UI writes
- Reversible tools (`create_customer`, `update_customer`, `add_transaction`,
  etc.) execute immediately
- Destructive tools (`delete_customer`, `merge_customers`) never mutate
  anything directly - they write a `pending_actions` row and the model is
  instructed to tell the user nothing happened yet. A human confirms via
  `POST /api/agent/pending/{id}/confirm` (or discards via `.../reject`)
  before the write actually happens
- Every tool call that produces a result is logged to `agent_actions` (an
  audit trail of what the AI has actually changed)
- `POST /api/agent/chat` - send `{"message": "..."}`, get back `{"reply":
  ..., "pending_actions": [...]}`; conversation memory is per org+user+thread
  (see Phase 5), backed by Postgres via `app/agent/checkpointer.py` - it
  survives process restarts, not just requests

## What's here (Phase 4 scope)

- `GET`/`PUT /api/settings` - per-org WhatsApp QR settings (business name,
  number, message template). The QR image itself is generated client-side
  (no backend QR rendering needed).
- `POST /api/customers/import` now takes `{"csv_text": "..."}` as a JSON
  body instead of a query parameter - a query string can't carry a
  real-sized CSV file reliably.
- `app/agent/ask_data.py` - the dedicated **read-only** "ask your data"
  chat, separate from Phase 2's general-purpose agent. No tools, no writes:
  it builds a compact text context from precomputed aggregates (same numbers
  `/api/summary` returns) plus a line per customer, then makes a single
  grounded LLM call via `POST /api/agent/ask` (`{"question": "..."}` ->
  `{"answer": "..."}`). Can't change records - if asked to edit something it
  says so and points back to the app.

Frontend (`frontend/`) now has a Settings page (QR generator + CSV
import/export) and an Ask Your Data page, alongside the Phase 3 auth/
customer/dashboard/assistant pages.

## What's here (post-Phase-4 additions)

- **Chat history**: `GET /api/agent/threads`, `GET
  /api/agent/threads/{id}/messages`, `DELETE /api/agent/threads/{id}` -
  real conversations persisted in `chat_threads`/`chat_messages`, so the
  frontend's "New chat" button and history panel can list/reopen past
  conversations, not just reset the visible transcript.
- **Voice input**: the frontend uses the browser's built-in Speech
  Recognition API (no backend involved, no cost) on both chat pages.
- **Vision**: `POST /api/agent/chat` accepts `image_data_url` - Groq's
  current free model is text-only, so any message with an image is routed
  to Gemini instead (`app/agent/model.py:get_vision_model`), which also
  supports tool-calling, so the agent can read a photo and act on it (e.g.
  create a customer from a photographed note) in one turn.
- **Markdown formatting**: both the Assistant and Ask Your Data system
  prompts ask for markdown, and the frontend renders it properly instead of
  showing raw asterisks.
- **Postgres-backed agent memory** (`app/agent/checkpointer.py`): replaced
  `InMemorySaver` with `langgraph-checkpoint-postgres`, using the same
  Supabase database. This isn't just "nice to have" - a local-disk/SQLite
  saver would've been just as ephemeral as in-memory on a platform like
  Render's free tier, where the whole container filesystem resets on every
  restart/redeploy. Verified by running two completely separate Python
  processes against the same thread and confirming the second recalled
  what the first said.
- **Deployment**: `render.yaml` (backend, Render) and `frontend/vercel.json`
  (SPA rewrite, Vercel). `CORS_ORIGINS` must include the deployed frontend's
  URL or its API calls fail silently in the browser (not visible via
  curl/server-to-server checks - CORS is browser-enforced only).

Not yet built: WhatsApp quick-capture extraction (paste a WhatsApp message,
LLM extracts structured fields) from the original prototype, and multi-user
role management (everyone is `owner` today, fixed at signup).
