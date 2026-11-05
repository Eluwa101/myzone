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
        # groq retired the llama-3.3 models; openai/gpt-oss-120b is current
        # as of this writing - check https://console.groq.com/docs/models if
        # this starts 404ing again.
        model = ChatGroq(model="openai/gpt-oss-120b", api_key=settings.groq_api_key)
        model.invoke("ping")
        _cached_model = model
    except Exception:
        _cached_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=settings.google_api_key)
    return _cached_model


def reset_model_cache() -> None:
    """Used by tests, and callable if a provider starts failing mid-run."""
    global _cached_model
    _cached_model = None


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
    """
    Groq's current free model (openai/gpt-oss-120b) is text-only, so any
    message that includes an image is always routed to Gemini instead,
    which supports both multimodal input and tool-calling - the agent can
    read a photo and act on it (e.g. create a customer from it) in one turn.
    """
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=settings.google_api_key)
