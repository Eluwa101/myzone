"""
Trim, reformat or rewrite a message that is already written - for email or WhatsApp -
without losing what must not be lost.

Used by the composer's "Improve" menu and by the chat assistant's rewrite_message tool.

What makes this safe to hand to a model:

- Merge tags ({{customer.first_name}}, {{#each ...}}...{{/each}}, {{#if ...}}...{{/if}}) are
  filled in per customer at send time. With keep_merge_tags on (the default) every tag in the
  input must come back unchanged and no new tag may appear. That is CHECKED HERE, in code - the
  prompt asking nicely is not the guarantee. A reply that breaks it gets one retry with the
  specific problem named; if it still breaks it, the ORIGINAL text comes back with a warning
  rather than a damaged message.
- Links and [placeholders] that were in the text are kept too (dropping a link or a blank the
  person meant to fill is a silent loss).
- With keep_merge_tags off the model may reword around or drop tags, but anything it leaves in
  must still be a valid tag - the same checker the Preview button uses.
- It never invents facts; "improve" is wording, structure and length, not new claims.
"""
import html
import json
import re
from typing import Callable

from app.agent.email_draft import _strip_fences
from app.agent.model import call_with_fallback, extract_text, get_model
from app.core.merge_tags import find_placeholders

ACTIONS = ("shorten", "reformat", "friendlier", "rewrite")
CHANNELS = ("email", "whatsapp")


class RewriteError(Exception):
    pass


_TAG = re.compile(r"\{\{[\s\S]*?\}\}")
_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_CUSTOM_HTML = re.compile(r"<(table|style|div|section|center|font)\b", re.IGNORECASE)


def _norm_tag(tag: str) -> str:
    """{{ customer.first_name }} and {{customer.first_name}} are the same tag."""
    inner = tag[2:-2].strip()
    return "{{" + re.sub(r"\s+", " ", inner) + "}}"


def extract_tags(text: str) -> list[str]:
    return [_norm_tag(t) for t in _TAG.findall(text or "")]


def extract_urls(text: str) -> set[str]:
    return {u.rstrip(".,;:!?") for u in _URL.findall(html.unescape(text or ""))}


def html_to_plain(text: str) -> str:
    """For a WhatsApp reply that came back with HTML in it despite being told not to."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|li|tr|h[1-6])>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+\n", "\n", text)).strip()


def _sanitize(channel: str, subject: str | None, body: str) -> tuple[str | None, str]:
    if channel == "whatsapp":
        if re.search(r"<[a-z][^>]*>", body, re.IGNORECASE):
            body = html_to_plain(body)
        return None, body.strip()
    body = re.sub(r"<script\b.*?</script\s*>", "", body, flags=re.IGNORECASE | re.DOTALL)
    return (subject or "").strip(), body.strip()


def _parse(channel: str, raw: str) -> tuple[str | None, str]:
    text = _strip_fences(raw)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise RewriteError("no JSON object in the reply")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise RewriteError(str(e)) from e
    if channel == "whatsapp":
        body = data.get("text")
        if not isinstance(body, str) or not body.strip():
            raise RewriteError("reply is missing text")
        return _sanitize(channel, None, body)
    subject, body = data.get("subject"), data.get("body_html")
    if not isinstance(subject, str) or not isinstance(body, str) or not body.strip():
        raise RewriteError("reply is missing subject or body_html")
    return _sanitize(channel, subject, body)


_ACTION_TEXT = {
    "shorten": "Make it clearly shorter - aim for about half the length - without losing any fact, merge tag, link or call to action.",
    "friendlier": "Make the tone warmer and more personal, keeping about the same length and every fact, merge tag and link.",
}


def _action_text(channel: str, action: str, instruction: str | None) -> str:
    if action == "rewrite":
        return f"Rewrite it as follows, keeping everything the instruction doesn't touch: {instruction}"
    if action == "reformat":
        if channel == "whatsapp":
            return (
                "Reformat it for easy reading on a phone: short lines, a blank line between ideas, '•' bullets for lists. "
                "Change wording only where the formatting needs it."
            )
        return "Tidy the formatting: short paragraphs, lists where there are lists. Keep the wording."
    return _ACTION_TEXT[action]


def _system_prompt(channel: str, keep_tags: bool, tags_text: str, business_text: str, custom_html: bool) -> str:
    if channel == "whatsapp":
        medium = (
            "You edit a WhatsApp message a small business will send to a customer. Plain text only - no HTML, no markdown headings. "
            "WhatsApp formatting is fine: *bold* and _italic_. Use short paragraphs and line breaks. Add an emoji only if the original "
            "has one or the person asked for a friendlier tone (one or two at most). "
            'Reply with ONLY a JSON object: {"text": "..."}'
        )
    elif custom_html:
        medium = (
            "You edit the text of an email a small business will send. The email is a designed HTML layout: keep ALL the markup, tables "
            "and style attributes exactly as they are and change only the words inside. "
            'Reply with ONLY a JSON object: {"subject": "...", "body_html": "..."}'
        )
    else:
        medium = (
            "You edit an email a small business will send. body_html is simple rich text: only <p>, <strong>, <em>, <u>, <ul>/<ol>/<li>, "
            "<a href>, <br>. No tables, no style attributes, no <div>. "
            'Reply with ONLY a JSON object: {"subject": "...", "body_html": "..."}'
        )
    tags = (
        "Merge tags look like {{customer.first_name}}, and blocks like {{#each ...}} ... {{/each}} and {{#if ...}} ... {{/if}}. They are "
        "filled in per customer later. Copy EVERY merge tag exactly as written - the same tags, the same block structure, nothing "
        "added, nothing removed - and never write example data in place of one."
        if keep_tags
        else "You may reword around merge tags or drop them if the request calls for it, but any merge tag you keep or add must be one "
        f"of these (copy the syntax exactly):\n{tags_text}"
    )
    return f"""{medium}

