from __future__ import annotations

import pytest

from reply_handler.llm import parse_inner_json


def test_parse_plain_json():
    assert parse_inner_json('{"a": 1}') == {"a": 1}


def test_parse_strips_code_fences():
    text = '```json\n{"a": 2}\n```'
    assert parse_inner_json(text) == {"a": 2}


def test_parse_slices_to_outermost_braces():
    text = 'here is some prose {"a": 3} and more prose'
    assert parse_inner_json(text) == {"a": 3}


def test_parse_invalid_raises():
    with pytest.raises(Exception):
        parse_inner_json("not json at all")
