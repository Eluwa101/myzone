"""
The message rewrite skill. A fake model stands in for the LLM, so these test the
safeguards - the part we own - not the model's judgment: merge tags, links and
[placeholders] must survive, and a reply that breaks them is retried and then
discarded in favour of the original.
"""
import json
from types import SimpleNamespace

import pytest

import app.agent.rewrite as rewrite_module

ORIGINAL_WA = "Hi {{customer.first_name}}, your order from {{business.name}} is ready. Pay at https://pay.example.com/abc or call us. Offer: [discount] off!"


class FakeModel:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(json.loads(json.dumps(messages)))
        reply = self.replies.pop(0)
        return SimpleNamespace(content=reply if isinstance(reply, str) else json.dumps(reply))


@pytest.fixture
def fake_model(monkeypatch):
    def install(*replies):
        model = FakeModel(replies)
        monkeypatch.setattr(rewrite_module, "call_with_fallback", lambda get_model, fn: fn(model))
        return model

    return install


def _post(client, headers, **overrides):
    payload = {"channel": "whatsapp", "action": "shorten", "body": ORIGINAL_WA, **overrides}
    return client.post("/api/messages/rewrite", json=payload, headers=headers)


def test_good_rewrite_keeps_tags_link_and_placeholder(client, auth_headers, fake_model):
    model = fake_model({"text": "Hi {{customer.first_name}}, your order from {{business.name}} is ready: https://pay.example.com/abc. [discount] off!"})
    resp = _post(client, auth_headers)
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert out["warning"] is None and out["unchanged"] is False
    assert "{{customer.first_name}}" in out["body"] and "https://pay.example.com/abc" in out["body"]
    assert out["placeholders"] == ["[discount]"]
    assert len(model.calls) == 1


def test_dropped_tag_is_retried_with_the_specific_problem_named(client, auth_headers, fake_model):
    model = fake_model(
        {"text": "Hi there, your order is ready: https://pay.example.com/abc. [discount] off!"},  # lost both tags
        {"text": "Hi {{customer.first_name}}, order from {{business.name}} ready: https://pay.example.com/abc. [discount] off!"},
    )
    out = _post(client, auth_headers).json()
    assert out["warning"] is None and "{{customer.first_name}}" in out["body"]
    assert len(model.calls) == 2
    feedback = model.calls[1][-1]["content"]
    assert "{{customer.first_name}}" in feedback and "{{business.name}}" in feedback and "missing" in feedback


def test_unfixable_reply_returns_the_original_untouched_with_a_warning(client, auth_headers, fake_model):
    model = fake_model({"text": "Short message, no tags."}, {"text": "Still no tags."})
    out = _post(client, auth_headers).json()
    assert out["body"] == ORIGINAL_WA and out["unchanged"] is True
    assert "untouched" in out["warning"]
    assert len(model.calls) == 2  # exactly one retry, not a loop


def test_invented_tag_is_rejected(client, auth_headers, fake_model):
    fake_model(
        {"text": "Hi {{customer.first_name}} {{customer.last_name}}, from {{business.name}}: https://pay.example.com/abc [discount]"},
        {"text": "Hi {{customer.first_name}}, from {{business.name}}: https://pay.example.com/abc [discount]"},
    )
    out = _post(client, auth_headers).json()
    assert "last_name" not in out["body"] and out["warning"] is None


def test_dropped_link_and_dropped_placeholder_are_rejected(client, auth_headers, fake_model):
    model = fake_model(
        {"text": "Hi {{customer.first_name}}, {{business.name}} order ready. [discount]"},  # link gone
        {"text": "Hi {{customer.first_name}}, {{business.name}}: https://pay.example.com/abc ready."},  # placeholder gone
    )
    out = _post(client, auth_headers).json()
    assert out["unchanged"] is True and out["body"] == ORIGINAL_WA
    assert "https://pay.example.com/abc" in model.calls[1][-1]["content"]
    assert "[discount]" in model.calls[1][-1]["content"] or "[discount]" in str(model.calls)


def test_spacing_inside_a_tag_is_not_a_change(client, auth_headers, fake_model):
    fake_model({"text": "Hi {{ customer.first_name }}, {{business.name}} order ready: https://pay.example.com/abc [discount]"})
    assert _post(client, auth_headers).json()["warning"] is None


def test_unparseable_reply_gets_one_retry(client, auth_headers, fake_model):
    model = fake_model("sorry, here is your message!", {"text": "Hi {{customer.first_name}} {{business.name}} https://pay.example.com/abc [discount]"})
    out = _post(client, auth_headers).json()
    assert out["warning"] is None and len(model.calls) == 2


