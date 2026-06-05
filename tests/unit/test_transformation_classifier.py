"""
Unit tests for transformation-classification loading.

Covers the display-path helpers added to read the transformation classification
from the live synthesis-pipeline record in ``extraction_prompts`` (rather than
the legacy ``case_transformation`` table, which the precedent feature extractor
resets to NULL on re-extraction):

- ``_parse_transformation_record``: parses the stored LLM output, handling both
  the bare-JSON and the markdown-fenced forms, and raising on real corruption.
- ``load_latest_transformation``: queries the latest record and normalizes its
  keys for display.

These tests mock the model query to avoid database and LLM dependencies.
"""

import json
import types

import pytest
from unittest.mock import MagicMock, patch

from app.services.case_analysis.transformation_classifier import (
    _parse_transformation_record,
    load_latest_transformation,
)


def _prompt(raw_response=None, results_summary=None):
    """A stand-in for an ExtractionPrompt row (only the read fields)."""
    return types.SimpleNamespace(
        raw_response=raw_response,
        results_summary=results_summary,
    )


def _patch_query(prompt):
    """Patch ExtractionPrompt so the query chain yields ``prompt`` (or None)."""
    mock_model = MagicMock()
    mock_model.query.filter_by.return_value.order_by.return_value.first.return_value = prompt
    return patch('app.models.ExtractionPrompt', mock_model)


# =============================================================================
# _parse_transformation_record
# =============================================================================

class TestParseTransformationRecord:

    def test_bare_json_raw_response(self):
        rec = _parse_transformation_record(_prompt(raw_response='{"type": "transfer"}'))
        assert rec == {"type": "transfer"}

    def test_fenced_json_with_language_tag(self):
        raw = '```json\n{"type": "stalemate"}\n```'
        assert _parse_transformation_record(_prompt(raw_response=raw)) == {"type": "stalemate"}

    def test_fenced_json_without_language_tag(self):
        raw = '```\n{"type": "oscillation"}\n```'
        assert _parse_transformation_record(_prompt(raw_response=raw)) == {"type": "oscillation"}

    def test_results_summary_dict_when_raw_empty(self):
        rec = _parse_transformation_record(
            _prompt(raw_response='', results_summary={"type": "phase_lag"})
        )
        assert rec == {"type": "phase_lag"}

    def test_results_summary_json_string_when_raw_empty(self):
        rec = _parse_transformation_record(
            _prompt(raw_response=None, results_summary='{"type": "transfer"}')
        )
        assert rec == {"type": "transfer"}

    def test_returns_none_when_no_data(self):
        assert _parse_transformation_record(_prompt(raw_response=None, results_summary=None)) is None

    def test_malformed_raw_response_raises(self):
        # A malformed record is real corruption, not an absence of data; it must
        # raise rather than be silently dropped.
        with pytest.raises(json.JSONDecodeError):
            _parse_transformation_record(_prompt(raw_response='{not valid json'))


# =============================================================================
# load_latest_transformation
# =============================================================================

class TestLoadLatestTransformation:

    def test_returns_none_when_no_prompt(self):
        with _patch_query(None):
            assert load_latest_transformation(case_id=8) is None

    def test_normalizes_transformation_type_key(self):
        p = _prompt(raw_response=json.dumps({
            "transformation_type": "transfer",
            "pattern_description": "obligation moves to another party",
            "confidence": 0.9,
            "reasoning": "because the duty shifts",
        }))
        with _patch_query(p):
            assert load_latest_transformation(case_id=8) == {
                "type": "transfer",
                "pattern": "obligation moves to another party",
                "confidence": 0.9,
                "reasoning": "because the duty shifts",
            }

    def test_normalizes_short_type_and_pattern_keys(self):
        p = _prompt(raw_response=json.dumps({"type": "stalemate", "pattern": "stuck"}))
        with _patch_query(p):
            result = load_latest_transformation(case_id=8)
        assert result["type"] == "stalemate"
        assert result["pattern"] == "stuck"
        assert result["confidence"] is None
        assert result["reasoning"] == ""

    def test_returns_none_when_record_has_no_type(self):
        p = _prompt(raw_response=json.dumps({"pattern": "no type here"}))
        with _patch_query(p):
            assert load_latest_transformation(case_id=8) is None
