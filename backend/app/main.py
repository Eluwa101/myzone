from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import agent, auth, customers, settings, summary, transactions

app = FastAPI(title="Mini CRM API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(customers.router)
app.include_router(transactions.router)
app.include_router(summary.router)
app.include_router(agent.router)
app.include_router(settings.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
