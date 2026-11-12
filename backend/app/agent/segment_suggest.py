"""
Turns a plain-English description of a customer group into a SegmentFilters
condition tree - a single grounded LLM call, no tools, no writes, same
lightweight pattern as ask_data.py. Kept separate from the general-purpose
agent in runner.py, which can take actions and isn't meant to also do
structured extraction.
"""
import json
from datetime import date

from app.agent.model import call_with_fallback, extract_text, get_model
from app.controllers.segment_fields import FIELD_REGISTRY, OPERATORS_BY_TYPE
from app.schemas.segment import SegmentFilters

SCHEMA_EXAMPLE = {
    "type": "group",
    "combinator": "or",
    "conditions": [
        {"type": "condition", "field": "status", "operator": "equals", "value": "lead"},
        {
            "type": "group",
            "combinator": "and",
            "conditions": [
                {"type": "condition", "field": "interests", "operator": "contains", "value": "generator"},
                {"type": "condition", "field": "last_purchase_date", "operator": "over_days_ago", "value": 60},
            ],
        },
    ],
}


def _field_catalog() -> str:
    lines = [f'- "{f.key}" ({f.type}){" - choices: " + ", ".join(f.choices) if f.choices else ""}' for f in FIELD_REGISTRY.values()]
    lines.append('- "extra.<key>" (text) - one of the org\'s own custom fields, e.g. "extra.Car"')
    return "\n".join(lines)


def _operator_catalog() -> str:
    return "\n".join(f"- {ftype}: {', '.join(ops)}" for ftype, ops in OPERATORS_BY_TYPE.items())


def _build_system_prompt() -> str:
    # Built fresh per call (not a module-level constant) so "today" stays
    # accurate for a long-running server process, not frozen at import time.
    return f"""You turn a plain-English description of a group of customers into a JSON \
condition tree for a CRM's segment builder. Reply with ONLY a single JSON object - no prose, no \
markdown code fences.

Shape: a node is either a condition or a group.
Condition: {{"type": "condition", "field": <field key>, "operator": <operator>, "value": <...>, \
"value2": <...>, "values": [...]}} - only include value/value2/values as the operator needs them:
most operators use "value", "between" also uses "value2" as the upper bound, "in_list"/"not_in_list" \
use "values" (a list of strings).
Group: {{"type": "group", "combinator": "and" | "or" | "nor", "conditions": [<node>, ...]}} - "nor" \
means none of the conditions may match. Groups can nest inside a group's "conditions" list to express \
"(A and B) or (C and not D)"-style logic. The top-level response is always a group.

Available fields:
{_field_catalog()}

Available operators by field type:
{_operator_catalog()}

Dates (birthday, consent_date, created_at, last_purchase_date, first_purchase_date, last_order_date) \
use YYYY-MM-DD strings for "equals"/"greater_than"/"less_than"/"between", or a plain integer number \
of days for "within_last_days"/"over_days_ago" - e.g. "hasn't bought in 60 days" is field \
"last_purchase_date", operator "over_days_ago", value 60. A customer who has never purchased or \
never ordered automatically counts as matching "over_days_ago" on last_purchase_date/last_order_date \
(win-back targeting should catch people who've never bought, not just people who stopped). Boolean \
fields (has_unpaid_order, has_undelivered_order) use operator "equals" with value true or false. For \
"never bought anything", use field "transaction_count", operator "equals", value 0 (or status \
"equals" "lead" if that fits the intent better).

Example - "leads, or people interested in generators who haven't bought in 60 days":
{json.dumps(SCHEMA_EXAMPLE)}

Today is {date.today().isoformat()}."""


class SegmentSuggestionError(Exception):
    pass


def suggest_segment_filters(description: str) -> SegmentFilters:
    messages = [
        {"role": "system", "content": _build_system_prompt()},
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
        data.setdefault("type", "group")
        return SegmentFilters.model_validate(data)
    except (ValueError, TypeError) as e:
        raise SegmentSuggestionError(str(e)) from e


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("sql"):
            text = text[3:]
    return text.strip()


def suggest_segment_sql(description: str, schema_text: str, current_sql: str | None = None) -> str:
    """Writes (or edits) a SQLite SELECT for a custom SQL segment. The
    result is validated the same way a hand-written query is, so the
    assistant can't produce anything a user couldn't type themselves."""
    from app.controllers.segment_sql import SegmentSQLError, validate_sql

    system = f"""You write one SQLite SELECT query that finds the customers for a marketing segment.

Tables (one business's data only; dates are 'YYYY-MM-DD' text; yes/no flags are 1/0):
{schema_text}

Rules:
- Reply with ONLY the SQL - no explanation, no markdown.
- The query must return customer ids, e.g. SELECT c.id FROM customers c ...
- One statement, SELECT only (WITH ... SELECT is fine). Use only the tables and columns above.
- Match text case-insensitively: LOWER(col) LIKE '%word%'.
- Relative dates: date('now', '-30 days'). Today is {date.today().isoformat()}.
- "Never bought X" means NOT EXISTS / NOT IN over transaction_items, so customers with no purchases are included."""
    user = description if not current_sql else f"Current query:\n{current_sql}\n\nChange it so that: {description}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    result = call_with_fallback(get_model, lambda model: model.invoke(messages))
    try:
        return validate_sql(_strip_fences(extract_text(result.content)))
    except SegmentSQLError as e:
        raise SegmentSuggestionError(str(e)) from e
