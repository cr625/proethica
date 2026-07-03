"""Step-3 temporal extractor budget floors (WP-A: direct_call_params routing).

The five temporal_dynamics extractors make direct ``client.messages.stream`` calls on
the POWERFUL tier with per-call budgets of 4000-12000 tokens. Thinking-by-default
models (Fable 5, Sonnet 5) spend thinking tokens from the SAME ``max_tokens`` budget
as the visible text, so those budgets truncate the JSON mid-generation (the exact
failure mode that cut the transformation classifier at 1500 before it was floored).
Every call site now routes its model/max_tokens/temperature kwargs through
``app.utils.llm_utils.direct_call_params``; these tests pin the built call kwargs:

(a) under a thinking-by-default model the budget floors to 16000 and ``temperature``
    is passed only when the model supports it (Fable 5 / Sonnet 5 reject it);
(b) under a non-thinking model the requested budget is preserved unchanged, and the
    causal extractor (the only temporal call site that sets a temperature) still
    passes its temperature=0.2;
(c) under Opus 4.8 (temperature-unsupported but NOT thinking-by-default) the causal
    budget stays 12000 and temperature is omitted.

Style mirrors tests/extraction/test_thinking_model_hardening.py. DB/LLM-free: the
Anthropic client and (where the prompt builder reads ontology files) the prompt
builder are faked; assertions are on the kwargs captured from ``messages.stream``.
"""
import json
from types import SimpleNamespace

import anthropic
import pytest

from model_config import ModelConfig

from app.services.temporal_dynamics.extractors import action_extractor
from app.services.temporal_dynamics.extractors import causal_extractor
from app.services.temporal_dynamics.extractors import event_extractor
from app.services.temporal_dynamics.extractors import temporal_extractor
from app.services.temporal_dynamics.extractors import temporal_marker_extractor

_NON_THINKING_MODEL = "claude-sonnet-4-6"
_THINKING_MODELS = sorted(ModelConfig.THINKING_ON_BY_DEFAULT)


# ---------------------------------------------------------------------------
# Fakes: an Anthropic client whose messages.stream captures its kwargs and
# returns a thinking-first message (so text_from_message is exercised too).
# ---------------------------------------------------------------------------

class _FakeStream:
    def __init__(self, message):
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._message


class _FakeClient:
    """Captures messages.stream(**kwargs) into ``captured`` and returns ``response_text``."""

    def __init__(self, captured, response_text):
        def _stream(**kwargs):
            captured.append(dict(kwargs))
            message = SimpleNamespace(
                content=[
                    SimpleNamespace(type="thinking", thinking="chain of thought"),
                    SimpleNamespace(type="text", text=response_text),
                ],
                usage=SimpleNamespace(input_tokens=10, output_tokens=20),
            )
            return _FakeStream(message)

        self.messages = SimpleNamespace(stream=_stream)