def test_whatsapp_reply_with_html_is_converted_to_plain_text(client, auth_headers, fake_model):
    fake_model({"text": "<p>Hi {{customer.first_name}},</p><p>{{business.name}} <b>ready</b>: https://pay.example.com/abc<br>[discount]</p>"})
    body = _post(client, auth_headers).json()["body"]
    assert "<" not in body and body.startswith("Hi {{customer.first_name}},")


def test_keep_tags_off_allows_dropping_tags_but_not_inventing_broken_ones(client, auth_headers, fake_model):
    fake_model({"text": "Your order is ready: https://pay.example.com/abc [discount]"})  # tags gone - fine when the user asked for it
    out = _post(client, auth_headers, keep_merge_tags=False, action="rewrite", instruction="remove all personalization").json()
    assert out["warning"] is None and "{{" not in out["body"]

    fake_model({"text": "Hi {{nonsense.tag}} https://pay.example.com/abc [discount]"}, {"text": "Hi friend https://pay.example.com/abc [discount]"})
    out = _post(client, auth_headers, keep_merge_tags=False).json()
    assert "nonsense" not in out["body"]  # a tag that won't resolve is never accepted


def test_links_are_kept_even_when_tags_may_change(client, auth_headers, fake_model):
    fake_model({"text": "Hi friend, order ready. [discount]"}, {"text": "Hi friend, order ready. [discount]"})
    out = _post(client, auth_headers, keep_merge_tags=False).json()
    assert out["unchanged"] is True and "https://pay.example.com/abc" in out["body"]


def test_email_rewrite_returns_subject_and_body(client, auth_headers, fake_model):
    fake_model({"subject": "Hi {{customer.first_name}} - quick note", "body_html": "<p>Hello {{customer.first_name}}, short and sweet.</p>"})
    out = _post(client, auth_headers, channel="email", subject="Hello {{customer.first_name}}, a long subject line", body="<p>Hello {{customer.first_name}}, a very long email.</p>").json()
    assert out["subject"] == "Hi {{customer.first_name}} - quick note" and "short and sweet" in out["body"]


def test_designed_email_prompt_says_to_keep_the_layout(client, auth_headers, fake_model):
    model = fake_model({"subject": "s", "body_html": '<table><tr><td style="color:red">Hello {{customer.first_name}}</td></tr></table>'})
    _post(client, auth_headers, channel="email", subject="s", body='<table><tr><td style="color:red">Hello there {{customer.first_name}} and more</td></tr></table>')
    system = model.calls[0][0]["content"]
    assert "keep ALL the markup" in system


def test_rewrite_needs_an_instruction_and_a_body(client, auth_headers, fake_model):
    fake_model()
    assert _post(client, auth_headers, action="rewrite").status_code == 422  # no instruction
    assert _post(client, auth_headers, body="").status_code == 422
    assert _post(client, auth_headers, action="explode").status_code == 422
    assert _post(client, auth_headers, channel="sms").status_code == 422


def test_prompt_carries_the_keep_tags_rule_or_the_allowed_list(client, auth_headers, fake_model):
    model = fake_model({"text": "Hi {{customer.first_name}} {{business.name}} https://pay.example.com/abc [discount]"})
    _post(client, auth_headers)
    assert "Copy EVERY merge tag exactly" in model.calls[0][0]["content"]
    model = fake_model({"text": "Hi {{customer.first_name}} {{business.name}} https://pay.example.com/abc [discount]"})
    _post(client, auth_headers, keep_merge_tags=False)
    assert "must be one of these" in model.calls[0][0]["content"] and "{{customer.first_name}}" in model.calls[0][0]["content"]


def test_assistant_tool_is_read_only_and_uses_the_same_guarantees(db_session, seeded_org, fake_model):
    from app.agent.read_tools import build_read_tools
    from app.agent.tools import build_tools

    org_id, user_id = seeded_org
    assert "rewrite_message" in {t.name for t in build_read_tools(db_session, org_id)}  # available to Ask Data too
    tools = {t.name: t for t in build_tools(db_session, org_id, user_id)}

    fake_model({"text": "Hi {{customer.first_name}}!"})
    out = tools["rewrite_message"].invoke({"text": "Hi {{customer.first_name}}, long message here", "action": "shorten"})
    assert out["text"] == "Hi {{customer.first_name}}!" and out["warning"] is None

    fake_model({"text": "Hi!"}, {"text": "Hi!"})  # tag dropped twice
    out = tools["rewrite_message"].invoke({"text": "Hi {{customer.first_name}}, long message here", "action": "shorten"})
    assert out["unchanged"] is True and out["text"] == "Hi {{customer.first_name}}, long message here"

    assert tools["rewrite_message"].invoke({"text": "x", "action": "rewrite"})["status"] == "error"  # needs an instruction
