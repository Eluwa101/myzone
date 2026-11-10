"""Replay-safety for offline-queued requests.

The frontend's offline outbox retries a mutating request (with a client-
generated Idempotency-Key) whenever it isn't sure the previous attempt
landed - e.g. the tab closed or reconnected mid-request. Without this, a
retried `POST /api/customers/{id}/transactions` that actually succeeded the
first time would log the same sale twice.

Only engages when the client sends the header at all, so it changes nothing
for ordinary (non-offline-queued) traffic - no caching, no behavior change,
just a header this middleware doesn't look for.
"""
import datetime
import json
import logging
from uuid import UUID

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.idempotency import IdempotencyKey

logger = logging.getLogger(__name__)

MUTATING_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
REPLAY_WINDOW = datetime.timedelta(days=7)
HEADER_NAME = "idempotency-key"


def _org_id_from_request(request: Request) -> UUID | None:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        org_id = payload.get("org_id")
        return UUID(org_id) if org_id else None
    except (JWTError, ValueError):
        return None


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        key = request.headers.get(HEADER_NAME)
        if not key or request.method not in MUTATING_METHODS:
            return await call_next(request)

        org_id = _org_id_from_request(request)
        if org_id is None:
            return await call_next(request)

        path = request.url.path
        db = SessionLocal()
        try:
            try:
                cutoff = datetime.datetime.now(datetime.timezone.utc) - REPLAY_WINDOW
                cached = (
                    db.query(IdempotencyKey)
                    .filter(
                        IdempotencyKey.org_id == org_id,
                        IdempotencyKey.key == key,
                        IdempotencyKey.method == request.method,
                        IdempotencyKey.path == path,
                        IdempotencyKey.created_at >= cutoff,
                    )
                    .first()
                )
            except Exception:  # noqa: BLE001 - a broken lookup must degrade to "not cached", never break the real request
                db.rollback()
                logger.exception("Idempotency lookup failed for org %s - proceeding without replay protection", org_id)
                cached = None

            if cached is not None:
                return Response(
                    content=cached.response_body,
                    status_code=cached.status_code,
                    media_type=cached.content_type,
                    headers={"X-Idempotent-Replay": "true"},
                )

            response = await call_next(request)
            if 200 <= response.status_code < 300:
                body_chunks = [chunk async for chunk in response.body_iterator]
                body = b"".join(body_chunks)
                try:
                    db.add(
                        IdempotencyKey(
                            org_id=org_id,
                            key=key,
                            method=request.method,
                            path=path,
                            status_code=response.status_code,
                            content_type=response.media_type,
                            response_body=body.decode("utf-8") if body else None,
                        )
                    )
                    db.commit()
                except Exception:  # noqa: BLE001 - a concurrent duplicate insert must never break the real response
                    db.rollback()
                    logger.info("Idempotency key %s for org %s could not be stored (likely a concurrent retry)", key, org_id)
                return Response(content=body, status_code=response.status_code, media_type=response.media_type, headers=dict(response.headers))
            return response
        finally:
            db.close()
