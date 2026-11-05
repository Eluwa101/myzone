"""Lightweight in-memory rate limiter for the public form-submission
endpoint. Per-process only (resets on deploy/restart) - an abuse guard, not
a hard security boundary, which is an acceptable tradeoff at this scale."""
import time
from collections import defaultdict

_WINDOW_SECONDS = 600.0
_MAX_REQUESTS = 30

_hits: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(key: str) -> bool:
    """Returns True if the request is allowed, False if `key` has already
    hit the limit within the current window."""
    now = time.monotonic()
    hits = _hits[key]
    cutoff = now - _WINDOW_SECONDS
    while hits and hits[0] < cutoff:
        hits.pop(0)
    if len(hits) >= _MAX_REQUESTS:
        return False
    hits.append(now)
    return True
