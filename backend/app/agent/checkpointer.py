"""
Postgres-backed conversation memory for the agent, replacing InMemorySaver.
Unlike in-process memory (and unlike a local-disk SQLite file, which would
be just as ephemeral on a platform like Render's free tier, where the whole
container filesystem resets on every restart/redeploy), this survives
restarts because it lives in the same Supabase Postgres database as
everything else.

Built lazily (not at import time) and cached, so importing this module -
which happens whenever app.agent.runner is imported, i.e. on every test
run - never opens a real database connection on its own. Only calling
get_checkpointer() does.
"""
from urllib.parse import quote

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

from app.core.config import settings

_checkpointer: PostgresSaver | None = None

_RLS_TABLES = ["checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"]


def _to_psycopg_conninfo(database_url: str) -> str:
    """SQLAlchemy's URL parser tolerates unescaped special characters (like
    '/') in the password; psycopg's own URI parser does not (it broke on
    exactly this with our real Supabase password). Build the connection
    string from the already-correctly-parsed components instead of
    string-replacing the SQLAlchemy URL directly."""
    from sqlalchemy.engine.url import make_url

    url = make_url(database_url)
    return f"postgresql://{quote(url.username, safe='')}:{quote(url.password, safe='')}@{url.host}:{url.port}/{url.database}"


def _lock_down_rls(pool: ConnectionPool) -> None:
    # Same reasoning as the Alembic RLS migrations for our own tables:
    # Supabase's Data API would otherwise expose these via anon/authenticated.
    # langgraph owns this schema (created via .setup()), so this runs here
    # instead of as an Alembic migration.
    with pool.connection() as conn:
        for table in _RLS_TABLES:
            conn.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def get_checkpointer() -> PostgresSaver:
    global _checkpointer
    if _checkpointer is None:
        pool = ConnectionPool(
            conninfo=_to_psycopg_conninfo(settings.database_url),
            min_size=1,
            max_size=5,
            kwargs={"autocommit": True, "row_factory": psycopg.rows.dict_row},
            # Same reasoning as pool_pre_ping on the main SQLAlchemy engine:
            # Supabase's pooler closes idle connections server-side, and
            # without this a pooled connection that went stale between chat
            # requests fails with "server closed the connection
            # unexpectedly" instead of being silently replaced.
            check=ConnectionPool.check_connection,
        )
        saver = PostgresSaver(pool)
        saver.setup()
        _lock_down_rls(pool)
        _checkpointer = saver
    return _checkpointer


def close_checkpointer() -> None:
    """Call on app shutdown so the pool's worker threads stop cleanly."""
    global _checkpointer
    if _checkpointer is not None:
        _checkpointer.conn.close()
        _checkpointer = None
