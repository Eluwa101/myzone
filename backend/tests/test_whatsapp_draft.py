"""The assistant that writes a WhatsApp message from a description. A fake model stands in
for the LLM; what is tested is the plumbing and the tag checking we own."""
import json
from types import SimpleNamespace
from uuid import UUID

import pytest

import app.agent.email_draft as email_draft


class FakeModel:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def invoke(self, messages):
        self.calls.append(json.loads(json.dumps(messages)))
        reply = self.replies.pop(0)
        return SimpleNamespace(content=reply if isinstance(reply, str) else json.dumps(reply))


@pytest.fixture
def fake_model(monkeypatch):
    def install(*replies):
        model = FakeModel(replies)
        monkeypatch.setattr(email_draft, "call_with_fallback", lambda get_model, fn: fn(model))
        return model

    return install


def _draft(client, headers, **body):
    return client.post("/api/messages/draft-whatsapp", json={"description": "tell them their order is ready", **body}, headers=headers)


def test_writes_a_message_with_merge_tags_and_flags_blanks(client, auth_headers, fake_model):
    model = fake_model({"text": "Hi {{customer.first_name}}, your order from {{business.name}} is ready! Enjoy [discount] off next time."})
    resp = _draft(client, auth_headers)
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert out["text"].startswith("Hi {{customer.first_name}}") and out["problems"] == [] and out["placeholders"] == ["[discount]"]
    assert "Write this WhatsApp message" in model.calls[0][1]["content"]
    assert "Plain text only" in model.calls[0][0]["content"]


def test_broken_tag_gets_one_retry_then_is_reported_not_hidden(client, auth_headers, fake_model):
    model = fake_model({"text": "Hi {{nonsense.tag}}"}, {"text": "Hi {{still.bad}}"})
    out = _draft(client, auth_headers).json()
    assert len(model.calls) == 2 and "nonsense" in model.calls[1][-1]["content"]
    assert out["problems"]  # still broken after the retry - the person sees it, nothing is silently fixed or sent


def test_broken_tag_fixed_on_retry(client, auth_headers, fake_model):
    fake_model({"text": "Hi {{nonsense.tag}}"}, {"text": "Hi {{customer.first_name}}"})
    out = _draft(client, auth_headers).json()
    assert out["text"] == "Hi {{customer.first_name}}" and out["problems"] == []


def test_html_in_the_reply_becomes_plain_text(client, auth_headers, fake_model):
    fake_model({"text": "<p>Hi {{customer.first_name}},</p><p>Your order is <b>ready</b>.</p>"})
    text = _draft(client, auth_headers).json()["text"]
    assert "<" not in text and "Hi {{customer.first_name}}" in text


def test_editing_an_existing_message_sends_it_along(client, auth_headers, fake_model):
    model = fake_model({"text": "Hi {{customer.first_name}}, ready!"})
    _draft(client, auth_headers, description="make it shorter", current_text="Hi {{customer.first_name}}, your order is now ready for collection.")
    assert "Current message" in model.calls[0][1]["content"] and "ready for collection" in model.calls[0][1]["content"]


def test_unusable_reply_is_a_clear_error(client, auth_headers, fake_model):
    fake_model("sorry!", "still sorry")
    assert _draft(client, auth_headers).status_code == 422


def test_segment_context_is_used_and_unknown_segment_is_404(client, auth_headers, fake_model):
    seg = client.post("/api/segments", json={"name": "Everyone"}, headers=auth_headers).json()
    model = fake_model({"text": "Hi {{customer.first_name}}"})
    assert _draft(client, auth_headers, segment_id=seg["id"]).status_code == 200
    assert "customer segment" in model.calls[0][0]["content"]
    assert _draft(client, auth_headers, segment_id=str(UUID(int=1))).status_code == 404
    assert _draft(client, auth_headers, description="").status_code == 422
