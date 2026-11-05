"""
Regression test: Gemini (and other multimodal-capable models) can return
.content as a list of blocks instead of a plain string, even for a
text-only reply. This broke persisting chat messages (a string column)
until extract_text normalized it.
"""
from app.agent.model import extract_text


def test_extract_text_passes_through_plain_string():
    assert extract_text("hello") == "hello"


def test_extract_text_joins_text_blocks():
    assert extract_text([{"type": "text", "text": "hello "}, {"type": "text", "text": "world"}]) == "hello world"


def test_extract_text_handles_plain_strings_in_list():
    assert extract_text(["hello ", "world"]) == "hello world"


def test_extract_text_ignores_non_text_blocks():
    assert extract_text([{"type": "text", "text": "hi"}, {"type": "image_url", "image_url": {"url": "x"}}]) == "hi"


def test_extract_text_handles_empty_and_none():
    assert extract_text(None) == ""
    assert extract_text([]) == ""
    assert extract_text("") == ""
