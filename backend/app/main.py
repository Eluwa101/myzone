import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agent.checkpointer import close_checkpointer
from app.core.config import settings as app_settings
from app.core.idempotency import IdempotencyMiddleware
from app.routes import agent, auth, customers, forms, notes, notifications, orders, public_forms, saved_widgets, segments, settings, summary, transactions, webhooks

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_checkpointer()


app = FastAPI(title="MyShop API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(IdempotencyMiddleware)

app.include_router(auth.router)
app.include_router(customers.router)
app.include_router(transactions.router)
app.include_router(orders.router)
app.include_router(orders.all_orders_router)
app.include_router(notes.router)
app.include_router(notifications.router)
app.include_router(saved_widgets.router)
app.include_router(forms.router)
app.include_router(public_forms.router)
app.include_router(segments.router)
app.include_router(summary.router)
app.include_router(agent.router)
app.include_router(settings.router)
app.include_router(webhooks.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # An uncaught exception otherwise crashes straight to Starlette's default
    # error response, which is built outside CORSMiddleware and so carries no
    # CORS headers - the browser can't even read the 500 and reports it as a
    # bare network failure ("Failed to fetch") instead of a real error.
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong. Please try again."})


@app.get("/api/health")
def health():
    return {"status": "ok"}
