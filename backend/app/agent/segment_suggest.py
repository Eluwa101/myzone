"""
Turns a plain-English description of a customer group into SegmentFilters -
a single grounded LLM call, no tools, no writes, same lightweight pattern as
ask_data.py. Kept separate from the general-purpose agent in runner.py,
which can take actions and isn't meant to also do structured extraction.
"""
import json
from datetime import date

from app.agent.model import call_with_fallback, extract_text, get_model
from app.schemas.segment import SegmentFilters

SYSTEM_PROMPT = """You turn a plain-English description of a group of customers into a JSON filter \
object for a CRM's segment builder. Reply with ONLY a single JSON object - no prose, no markdown \
code fences - matching this shape exactly (every key optional; omit any you don't need):
{{"status": "lead" | "customer" | "inactive", "interest_contains": string, "has_consent": true | \
false, "search": string, "last_purchase_within_days": integer, "last_purchase_over_days": integer, \
"min_transactions": integer}}

Guidance: "search" matches a name/phone/email substring - use it only for a specific name or \
contact fragment the user gave, never for a general description. "interest_contains" matches the \
free-text "interested in" field. Use last_purchase_within_days for "bought recently / in the last \
N days", and last_purchase_over_days for "haven't bought in N days / churned / win-back targeting" \
- these are mutually exclusive, never set both. If the user gives no clear number of days, leave \
both out rather than guessing one. min_transactions must be 1 or more - there is no filter for \
exactly zero purchases, so for "never bought / no purchases yet" leave min_transactions out \
entirely (status "lead" is usually the better fit for that intent). Today is {today}."""


class SegmentSuggestionError(Exception):
    pass


def suggest_segment_filters(description: str) -> SegmentFilters:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(today=date.today().isoformat())},
        {"role": "user", "content": description},
    ]
    result = call_with_fallback(get_model, lambda model: model.invoke(messages))
    text = extract_text(result.content).strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object.")
        return SegmentFilters(**{k: v for k, v in data.items() if v is not None})
    except (ValueError, TypeError) as e:
        raise SegmentSuggestionError(str(e)) from e