def _patch_client_and_model(monkeypatch, captured, response_text, model):
    """Route the in-function ``anthropic.Anthropic(...)`` construction to the fake
    client and pin the powerful tier to ``model`` (the extractors resolve it via
    ``ModelConfig.get_claude_model('powerful')``)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    fake = _FakeClient(captured, response_text)
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: fake)
    monkeypatch.setattr(
        ModelConfig, "get_claude_model",
        classmethod(lambda cls, use_case="default": model),
    )
    return fake


def _assert_floored_no_temperature(kwargs, model):
    assert kwargs["model"] == model
    assert kwargs["max_tokens"] == 16000, (
        "thinking spends from the same max_tokens budget; the requested budget "
        "must floor to 16000 under a thinking-by-default model"
    )
    # Both thinking-by-default models also reject temperature; the gate must hold.
    assert ("temperature" in kwargs) == ModelConfig.supports_temperature(model)


# ---------------------------------------------------------------------------
# Action extractor (Stage 3, requested budget 8000)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("model", _THINKING_MODELS)
def test_action_extractor_floors_budget_for_thinking_models(model):
    captured = []
    client = _FakeClient(captured, "not json, unused")
    action_extractor._call_llm_with_streaming(client, model, "PROMPT", "Phase 1", 0)
    assert len(captured) == 1
    _assert_floored_no_temperature(captured[0], model)


def test_action_extractor_preserves_budget_for_non_thinking_model():
    captured = []
    client = _FakeClient(captured, "unused")
    action_extractor._call_llm_with_streaming(client, _NON_THINKING_MODEL, "PROMPT", "Phase 1", 0)
    assert captured[0]["max_tokens"] == 8000
    assert "temperature" not in captured[0]  # the action call site sets no temperature


# ---------------------------------------------------------------------------
# Event extractor (Stage 4, requested budget 8000)
# ---------------------------------------------------------------------------

def _run_event_extractor(monkeypatch, model):
    captured = []
    _patch_client_and_model(monkeypatch, captured, json.dumps({"events": []}), model)
    # The real prompt builder reads ontology TTL/SHACL files (concept_ontology_slots);
    # the assertion is about the call kwargs, so keep the test file-read-free.
    monkeypatch.setattr(
        event_extractor, "_build_event_extraction_prompt",
        lambda *args, **kwargs: "PROMPT",
    )
    events = event_extractor.extract_events_with_classification(
        narrative={}, temporal_markers={}, actions=[], case_id=0, llm_trace=[],
    )
    assert events == []
    assert len(captured) == 1, "the stream call must have been reached (not swallowed)"
    return captured[0]


@pytest.mark.parametrize("model", _THINKING_MODELS)
def test_event_extractor_floors_budget_for_thinking_models(monkeypatch, model):
    _assert_floored_no_temperature(_run_event_extractor(monkeypatch, model), model)


def test_event_extractor_preserves_budget_for_non_thinking_model(monkeypatch):
    kwargs = _run_event_extractor(monkeypatch, _NON_THINKING_MODEL)
    assert kwargs["max_tokens"] == 8000
    assert "temperature" not in kwargs  # the event call site sets no temperature


# ---------------------------------------------------------------------------
# Causal extractor (Stage 5, requested budget 12000, temperature 0.2)
# ---------------------------------------------------------------------------

def _run_causal_extractor(monkeypatch, model):
    captured = []
    _patch_client_and_model(
        monkeypatch, captured, json.dumps({"causal_relationships": []}), model,
    )
    chains = causal_extractor.analyze_causal_chains(
        actions=[], events=[], case_id=0, llm_trace=[],
        facts_text="facts", discussion_text="discussion",
    )
    assert chains == []
    assert len(captured) == 1, "the stream call must have been reached (not swallowed)"
    return captured[0]


@pytest.mark.parametrize("model", _THINKING_MODELS)
def test_causal_extractor_floors_budget_for_thinking_models(monkeypatch, model):
    _assert_floored_no_temperature(_run_causal_extractor(monkeypatch, model), model)


def test_causal_extractor_preserves_budget_and_temperature_for_non_thinking_model(monkeypatch):
    kwargs = _run_causal_extractor(monkeypatch, _NON_THINKING_MODEL)
    assert kwargs["max_tokens"] == 12000
    assert kwargs["temperature"] == 0.2  # the one temporal call site that samples


def test_causal_extractor_omits_temperature_for_opus48_without_flooring(monkeypatch):
    # Opus 4.8: rejects temperature but is NOT thinking-by-default, so the
    # requested budget passes through unchanged while temperature is gated off.
    kwargs = _run_causal_extractor(monkeypatch, "claude-opus-4-8")
    assert kwargs["max_tokens"] == 12000
    assert "temperature" not in kwargs


# ---------------------------------------------------------------------------
# Stage 1 section analysis + Stage 2 temporal markers (requested budget 4000)
# ---------------------------------------------------------------------------

_SECTION_ANALYSIS_JSON = json.dumps({
    "unified_timeline_summary": "summary",
    "decision_points": [],
    "temporal_overlap_notes": "notes",
    "competing_priorities_mentioned": [],
})

_MARKERS_JSON = json.dumps({
    "explicit_dates": [],
    "temporal_phrases": [],
    "durations": [],
    "allen_relations": [],
})


@pytest.mark.parametrize("model", _THINKING_MODELS)
def test_section_analysis_floors_budget_for_thinking_models(monkeypatch, model):
    captured = []
    _patch_client_and_model(monkeypatch, captured, _SECTION_ANALYSIS_JSON, model)
    analysis, trace = temporal_extractor.analyze_combined_sections("facts", "discussion")
    assert analysis["unified_timeline_summary"] == "summary"
    assert len(captured) == 1
    _assert_floored_no_temperature(captured[0], model)


def test_section_analysis_preserves_budget_for_non_thinking_model(monkeypatch):
    captured = []
    _patch_client_and_model(monkeypatch, captured, _SECTION_ANALYSIS_JSON, _NON_THINKING_MODEL)
    temporal_extractor.analyze_combined_sections("facts", "discussion")
    assert captured[0]["max_tokens"] == 4000
    assert "temperature" not in captured[0]


@pytest.mark.parametrize("model", _THINKING_MODELS)
def test_temporal_markers_floors_budget_for_thinking_models(monkeypatch, model):
    captured = []
    _patch_client_and_model(monkeypatch, captured, _MARKERS_JSON, model)
    markers = temporal_marker_extractor.extract_temporal_markers_llm(
        "facts", "discussion", "timeline summary", llm_trace=[],
    )
    assert markers["explicit_dates"] == []
    assert len(captured) == 1
    _assert_floored_no_temperature(captured[0], model)


def test_temporal_markers_preserves_budget_for_non_thinking_model(monkeypatch):
    captured = []
    _patch_client_and_model(monkeypatch, captured, _MARKERS_JSON, _NON_THINKING_MODEL)
    temporal_marker_extractor.extract_temporal_markers_llm(
        "facts", "discussion", "timeline summary", llm_trace=[],
    )
    assert captured[0]["max_tokens"] == 4000
    assert "temperature" not in captured[0]
