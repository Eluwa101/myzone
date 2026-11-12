"""API keys: generating, hashing and looking them up.

A key looks like `msk_live_` + 40 random url-safe characters. It's
compared by SHA-256 hash (fast, and fine for a high-entropy random secret
- bcrypt is for low-entropy passwords), so the database never holds a
usable key."""
import datetime
import hashlib
import secrets

from sqlalchemy.orm import Session

from app.models.api_key import ApiKey

KEY_PREFIX = "msk_live_"
_LAST_USED_RESOLUTION = datetime.timedelta(minutes=5)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_key() -> tuple[str, str, str]:
    """(the key to show once, its display prefix, its hash to store)"""
    key = KEY_PREFIX + secrets.token_urlsafe(30)
    return key, key[: len(KEY_PREFIX) + 4], hash_key(key)


def is_api_key(token: str | None) -> bool:
    return bool(token) and token.startswith(KEY_PREFIX)


def find_active_key(db: Session, key: str) -> ApiKey | None:
    if not is_api_key(key):
        return None
    return db.query(ApiKey).filter(ApiKey.key_hash == hash_key(key), ApiKey.revoked_at.is_(None)).first()


def touch(db: Session, api_key: ApiKey) -> None:
    """Record use, at most every few minutes - not a write per request."""
    now = datetime.datetime.now(datetime.timezone.utc)
    last = api_key.last_used_at
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=datetime.timezone.utc)
    if last is None or now - last > _LAST_USED_RESOLUTION:
        api_key.last_used_at = now
        db.commit()
