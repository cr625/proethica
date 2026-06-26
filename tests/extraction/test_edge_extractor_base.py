"""
Characterization tests for the shared edge-extractor base and its subclasses.

These lock the behavior preserved by the `StreamingEdgeExtractor` refactor
(plan: .claude/plans/services-modularization.md, Phase 1). They run with a
mocked Anthropic client so no API access is needed. The defeasibility extractor
is already covered by test_defeasibility_edges.py; this module adds the RPO and
temporal-sequence subclasses plus the base-level invariants (the shared
truncation-recovery scan and the swallow-vs-propagate error semantics).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.services.extraction.edge_extractor_base import StreamingEdgeExtractor


@pytest.fixture(autouse=True)
def _stub_edge_templates(monkeypatch):
    """rpo_edges and defeasibility now render their prompts from editable DB templates; stub the
    loaders so these mock-client tests need no DB / app context (the mock ignores the prompt text).
    The temporal-sequence loader is stubbed separately in TestTemporalSequenceExtractor."""
    class _Stub:
        def render(self, **kw):
            return "USER"

        def render_system(self, **kw):
            return "SYSTEM"

    import app.services.extraction.rpo_edges as rpo
    import app.services.extraction.enhanced_prompts_defeasibility as defp
    monkeypatch.setattr(rpo, "_load_rpo_template", lambda: _Stub())
    monkeypatch.setattr(defp, "_load_defeasibility_template", lambda: _Stub())


# ---------------------------------------------------------------------------
# Mock client helpers (mirror the Anthropic streaming context-manager shape)
# ---------------------------------------------------------------------------

def _make_mock_client_raw_text(raw: str, stop_reason: str = "end_turn") -> MagicMock:
    client = MagicMock()
    final_msg = MagicMock()
    final_msg.stop_reason = stop_reason
    final_msg.usage = MagicMock(input_tokens=10, output_tokens=20)

    stream_obj = MagicMock()
    stream_obj.text_stream = iter([raw])
    stream_obj.get_final_message.return_value = final_msg

    stream_ctx = MagicMock()
    stream_ctx.__enter__ = MagicMock(return_value=stream_obj)
    stream_ctx.__exit__ = MagicMock(return_value=False)

    client.messages.stream.return_value = stream_ctx
    return client


def _make_mock_client_json(payload: dict) -> MagicMock:
    return _make_mock_client_raw_text(json.dumps(payload))


def _make_mock_client_that_raises() -> MagicMock:
    client = MagicMock()
    client.messages.stream.side_effect = RuntimeError("boom")
    return client


# ---------------------------------------------------------------------------
# Base-level invariants
# ---------------------------------------------------------------------------

class TestSharedRecoveryScan:
    def test_iter_flat_json_objects(self):
        raw = 'noise {"a": 1} junk {"b": 2, "c": "x"} tail {not json}'
        objs = list(StreamingEdgeExtractor._iter_flat_json_objects(raw))
        assert objs == [{"a": 1}, {"b": 2, "c": "x"}]

    def test_iter_skips_non_dict_and_unparseable(self):
        raw = '{"ok": true} {oops} {"also": 2}'
        objs = list(StreamingEdgeExtractor._iter_flat_json_objects(raw))
        assert objs == [{"ok": True}, {"also": 2}]


class TestStreamErrorSemantics:
    """RPO historically propagated stream exceptions; defeasibility and
    temporal-sequence swallowed them. The base preserves both via
    `swallow_stream_errors`."""

    def test_swallowing_extractor_returns_none_on_stream_error(self):
        from app.services.extraction.defeasibility_edges import (
            DefeasibilityEdgeExtractor,
        )
        from app.services.extraction.enhanced_prompts_defeasibility import (
            ObligationContext,
        )

        client = _make_mock_client_that_raises()
        extractor = DefeasibilityEdgeExtractor(llm_client=client, model="claude-test-model")
        # Two obligations so the extractor actually reaches the LLM call.
        edges = extractor.extract(
            case_id=1,
            obligations=[
                ObligationContext(iri="http://x/o1", label="o1"),
                ObligationContext(iri="http://x/o2", label="o2"),
            ],
            states=[],
        )
        assert edges == []

    def test_propagating_extractor_raises_on_stream_error(self):
        from app.services.extraction.rpo_edges import RPOEdgeExtractor, Indiv

        client = _make_mock_client_that_raises()
        extractor = RPOEdgeExtractor(llm_client=client, model="claude-test-model")
        with pytest.raises(RuntimeError):
            extractor.extract(
                case_id=1,
                roles=[Indiv("http://x/r1", "r1", {})],
                principles=[Indiv("http://x/p1", "p1", {})],
                obligations=[Indiv("http://x/o1", "o1", {})],
            )


# ---------------------------------------------------------------------------
# RPOEdgeExtractor
# ---------------------------------------------------------------------------

ROLE = "http://proethica.org/ontology/case/1#Engineer_Role"
PRIN = "http://proethica.org/ontology/case/1#Public_Welfare_Principle"
OBL = "http://proethica.org/ontology/case/1#Report_Findings_Obligation"


class TestRPOEdgeExtractor:
    def _extractor(self, payload):
        from app.services.extraction.rpo_edges import RPOEdgeExtractor
        return RPOEdgeExtractor(
            llm_client=_make_mock_client_json(payload), model="claude-test-model"
        )

    def _inputs(self):
        from app.services.extraction.rpo_edges import Indiv
        return (
            [Indiv(ROLE, "Engineer", {})],
            [Indiv(PRIN, "Public Welfare", {})],
            [Indiv(OBL, "Report Findings", {})],
        )

    def test_emits_three_valid_edges(self):
        payload = {"edges": [
            {"predicate": "hasObligation", "subject_iri": ROLE,
             "object_iri": OBL, "source_text": "a", "confidence": 0.9},
            {"predicate": "adheresToPrinciple", "subject_iri": ROLE,
             "object_iri": PRIN, "source_text": "b", "confidence": 0.8},
            {"predicate": "derivedFromPrinciple", "subject_iri": OBL,
             "object_iri": PRIN, "source_text": "c", "confidence": 0.7},
        ]}
        roles, principles, obligations = self._inputs()
        edges = self._extractor(payload).extract(1, roles, principles, obligations)
        by_pred = {e["predicate"]: e for e in edges}
        assert set(by_pred) == {"hasObligation", "adheresToPrinciple", "derivedFromPrinciple"}
        assert by_pred["hasObligation"]["subject_iri"] == ROLE
        assert by_pred["hasObligation"]["object_iri"] == OBL
        assert by_pred["derivedFromPrinciple"]["confidence"] == pytest.approx(0.7)

    def test_drops_endpoint_category_violation(self):
        # hasObligation requires a Role subject; a Principle subject is dropped.
        payload = {"edges": [
            {"predicate": "hasObligation", "subject_iri": PRIN,
             "object_iri": OBL, "source_text": "bad", "confidence": 0.9},
            {"predicate": "adheresToPrinciple", "subject_iri": ROLE,
             "object_iri": PRIN, "source_text": "ok", "confidence": 0.8},
        ]}
        roles, principles, obligations = self._inputs()
        edges = self._extractor(payload).extract(1, roles, principles, obligations)
        assert len(edges) == 1
        assert edges[0]["predicate"] == "adheresToPrinciple"

    def test_dedupes_repeated_triple(self):
        payload = {"edges": [
            {"predicate": "hasObligation", "subject_iri": ROLE,
             "object_iri": OBL, "source_text": "first", "confidence": 0.9},
            {"predicate": "hasObligation", "subject_iri": ROLE,
             "object_iri": OBL, "source_text": "second", "confidence": 0.5},
        ]}
        roles, principles, obligations = self._inputs()
        edges = self._extractor(payload).extract(1, roles, principles, obligations)
        assert len(edges) == 1

    def test_strips_angle_brackets_on_iris(self):
        payload = {"edges": [
            {"predicate": "hasObligation", "subject_iri": f"<{ROLE}>",
             "object_iri": f"  {OBL} ", "source_text": "a", "confidence": 0.9},
        ]}
        roles, principles, obligations = self._inputs()
        edges = self._extractor(payload).extract(1, roles, principles, obligations)
        assert len(edges) == 1
        assert edges[0]["subject_iri"] == ROLE
        assert edges[0]["object_iri"] == OBL

    def test_empty_when_no_roles(self):
        from app.services.extraction.rpo_edges import RPOEdgeExtractor
        client = _make_mock_client_json({"edges": []})
        extractor = RPOEdgeExtractor(llm_client=client, model="claude-test-model")
        edges = extractor.extract(1, roles=[], principles=[], obligations=[])
        assert edges == []
        client.messages.stream.assert_not_called()

    def test_recovers_truncated_edges(self):
        truncated = (
            '{"edges": [\n'
            f'  {{"predicate": "hasObligation", "subject_iri": "{ROLE}", '
            f'"object_iri": "{OBL}", "source_text": "first", "confidence": 0.9}},\n'
            f'  {{"predicate": "adheresToPrinciple", "subject_iri": "{ROLE}", '
            f'"object_iri": "{PRIN}", "source_text": "cut off mid'
            # no closing quote/brace/array
        )
        from app.services.extraction.rpo_edges import RPOEdgeExtractor
        extractor = RPOEdgeExtractor(
            llm_client=_make_mock_client_raw_text(truncated, stop_reason="max_tokens"),
            model="claude-test-model",
        )
        roles, principles, obligations = self._inputs()
        edges = extractor.extract(1, roles, principles, obligations)
        # Only the first complete edge survives; the truncated second is lost.
        assert len(edges) == 1
        assert edges[0]["predicate"] == "hasObligation"


# ---------------------------------------------------------------------------
# TemporalSequenceExtractor
# ---------------------------------------------------------------------------

E1 = "http://proethica.org/ontology/case/1#Action_Submit_Report"
E2 = "http://proethica.org/ontology/case/1#Event_Discharge_Detected"


class _StubTemporalTemplate:
    """Stand-in for the editable temporal_sequence template so these tests need no DB / app context.
    The mock client ignores the prompt text, so minimal render/render_system suffice."""
    def render(self, **kw):
        return "USER\n" + kw.get("items", "")

    def render_system(self, **kw):
        return "SYSTEM"


class TestTemporalSequenceExtractor:
    @pytest.fixture(autouse=True)
    def _stub_template(self, monkeypatch):
        import app.services.extraction.temporal_sequence as ts
        monkeypatch.setattr(ts, "_load_temporal_template", lambda: _StubTemporalTemplate())

    def _entries(self):
        from app.services.extraction.temporal_sequence import TemporalEntryContext
        return [
            TemporalEntryContext(iri=E1, kind="Action", label="Submit report",
                                 temporal_marker="after", description="d1"),
            TemporalEntryContext(iri=E2, kind="Event", label="Discharge detected",
                                 temporal_marker="before", description="d2"),
        ]

    def test_returns_permutation(self):
        from app.services.extraction.temporal_sequence import TemporalSequenceExtractor
        client = _make_mock_client_json({"ordered_iris": [E2, E1], "rationale": "discharge first"})
        extractor = TemporalSequenceExtractor(llm_client=client, model="claude-test-model")
        result = extractor.extract(case_id=1, entries=self._entries())
        assert result.ordered_iris == [E2, E1]

    def test_empty_entries_skips_llm(self):
        from app.services.extraction.temporal_sequence import TemporalSequenceExtractor
        client = _make_mock_client_json({"ordered_iris": []})
        extractor = TemporalSequenceExtractor(llm_client=client, model="claude-test-model")
        result = extractor.extract(case_id=1, entries=[])
        assert result.ordered_iris == []
        client.messages.stream.assert_not_called()

    def test_non_permutation_rejected(self):
        from app.services.extraction.temporal_sequence import TemporalSequenceExtractor
        # Drops E1 -> not a permutation of the two inputs.
        client = _make_mock_client_json({"ordered_iris": [E2], "rationale": "x"})
        extractor = TemporalSequenceExtractor(llm_client=client, model="claude-test-model")
        with pytest.raises(ValueError):
            extractor.extract(case_id=1, entries=self._entries())

    def test_empty_response_raises(self):
        from app.services.extraction.temporal_sequence import TemporalSequenceExtractor
        client = _make_mock_client_raw_text("")
        extractor = TemporalSequenceExtractor(llm_client=client, model="claude-test-model")
        with pytest.raises(RuntimeError):
            extractor.extract(case_id=1, entries=self._entries())

    def test_uses_default_tier_not_powerful(self):
        from app.services.extraction.temporal_sequence import TemporalSequenceExtractor
        from model_config import ModelConfig
        extractor = TemporalSequenceExtractor()
        assert extractor._resolve_model() == ModelConfig.get_default_model()
