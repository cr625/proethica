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


# The 25-1 edge-selection reply on Sonnet 5.5, shortened: an answer, a self-correction, a
# second answer. Both parsers failed on it and the edge families fell back to embeddings.
SELF_CORRECTING_REPLY = (
    '{"1": [1], "2": [2, 1], "3": [3, 2, 1]}\n'
    'Wait, I need to map the numbers to the candidate lists correctly. Corrected output:\n'
    '{"1": [1], "2": [1, 2], "3": [1, 2, 3]}'
)


def test_self_correcting_reply_yields_the_corrected_object():
    expected = {"1": [1], "2": [1, 2], "3": [1, 2, 3]}
    assert canonical_extract(SELF_CORRECTING_REPLY) == expected
    assert legacy_extract(SELF_CORRECTING_REPLY) == expected


def test_last_fenced_object_wins():
    text = ('```json\n{"a": 1}\n```\nWait, that was wrong. Corrected:\n'
            '```json\n{"a": 2}\n```')
    assert canonical_extract(text) == {"a": 2}


def test_single_object_with_nested_objects_is_unchanged():
    text = 'Result: {"a": {"b": 1}, "c": [{"d": 2}]} as requested'
    assert canonical_extract(text) == {"a": {"b": 1}, "c": [{"d": 2}]}
