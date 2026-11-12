"""Writes (or rewrites) an email - subject and HTML body - from a plain
description, slotting in merge tags (single values, #each lists, #if
conditions, totals) where the description calls for customer data.

One LLM call; the draft's tags are then checked with the same checker the
Preview button uses, and if any don't resolve the model gets one chance
to fix them. Whatever problems remain are returned alongside the draft so
the user sees them, rather than silently sending broken tags."""
import json
import re
from typing import Callable

from app.agent.model import call_with_fallback, extract_text, get_model
from app.core.merge_tags import MERGE_TAG_GUIDE


class EmailDraftError(Exception):
    pass


_FORMATS = {
    "simple": """body_html is simple rich text for a visual editor: only <p>, <strong>, <em>, <u>, <ul>/<ol>/<li>, <a href>, <br>.
No tables, no style attributes, no <div>. Put every {{#each ...}}, {{else}}, {{/each}}, {{#if ...}} and {{/if}} on a line of its own,
i.e. in its own <p>...</p>, and each list row's content in one <p>.""",
    "designed": """body_html is a complete, designed HTML email that works in Gmail and Outlook:
- layout with nested <table role="presentation" cellpadding="0" cellspacing="0"> - an outer 100%-wide table with a light
  background, and a centred inner table with width="100%" and style="max-width:600px" (never a fixed width - it must
  shrink on phones) with a white background; inner data tables are width="100%" too
- inline style="..." attributes only - no <style> block, no classes, no external CSS, no scripts
- a coloured header row using the brand colour, a body row, and a small muted footer row with the business name
- show #each lists as table rows: put {{#each ...}} right after a <tr> header row and before the row <tr>, and {{/each}} after it
- fonts: Arial, Helvetica, sans-serif""",
}


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse(text: str) -> dict:
    text = _strip_fences(text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise EmailDraftError("no JSON object in the reply")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise EmailDraftError(str(e)) from e
    subject, body = data.get("subject"), data.get("body_html")
    if not isinstance(subject, str) or not isinstance(body, str) or not body.strip():
        raise EmailDraftError("reply is missing subject or body_html")
    # an email has no use for scripts, and the preview never runs them anyway
    body = re.sub(r"<script\b.*?</script\s*>", "", body, flags=re.IGNORECASE | re.DOTALL)
    if "\n" not in body.strip():
        # models sometimes return the whole design on one line - break it at
        # block-level tags and block tags so it's editable in the HTML view
        body = re.sub(r"(<(?:/?table|/?tr|td|th|p|h[1-6]|ul|ol|li)\b|\{\{\s*(?:#each|#if|else|/each|/if)\b)", r"\n\1", body)
    return {"subject": subject.strip(), "body_html": body.strip()}


def draft_email(
    *,
    description: str,
    fmt: str,
    tags_text: str,
    business_text: str,
    segment_text: str | None,
    suggested_text: str | None,
    current_subject: str | None,
    current_body: str | None,
    check: Callable[[str, str], list[str]],
) -> dict:
    system = f"""You write marketing and customer-care emails for a small business, with merge tags that are filled in per customer.

{business_text}

{MERGE_TAG_GUIDE}

Single-value tags available to this business (use exactly these, nothing else):
{tags_text}
""" + (f"\nThe email goes to this customer segment:\n{segment_text}\n" if segment_text else "") + (
        f"\nTags that fit this segment especially well:\n{suggested_text}\n" if suggested_text else ""
    ) + f"""
Format:
{_FORMATS.get(fmt, _FORMATS["simple"])}

Rules:
- Use merge tags wherever the request refers to customer data (names, purchases, items, dates, totals, conditions) - never write
  example data in their place.
- Never invent facts the user didn't give (prices, discounts, deadlines, links, phone numbers). Leave a clear placeholder like
  [discount] or [link] instead.
- Give lists an {{{{else}}}} fallback when an empty list would read oddly.
- Keep it short, warm and in plain language unless asked otherwise. The subject may use single-value tags but not lists or #if.
- Reply with ONLY a JSON object: {{"subject": "...", "body_html": "..."}}"""

    if current_body and current_body.strip():
        user = f"""Current subject: {current_subject or ""}
Current body_html:
{current_body}

Change the email as follows, keeping everything that isn't asked to change: {description}"""
    else:
        user = f"Write this email: {description}"

    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    draft: dict | None = None
    problems: list[str] = []
    for attempt in range(2):
        result = call_with_fallback(get_model, lambda model: model.invoke(messages))
        raw = extract_text(result.content)
        try:
            draft = _parse(raw)
        except EmailDraftError:
            if attempt == 1 or draft is not None:
                break
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": 'That wasn\'t valid JSON. Reply with only {"subject": "...", "body_html": "..."}.'},
            ]
            continue
        problems = check(draft["subject"], draft["body_html"])
        if not problems or attempt == 1:
            break
        messages += [
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": "Some merge tags won't work:\n- " + "\n- ".join(problems) + "\nFix them and reply with the full JSON again.",
            },
        ]
    if draft is None:
        raise EmailDraftError("the model didn't return a usable draft")
    return {**draft, "problems": problems}
