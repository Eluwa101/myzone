"""Shared optional paging for list endpoints.

The list endpoints are part of the public API and return plain JSON arrays,
so paging is opt-in and non-breaking: without ``page`` every matching row is
returned exactly as before; with it, that slice. Either way the total number
of matching rows (before slicing) is sent in the ``X-Total-Count`` header.
"""

from fastapi import Response
from sqlalchemy import JSON, Text, func, or_
from sqlalchemy.orm import Query

MAX_PAGE_SIZE = 200
TOTAL_HEADER = "X-Total-Count"
ESCAPE = chr(92)  # backslash, the LIKE escape character


def like_pattern(search: str | None) -> str | None:
    """Lower-cased %term% for a case-insensitive contains match, or None when blank."""
    term = (search or "").strip().lower()
    if not term:
        return None
    escaped = term.replace(ESCAPE, ESCAPE * 2).replace("%", ESCAPE + "%").replace("_", ESCAPE + "_")
    return f"%{escaped}%"


def contains_any(pattern: str, *columns):
    """OR of case-insensitive LIKE across columns; JSON columns are cast to text."""
    clauses = []
    for col in columns:
        expr = col.cast(Text) if isinstance(col.type, JSON) else col
        clauses.append(func.lower(func.coalesce(expr, "")).like(pattern, escape="\\"))
    return or_(*clauses)


def paginate(query: Query, response: Response, page: int | None, page_size: int = 20, limit: int | None = None) -> list:
    """Run an already filtered + deterministically ordered query.

    ``limit`` (only used when ``page`` is omitted) preserves an endpoint's
    older "most recent N" behaviour. Always sets X-Total-Count to the number
    of matching rows before any slicing.
    """
    total = query.order_by(None).count()
    response.headers[TOTAL_HEADER] = str(total)
    if page is None:
        return (query.limit(limit) if limit else query).all()
    size = min(max(1, page_size), MAX_PAGE_SIZE)
    return query.offset((max(1, page) - 1) * size).limit(size).all()
