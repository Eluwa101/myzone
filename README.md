# MyShop

**Customer relationships and sales activity, in one simple workspace.**

MyShop is a multi-tenant CRM for small businesses that want to keep customer records organized, track purchases, and understand their sales activity without juggling spreadsheets. A web dashboard and AI assistant provide two ways to work with the same customer data.

## What you can do

- **Keep customer records tidy.** Create and update customer profiles, find likely duplicates using contact details, review duplicate groups, and merge records.
- **Track customer purchases.** Record transactions against customers and use the dashboard to review sales and customer activity.
- **See useful business summaries.** View customer status counts, sales by currency, monthly trends, top customers, and interest summaries.
- **Move data in and out.** Import customer data from CSV with flexible header matching and export records for use elsewhere.
- **Get help from AI.** Ask the assistant to answer questions or perform supported CRM tasks. Routine supported actions can be applied directly; destructive actions such as deleting or merging records require explicit confirmation.
- **Ask questions without changing data.** The separate Ask Your Data experience answers questions using CRM data and is read-only.
- **Pick up conversations later.** Assistant conversation history is persisted in PostgreSQL. Voice input is available through supported browsers, and the general assistant can accept images using a configured vision-capable model.
- **Share contact details.** Configure business details and a WhatsApp message template, then generate a QR code in the web app.

## Designed for focused CRM work

MyShop focuses on customer relationship management and basic sales tracking. It does **not** process payments and is not an accounting, inventory, or full marketing-automation system. Transactions are records for tracking business activity, not payment events.

Organizations are separated, but role-based access levels are not implemented yet; new users currently receive the owner role. WhatsApp quick-capture extraction is also not currently available. AI capabilities depend on the selected provider and its current availability, terms, and data policies. The core CRM can run without AI provider keys.

## Technology

- **Web app:** React, TypeScript, Vite
- **API:** Python, FastAPI, SQLAlchemy, Alembic
- **Database:** PostgreSQL
- **AI features:** LangChain/LangGraph, with Groq and Google Gemini support
- **Deployment configuration:** Render (API) and Vercel (frontend)

## Run locally

### Requirements

- Python version listed in `backend/.python-version`
- Node.js and npm
- Docker with Docker Compose
- A Groq or Google Gemini API key to use AI features (optional for core CRM functionality)

### 1. Start the database

From the repository root:

```bash
docker compose up -d
```

### 2. Configure and run the API

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment and install dependencies:

```bash
# macOS / Linux
source .venv/bin/activate
pip install -r requirements.txt

# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `backend/.env` from the example. Set a strong `JWT_SECRET`; add at least one model API key if you want to use AI features.

```bash
# macOS / Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Apply migrations and start the development server:

```bash
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

The API is at <http://localhost:8000>. Interactive API documentation is at <http://localhost:8000/docs>.

### 3. Run the web app

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the local address printed by Vite. Make sure the API's `CORS_ORIGINS` includes that frontend origin; the example configuration allows `http://localhost:5173`.

For deployment, configure the backend environment using `backend/.env.example`, including a production database URL, a strong JWT secret, allowed frontend origins, and any model provider keys. Deployment configuration is in `render.yaml` and `frontend/vercel.json`.

## Tests

Backend tests use an in-memory SQLite database, so they do not require the local PostgreSQL service:

```bash
cd backend
python -m pip install -r requirements.txt
python -m pytest
```

To run the smoke test against the database configured in `backend/.env`:

```bash
cd backend
python scripts/smoke_test.py
```

## Project structure

```text
backend/   FastAPI API, database models, business logic, AI features, and tests
frontend/  React web application
src/       Standalone AI-agent learning examples
```

The `src/` scripts are educational examples, separate from the MyShop product. The product's CRM and assistant functionality is implemented in `backend/` and `frontend/`.

## More information

- [Backend guide](backend/README.md)
- [Frontend guide](frontend/README.md)
- [Backend environment example](backend/.env.example)

---

Built by [@exploraX_](https://x.com/exploraX_).
