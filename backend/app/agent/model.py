"""
Same fallback pattern as src/agent.py: try groq first (fast, free), fall
back to gemini if groq is down or rate-limited. Cached after the first
successful resolution so we're not pinging a provider on every chat turn.
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from app.core.config import settings

_cached_model = None


def get_model():
    global _cached_model
    if _cached_model is not None:
        return _cached_model

    try:
        model = ChatGroq(model="llama-3.3-70b-versatile", api_key=settings.groq_api_key)
        model.invoke("ping")
        _cached_model = model
    except Exception:
        _cached_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=settings.google_api_key)
    return _cached_model


def reset_model_cache() -> None:
    """Used by tests, and callable if a provider starts failing mid-run."""
    global _cached_model
    _cached_model = None
