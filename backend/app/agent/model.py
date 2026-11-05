"""
Groq's free-tier daily token quota (200k TPD) kept getting exhausted under
real use, and recovering from that mid-request (building and running a
second full agent against Gemini as a fallback) was enough extra memory
pressure to OOM-kill the backend on Render's free tier. Gemini is now the
only provider - simpler, and it's held up reliably whenever it's been hit.
"""
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings

_cached_model = None


def get_model():
    global _cached_model
    if _cached_model is None:
        _cached_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=settings.google_api_key)
    return _cached_model


def reset_model_cache() -> None:
    """Used by tests, and callable if a provider starts failing mid-run."""
    global _cached_model
    _cached_model = None


def call_with_fallback(get_model_fn, invoke):
    """Retry once against a freshly-resolved model if the first invoke
    raises (e.g. a transient API error), rather than failing the request
    outright."""
    try:
        return invoke(get_model_fn())
    except Exception:
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
    """Gemini handles both text and multimodal input, so this is just an
    alias for get_model() - kept separate in case a future provider swap
    needs a different model for one but not the other."""
    return get_model()
