# MyShop

MyShop is a lightweight, multi-tenant customer and sales management app for small businesses. It brings customer records, purchase history, sales summaries, and an AI assistant together in one web application.

The app is designed to help a business keep customer information organized, understand sales activity, and complete common CRM tasks through either the web interface or a conversational assistant. It is built as a full-stack project with a React frontend, a FastAPI backend, and PostgreSQL for persistent data.

## What the app does

- **Manage customers:** create, view, update, and delete customer records; detect likely duplicates; review duplicate groups; and merge records.
- **Track transactions:** associate purchases with customers and keep customer status and interest information up to date.
- **Import and export customer data:** upload CSV files with flexible column headers, automatically reconcile duplicates during import, and export records.
- **Review business activity:** use the dashboard for customer-status counts, sales totals by currency, monthly trends, top customers, and interest summaries.
- **Use an AI assistant:** chat with an assistant that can answer questions and perform supported CRM actions using the same business logic as the web app. Reversible actions can run directly; destructive actions such as deleting or merging customers require confirmation.
- **Ask questions about CRM data:** use a separate read-only assistant to ask questions grounded in your customer and sales data. This assistant cannot modify records.
- **Keep conversations:** assistant threads and messages are stored in PostgreSQL and can be reopened later.
- **Use voice and images:** the chat interfaces support browser speech recognition where available. The general assistant can also accept an image; image requests use the configured vision-capable provider.
- **Configure WhatsApp contact sharing:** save organization-specific business details and generate a WhatsApp QR code in the frontend.

## Scope and limitations

MyShop currently focuses on customer relationship management and basic sales tracking. It is not a payment processor, accounting system, inventory manager, or full marketing automation platform. Transactions are customer-linked records for tracking business activity; the app does not process payments.

Organizations are separated in the application, but role-based permissions are not yet implemented: users currently receive the owner role at signup. WhatsApp quick-capture extraction is also not yet built. AI features require a configured model provider and may be subject to that provider's availability, pricing, and data policies.

## Technology

- **Frontend:** React, TypeScript, Vite
- **Backend:** Python, FastAPI, SQLAlchemy, Alembic
- **Database:** PostgreSQL
- **AI:** LangChain/LangGraph, with Groq and Google Gemini provider support
- **Deployment configuration:** Render for the backend and Vercel for the frontend

## Run locally

### Prerequisites

- Python version specified in `backend/.python-version`
- Node.js and npm
- Docker and Docker Compose
- API key for Groq or Google Gemini if you want to use AI features

### 1. Start PostgreSQL

From the repository root:

```bash
docker compose up -d
```

This starts the local PostgreSQL database used by the backend.

### 2. Configure and run the backend

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment, then install dependencies:

```bash
# macOS / Linux
source .venv/bin/activate
pip install -r requirements.txt

# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `backend/.env` from the example and set a secure `JWT_SECRET`. Add at least one model key to enable the AI features; the CRM API can be used without AI keys.

```bash
# macOS / Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Apply database migrations and start the API:

```bash
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

The API will be available at <http://localhost:8000>; interactive API documentation is at <http://localhost:8000/docs>.

### 3. Run the frontend

In a separate terminal, install frontend dependencies and start the development server:

```bash
cd frontend
npm install
npm run dev
```

Use the local URL printed by Vite. The backend's `CORS_ORIGINS` setting must include the frontend origin; the default backend example allows `http://localhost:5173`.

For deployment, configure the backend environment variables from `backend/.env.example`, including the production database URL, a strong JWT secret, allowed frontend origins, and any AI provider keys you intend to use. See `render.yaml` and `frontend/vercel.json` for the deployment configuration.

## Tests

Backend tests use an in-memory SQLite database and do not require the local PostgreSQL service:

```bash
cd backend
python -m pip install -r requirements.txt
python -m pytest
```

To run the backend smoke test against the database configured in `backend/.env`:

```bash
cd backend
python scripts/smoke_test.py
```

## Repository layout

```text
backend/   FastAPI API, database models, business logic, AI assistant, and tests
frontend/  React web application
src/       Standalone AI-agent learning examples
```

The scripts under `src/` are educational examples and are separate from the MyShop product backend. The app's production CRM and assistant functionality lives in `backend/` and `frontend/`.

## More details

- [Backend setup and implementation notes](backend/README.md)
- [Frontend](frontend/)
- [Environment variable example](backend/.env.example)

---

*Built by [@exploraX_](https://x.com/exploraX_)*
