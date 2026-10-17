"""Consolidated JSON parsing: one canonical extractor behind every seam."""
import pytest

from app.utils.llm_json_utils import (
    extract_json_from_response as canonical_extract,
    parse_json_response,
)
from app.utils.llm_utils import extract_json_from_response as legacy_extract


@pytest.mark.parametrize("text,expected", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ('Here is the result: {"a": 1} done', {"a": 1}),
    ('[1, 2, 3]', [1, 2, 3]),
    ('```\n[1, 2]\n```', [1, 2]),
])
def test_canonical_and_shim_agree(text, expected):
    assert canonical_extract(text) == expected
    assert legacy_extract(text) == expected


def test_extract_raises_on_unparseable():
    with pytest.raises(ValueError):
        canonical_extract("no json here")
    with pytest.raises(ValueError):
        legacy_extract("")


def test_array_parser_keeps_truncation_repair():
    truncated = '[{"x": 1}, {"x": 2'
    assert parse_json_response(truncated, context="test") == [{"x": 1}]


def test_manager_delegates_to_canonical():
    from app.services.llm.manager import LLMManager

    manager = LLMManager.__new__(LLMManager)
    assert manager.parse_json_response('```json\n{"name": "t"}\n```') == {"name": "t"}
    assert manager.parse_json_response('{"name": "t"}') == {"name": "t"}
