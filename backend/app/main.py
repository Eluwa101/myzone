from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.checkpointer import close_checkpointer
from app.core.config import settings as app_settings
from app.routes import agent, auth, customers, settings, summary, transactions


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_checkpointer()


app = FastAPI(title="Mini CRM API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origin_list,
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
