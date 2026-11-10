# MyShop API

The MyShop backend is a FastAPI service for organization-scoped customer and sales management. It provides authentication, customer and transaction APIs, CSV import/export, dashboard summaries, settings, and the AI assistant endpoints used by the frontend.

Built with FastAPI, SQLAlchemy, Alembic, and PostgreSQL. Business logic lives in controllers and is shared by the REST routes and assistant tools, so both interfaces use the same application rules.

## Capabilities

- Organization signup and JWT-based login.
- Customer CRUD, duplicate detection and grouping, and customer merging.
- Customer-linked transactions and dashboard aggregates.
- CSV customer import and export.
- Per-organization WhatsApp QR settings.
- General-purpose AI assistant with supported CRM tools, persisted chat history, and tool-action audit records. Destructive operations are staged as pending actions for user confirmation.
- Read-only Ask Your Data endpoint, grounded in customer and dashboard data.
- PostgreSQL-backed conversation memory.

## Local setup

From the repository root, start PostgreSQL:

```bash
docker compose up -d
```

Then create and activate a virtual environment in `backend/`, and install dependencies:

```bash
cd backend
python -m venv .venv

# macOS / Linux
source .venv/bin/activate
pip install -r requirements.txt

# Windows PowerShell (run these instead of the activation commands above)
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `backend/.env` from `.env.example` and configure `JWT_SECRET`. The example's database URL is for the local Docker Compose database. Add `GROQ_API_KEY`, `GOOGLE_API_KEY`, or both to enable the AI features; at least one provider key is needed for assistant requests.

```bash
# macOS / Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Apply migrations and run the API:

```bash
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

API base URL: <http://localhost:8000>  
Interactive API docs: <http://localhost:8000/docs>

The default `CORS_ORIGINS` allows the local frontend at `http://localhost:5173`. Add the deployed frontend origin to this setting when deploying.

## AI behavior and safeguards

The general assistant can call tools for supported CRM operations. These tools route through the same controllers as API requests. Reversible actions can run immediately; destructive actions such as deleting or merging customers create pending actions that a user must confirm or reject. Tool results are recorded in the agent action log.

The Ask Your Data assistant is separate and read-only: it uses prepared customer and summary context to answer questions and cannot modify records. Model provider availability, limits, and data policies are controlled by the configured provider.

## Tests

The test suite uses an in-memory SQLite database and does not require PostgreSQL:

```bash
python -m pytest
```

For an end-to-end smoke test against the database configured by `DATABASE_URL` in `.env`:

```bash
python scripts/smoke_test.py
```

## Key areas

- `app/models/` — database models
- `app/schemas/` — request and response validation
- `app/controllers/` — shared business logic
- `app/routes/` — HTTP API routes
- `app/agent/` — model setup, tools, memory, and data-question functionality
- `alembic/` — database migrations
- `tests/` — automated tests

For the complete application overview and frontend setup, see the [root README](../README.md).
