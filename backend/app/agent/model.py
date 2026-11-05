"""
Groq first (fast, free, generous per-minute limits), Gemini as fallback.
Groq's 200k/day token quota can still run out under real use - recovering
from that mid-request (building and running a second full agent against
Gemini) is a real memory spike on Render's 512MB free tier, so once that
happens we put Groq on a cooldown instead of re-attempting (and re-failing)
it on every subsequent request for the rest of the day. Only the first
request after a quota exhaustion pays the double-build cost.
"""
import time

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from app.core.config import settings

GROQ_COOLDOWN_SECONDS = 15 * 60

_cached_model = None
_groq_retry_at = 0.0


def _gemini():
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=settings.google_api_key)


def _start_groq_cooldown() -> None:
    global _groq_retry_at
    _groq_retry_at = time.monotonic() + GROQ_COOLDOWN_SECONDS


def get_model():
    global _cached_model
    if _cached_model is not None:
        return _cached_model

    if time.monotonic() < _groq_retry_at:
        _cached_model = _gemini()
        return _cached_model

    try:
        # groq retired the llama-3.3 models; openai/gpt-oss-120b is current
        # as of this writing - check console.groq.com/docs/models if this
        # starts 404ing again.
        model = ChatGroq(model="openai/gpt-oss-120b", api_key=settings.groq_api_key)
        model.invoke("ping")
        _cached_model = model
    except Exception:
        _start_groq_cooldown()
        _cached_model = _gemini()
    return _cached_model


def reset_model_cache() -> None:
    """Used by tests, and callable if a provider starts failing mid-run."""
    global _cached_model
    _cached_model = None


def call_with_fallback(get_model_fn, invoke):
    """Retry once against a freshly-resolved model if the first invoke
    raises. This is what actually catches Groq's quota running out mid-run
    - get_model()'s cheap "ping" check only catches it being down at the
    moment the model is first resolved - and it's also where the cooldown
    gets armed so later requests skip straight to Gemini."""
    try:
        return invoke(get_model_fn())
    except Exception:
        _start_groq_cooldown()
        reset_model_cache()
        return invoke(get_model_fn())


def extract_text(content) -> str:
    """Most models return a plain string for .content, but Gemini (and other
    multimodal-capable models) can return a list of content blocks instead -
    e.g. [{"type": "text", "text": "..."}] - even for a text-only reply."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content) if content else ""


def get_vision_model():
    """Groq's model is text-only, so any message that includes an image is
    always routed to Gemini instead, which supports both multimodal input
    and tool-calling - the agent can read a photo and act on it (e.g.
    create a customer from it) in one turn."""
    return _gemini()
