# Mini CRM backend (Phase 1)

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

## What's here (Phase 1 scope)

- Multi-tenant auth (signup creates an org + owner user, JWT login)
- Customer CRUD with dedup detection (phone/email/name matching), duplicate
  groups, merge
- Transactions per customer, auto-recomputed customer status + "already
  bought" interest cleanup
- CSV import (flexible header aliasing, auto-merges duplicates) and export
- Dashboard summary (status counts, sales by currency, monthly trend, top
  customers, interest rollup)

Not yet built (later phases): the LangChain agent/tools layer with the
confirm-before-destructive-write flow, the React frontend, WhatsApp
quick-capture extraction, and the "ask your data" chat.