{business_text}

{tags}

Rules:
- Never invent facts: no new prices, discounts, dates, deadlines, links, names or promises. Keep every link exactly as written.
- Leave [bracketed placeholders] where they are - they are blanks the sender still has to fill in.
- Keep the original language and the sender's voice unless asked to change it.
- Do the one thing asked and nothing else."""


def _issues(
    channel: str,
    keep_tags: bool,
    original: tuple[str, str],
    result: tuple[str | None, str],
    check: Callable[[str, str], list[str]],
) -> list[str]:
    """Everything wrong with a candidate reply, in words the model can act on."""
    orig_subject, orig_body = original
    subject, body = result
    out_subject = subject or ""
    issues: list[str] = []

    if keep_tags:
        wanted, got = extract_tags(orig_subject + "\n" + orig_body), extract_tags(out_subject + "\n" + body)
        missing = [t for t in dict.fromkeys(wanted) if t not in got]
        added = [t for t in dict.fromkeys(got) if t not in wanted]
        if missing:
            issues.append("These merge tags are missing and must be put back exactly: " + ", ".join(missing))
        if added:
            issues.append("These merge tags were not in the original and must be removed: " + ", ".join(added))
        gone = [p for p in find_placeholders(orig_subject, orig_body) if p not in find_placeholders(out_subject, body)]
        if gone:
            issues.append("These [placeholders] were dropped and must stay: " + ", ".join(gone))

    lost_links = sorted(extract_urls(orig_subject + " " + orig_body) - extract_urls(out_subject + " " + body))
    if lost_links:
        issues.append("These links were dropped or changed and must stay exactly as written: " + ", ".join(lost_links))

    # tags the checker rejects - but only ones the text didn't already have
    before = set(check(orig_subject, orig_body))
    new_problems = [p for p in check(out_subject, body) if p not in before]
    if new_problems:
        issues.append("Some merge tags won't work: " + "; ".join(new_problems))
    return issues


def rewrite_message(
    *,
    channel: str,
    action: str,
    body: str,
    subject: str | None,
    instruction: str | None,
    keep_merge_tags: bool,
    tags_text: str,
    business_text: str,
    check: Callable[[str, str], list[str]],
) -> dict:
    """Returns {"subject", "body", "unchanged", "warning"}. `unchanged` is true when the
    original is being handed back because no safe rewrite came out."""
    if channel not in CHANNELS:
        raise RewriteError(f"channel must be one of {CHANNELS}")
    if action not in ACTIONS:
        raise RewriteError(f"action must be one of {ACTIONS}")
    if action == "rewrite" and not (instruction or "").strip():
        raise RewriteError("a rewrite needs an instruction")
    if not body.strip():
        raise RewriteError("there is nothing to rewrite")

    original = ((subject or "").strip(), body.strip())
    custom_html = channel == "email" and bool(_CUSTOM_HTML.search(body))
    system = _system_prompt(channel, keep_merge_tags, tags_text, business_text, custom_html)
    request = f"{_action_text(channel, action, instruction)}\n\n"
    if channel == "email":
        request += f"Subject:\n{original[0]}\n\nbody_html:\n{original[1]}"
    else:
        request += f"Message:\n{original[1]}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": request}]

    last_issues: list[str] = []
    for attempt in range(2):
        raw = extract_text(call_with_fallback(get_model, lambda model: model.invoke(messages)).content)
        try:
            candidate = _parse(channel, raw)
        except RewriteError as e:
            last_issues = [f"The reply wasn't usable ({e})."]
            messages += [{"role": "assistant", "content": raw}, {"role": "user", "content": last_issues[0] + " Reply with only the JSON object."}]
            continue
        if channel == "email" and not candidate[0]:
            candidate = (original[0], candidate[1])  # an empty subject isn't a rewrite of it
        last_issues = _issues(channel, keep_merge_tags, original, candidate, check)
        if not last_issues:
            subject_out, body_out = candidate
            return {
                "subject": subject_out if channel == "email" else None,
                "body": body_out,
                "unchanged": body_out == original[1] and (subject_out or "") == (original[0] if channel == "email" else ""),
                "warning": None,
            }
        messages += [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "That can't be used:\n- " + "\n- ".join(last_issues) + "\nFix this and reply with the full JSON again."},
        ]

    return {
        "subject": original[0] if channel == "email" else None,
        "body": original[1],
        "unchanged": True,
        "warning": "Couldn't rewrite this without " + (
            "changing its merge tags or links" if keep_merge_tags else "breaking a merge tag or link"
        ) + " - your original text is untouched. Try a more specific instruction.",
    }


def build_rewrite_context(db, org_id) -> tuple[str, str]:
    """(business facts, usable single-value tags) - the same context the email drafter gets."""
    from app.core.merge_tags import TAG_PATTERN, available_merge_tags
    from app.models.org_settings import OrgSettings
    from app.models.organization import Organization

    org = db.get(Organization, org_id)
    s = db.get(OrgSettings, org_id)
    business = [f"Business name: {(s.biz_name if s else None) or (org.name if org else '')}"]
    if s and s.industry:
        business.append(f"Industry: {s.industry}")
    if s and s.manager_name:
        business.append(f"Manager (can sign off): {s.manager_name}")
    tags = "\n".join(f"- {t['tag']} ({t['label']})" for t in available_merge_tags(db, org_id) if TAG_PATTERN.fullmatch(t["tag"]))
    return "\n".join(business), tags
