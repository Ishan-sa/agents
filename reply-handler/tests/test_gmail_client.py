from __future__ import annotations

import base64

from reply_handler.gmail_client import (
    _extract_text_from_payload,
    _headers_dict,
    build_raw_reply,
)


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("utf-8")


def test_build_raw_reply_includes_threading_headers():
    raw = build_raw_reply(
        to="prospect@example.com",
        subject="Re: site rebuild",
        body="hey there",
        in_reply_to_message_id="<orig@mail.example>",
        references="<orig@mail.example>",
    )
    decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()
    assert "To: prospect@example.com" in decoded
    assert "Subject: Re: site rebuild" in decoded
    assert "In-Reply-To: <orig@mail.example>" in decoded
    assert "References: <orig@mail.example>" in decoded
    assert "hey there" in decoded


def test_build_raw_reply_skips_threading_headers_when_empty():
    raw = build_raw_reply(
        to="x@y.com", subject="hi", body="b",
        in_reply_to_message_id="", references="",
    )
    decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()
    assert "In-Reply-To" not in decoded
    assert "References" not in decoded


def test_extract_text_finds_plain_part_in_multipart():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": _b64("the plain body")}},
            {"mimeType": "text/html", "body": {"data": _b64("<p>html</p>")}},
        ],
    }
    assert "the plain body" in _extract_text_from_payload(payload)


def test_extract_text_falls_back_to_html_when_no_plain():
    payload = {
        "mimeType": "text/html",
        "body": {"data": _b64("<p>hello <b>world</b></p>")},
    }
    text = _extract_text_from_payload(payload)
    assert "hello" in text
    assert "world" in text
    assert "<" not in text  # tags stripped


def test_headers_dict_lowercases_keys():
    payload = {
        "headers": [
            {"name": "From", "value": "a@b.com"},
            {"name": "Message-ID", "value": "<x>"},
        ]
    }
    h = _headers_dict(payload)
    assert h["from"] == "a@b.com"
    assert h["message-id"] == "<x>"
