"""
Three-tier fallback: Groq first (fast, free, generous per-minute limits),
then OpenRouter's free-model router, then Gemini as the final safety net
(no cooldown, no ping check - it's the one provider that must always just
work). Groq's 200k/day token quota and OpenRouter's free-model daily request
cap can each run out under real use - recovering from that mid-request
(building and running a second full agent against the next provider) is a
real memory spike on Render's 512MB free tier, so once a provider fails
it's put on a cooldown instead of being re-attempted (and re-failing) on
every subsequent request. Only the first request after an exhaustion pays
the extra build cost.
"""
import time

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from app.core.config import settings

COOLDOWN_SECONDS = 15 * 60

_cached_model = None
_cached_provider: str | None = None
_cooldowns = {"groq": 0.0, "openrouter": 0.0}


def _groq():
    # groq retired the llama-3.3 models; openai/gpt-oss-120b is current as
    # of this writing - check console.groq.com/docs/models if this starts
    # 404ing again.
    return ChatGroq(model="openai/gpt-oss-120b", api_key=settings.groq_api_key)


def _openrouter():
    # openrouter/free randomly routes across whichever free models are
    # currently up, so a single model being retired/overloaded doesn't take
    # this provider down the way a hardcoded model id would.
    return ChatOpenAI(model="openrouter/free", api_key=settings.open_router_api_key, base_url="https://openrouter.ai/api/v1")


def _gemini():
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=settings.google_api_key)


def get_model():
    global _cached_model, _cached_provider
    if _cached_model is not None:
        return _cached_model

    now = time.monotonic()
    for name, build in (("groq", _groq), ("openrouter", _openrouter)):
        if now < _cooldowns[name]:
            continue
        try:
            model = build()
            model.invoke("ping")
            _cached_model, _cached_provider = model, name
            return _cached_model
        except Exception:
            _cooldowns[name] = now + COOLDOWN_SECONDS

    _cached_model, _cached_provider = _gemini(), "gemini"
    return _cached_model


def reset_model_cache() -> None:
    """Used by tests, and callable if a provider starts failing mid-run."""
    global _cached_model, _cached_provider
    _cached_model = None
    _cached_provider = None


def call_with_fallback(get_model_fn, invoke):
    """Retry once against a freshly-resolved model if the first invoke
    raises. This is what actually catches a provider's quota running out
    mid-run - get_model()'s cheap "ping" check only catches it being down
    at the moment the model is first resolved - and it's also where the
    cooldown gets armed so later requests skip straight past it."""
    try:
        return invoke(get_model_fn())
    except Exception:
        if _cached_provider in _cooldowns:
            _cooldowns[_cached_provider] = time.monotonic() + COOLDOWN_SECONDS
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
