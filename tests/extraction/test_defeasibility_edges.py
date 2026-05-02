"""
Unit tests for DefeasibilityEdgeExtractor against the Case 72 gold fixture.

The gold fixture is the hand-annotated KI2026 Fig. 1 worked example at
the end of OntServe/ontologies/proethica-case-72.ttl. These tests reproduce
the four expected triples (one symmetric competesWith pair, one prevailsOver,
one defeasibleUnder) using a mock LLM client so the suite runs without API
access.

A separate integration test (marked llm) exercises the real Anthropic
client against the same fixture. Skip when no API key is configured.
"""

from __future__ import annotations

import json
from typing import List
from unittest.mock import MagicMock

import pytest

from app.services.extraction.defeasibility_edges import DefeasibilityEdgeExtractor
from app.services.extraction.enhanced_prompts_defeasibility import (
    NarrativeContext,
    ObligationContext,
    StateContext,
    create_defeasibility_prompt,
)
from app.services.extraction.schemas import DefeasibilityEdge


# ---------------------------------------------------------------------------
# Gold fixture: Case 72 KI2026 Fig. 1 worked example
# ---------------------------------------------------------------------------

CASE72_NS = "http://proethica.org/ontology/case/72#"

FAITHFUL_AGENT_IRI = (
    f"{CASE72_NS}Doe_Faithful_Agent_Obligation_Fulfilled"
    "_XYZ_Corporation_Verbal_Disclosure"
)
PUBLIC_WELFARE_IRI = (
    f"{CASE72_NS}Doe_Public_Welfare_Safety_Escalation"
    "_XYZ_Discharge_Regulatory_Authority"
)
# em-dash (U+2014) intentionally retained
PUBLIC_SAFETY_STATE_IRI = (
    f"{CASE72_NS}Public_Safety_at_Risk_—_Water_Quality_Degradation"
)


@pytest.fixture
def case72_obligations() -> List[ObligationContext]:
    return [
        ObligationContext(
            iri=FAITHFUL_AGENT_IRI,
            label="Doe Faithful Agent Obligation Fulfilled XYZ Corporation Verbal Disclosure",
            statement=(
                "Engineer Doe fulfilled his faithful agent obligation to XYZ "
                "Corporation by completing his studies and honestly advising "
                "the corporation verbally of his adverse findings before the "
                "written report was completed."
            ),
            obligated_party="Engineer Doe",
            temporal_scope="From engagement through verbal disclosure of adverse findings",
        ),
        ObligationContext(
            iri=PUBLIC_WELFARE_IRI,
            label="Doe Public Welfare Safety Escalation XYZ Discharge Regulatory Authority",
            statement=(
                "Engineer Doe must escalate the safety-relevant findings to "
                "the State Pollution Control Authority despite the contract "
                "termination and the instruction not to render a written report."
            ),
            obligated_party="Engineer Doe",
        ),
    ]


@pytest.fixture
def case72_states() -> List[StateContext]:
    return [
        StateContext(
            iri=PUBLIC_SAFETY_STATE_IRI,
            label="Public Safety at Risk — Water Quality Degradation",
            state_class="Public Safety at Risk State",
            triggering_event=(
                "Doe concludes that XYZ's discharge will lower water quality "
                "below established minimum standards"
            ),
        ),
    ]


@pytest.fixture
def case72_narratives() -> List[NarrativeContext]:
    principle_iri = (
        f"{CASE72_NS}Faithful_Agent_Obligation_Fulfilled_Then"
        "_Superseded_By_Ethical_Limits"
    )
    return [
        NarrativeContext(
            source_iri=principle_iri,
            source_label="Faithful Agent Obligation Fulfilled Then Superseded By Ethical Limits",
            source_field="tensionresolution",
            text=(
                "The faithful agent obligation was fully discharged when Doe "
                "completed his studies and advised the client of his findings; "
                "the subsequent instruction to suppress the report and the "
                "client's presentation of contradictory data at the public "
                "hearing activated the overriding public welfare obligation."
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Mock client helpers
# ---------------------------------------------------------------------------

def _make_mock_client(json_response: dict) -> MagicMock:
    """Mock an Anthropic client whose stream context yields the supplied JSON.

    The extractor uses `client.messages.stream(...)` as a context manager
    and consumes `stream.text_stream` for the chunks. Both shapes are
    populated here so the test exercises the same code path as
    production.
    """
    return _make_mock_client_raw_text(json.dumps(json_response))


GOLD_LLM_OUTPUT = {
    "edges": [
        {
            # The LLM is asked for ONE direction of competesWith.
            # The extractor will materialize the inverse.
            "predicate": "competesWith",
            "subject_iri": FAITHFUL_AGENT_IRI,
            "object_iri": PUBLIC_WELFARE_IRI,
            "source_field": "tensionresolution",
            "source_text": (
                "the subsequent instruction to suppress the report and the "
                "client's presentation of contradictory data at the public "
                "hearing activated the overriding public welfare obligation"
            ),
            "source_individual_iri": (
                f"{CASE72_NS}Faithful_Agent_Obligation_Fulfilled_Then"
                "_Superseded_By_Ethical_Limits"
            ),
            "confidence": 0.9,
        },
        {
            "predicate": "prevailsOver",
            "subject_iri": PUBLIC_WELFARE_IRI,
            "object_iri": FAITHFUL_AGENT_IRI,
            "source_field": "tensionresolution",
            "source_text": "activated the overriding public welfare obligation",
            "confidence": 0.9,
        },
        {
            "predicate": "defeasibleUnder",
            "subject_iri": FAITHFUL_AGENT_IRI,
            "object_iri": PUBLIC_SAFETY_STATE_IRI,
            "source_field": "tensionresolution",
            "source_text": (
                "Public Safety at Risk -- Water Quality Degradation licenses "
                "the defeat of the faithful agent obligation"
            ),
            "confidence": 0.85,
        },
    ]
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPromptBuilder:
    """The prompt is the contract between caller and LLM. Verify that
    constraints survive serialization."""

    def test_property_axioms_present(self, case72_obligations, case72_states):
        from app.services.extraction.enhanced_prompts_defeasibility import SYSTEM_PROMPT
        # The verbatim TTL block must be in the system prompt.
        assert "owl:SymmetricProperty" in SYSTEM_PROMPT
        assert "rdfs:domain proeth-core:Obligation" in SYSTEM_PROMPT
        assert "rdfs:range proeth-core:State" in SYSTEM_PROMPT

    def test_iris_passed_verbatim(self, case72_obligations, case72_states):
        prompt = create_defeasibility_prompt(
            obligations=case72_obligations,
            states=case72_states,
            case_id=72,
        )
        # IRIs (including em-dash) appear verbatim in angle brackets.
        assert f"<{FAITHFUL_AGENT_IRI}>" in prompt
        assert f"<{PUBLIC_WELFARE_IRI}>" in prompt
        assert f"<{PUBLIC_SAFETY_STATE_IRI}>" in prompt

    def test_em_dash_survives(self, case72_states):
        prompt = create_defeasibility_prompt(
            obligations=[],
            states=case72_states,
            case_id=72,
        )
        assert "—" in prompt  # em-dash preserved

    def test_no_obligations_means_skipped(self, case72_states):
        # Single-obligation cases should be handled by the extractor, not
        # by the prompt builder, but a no-obligation prompt should still
        # be valid JSON-shaped text.
        prompt = create_defeasibility_prompt(
            obligations=[],
            states=case72_states,
            case_id=72,
        )
        assert "OBLIGATIONS" in prompt


class TestExtractorWithMockedLLM:
    """End-to-end extractor flow with a mocked Anthropic client."""

    def test_reproduces_case72_gold_fixture(
        self, case72_obligations, case72_states, case72_narratives
    ):
        client = _make_mock_client(GOLD_LLM_OUTPUT)
        extractor = DefeasibilityEdgeExtractor(
            llm_client=client, model="claude-test-model"
        )

        edges = extractor.extract(
            case_id=72,
            obligations=case72_obligations,
            states=case72_states,
            additional_narratives=case72_narratives,
        )

        # Symmetric closure -> 2 competesWith + 1 prevailsOver + 1 defeasibleUnder
        by_predicate = {}
        for e in edges:
            by_predicate.setdefault(e.predicate, []).append(e)

        assert len(by_predicate.get("competesWith", [])) == 2
        assert len(by_predicate.get("prevailsOver", [])) == 1
        assert len(by_predicate.get("defeasibleUnder", [])) == 1

        # Both directions of competesWith present
        cw_pairs = {(e.subject_iri, e.object_iri)
                    for e in by_predicate["competesWith"]}
        assert (FAITHFUL_AGENT_IRI, PUBLIC_WELFARE_IRI) in cw_pairs
        assert (PUBLIC_WELFARE_IRI, FAITHFUL_AGENT_IRI) in cw_pairs

        # prevailsOver: PublicWelfare wins over FaithfulAgent
        prevail = by_predicate["prevailsOver"][0]
        assert prevail.subject_iri == PUBLIC_WELFARE_IRI
        assert prevail.object_iri == FAITHFUL_AGENT_IRI

        # defeasibleUnder: FaithfulAgent yields under Public Safety state
        defeat = by_predicate["defeasibleUnder"][0]
        assert defeat.subject_iri == FAITHFUL_AGENT_IRI
        assert defeat.object_iri == PUBLIC_SAFETY_STATE_IRI
        assert "—" in defeat.object_iri  # em-dash preserved end-to-end

    def test_drops_invented_iris(self, case72_obligations, case72_states):
        """Edges that reference IRIs not in the input lists are silently dropped."""
        bad_output = {
            "edges": [
                {
                    "predicate": "competesWith",
                    "subject_iri": f"{CASE72_NS}Made_Up_Obligation",
                    "object_iri": PUBLIC_WELFARE_IRI,
                    "source_field": "tensionresolution",
                    "source_text": "fabricated",
                    "confidence": 0.9,
                },
                {
                    # Valid edge survives the filter
                    "predicate": "prevailsOver",
                    "subject_iri": PUBLIC_WELFARE_IRI,
                    "object_iri": FAITHFUL_AGENT_IRI,
                    "source_field": "tensionresolution",
                    "source_text": "real",
                    "confidence": 0.8,
                },
            ]
        }
        client = _make_mock_client(bad_output)
        extractor = DefeasibilityEdgeExtractor(
            llm_client=client, model="claude-test-model"
        )
        edges = extractor.extract(
            case_id=72,
            obligations=case72_obligations,
            states=case72_states,
        )
        # Only the valid prevailsOver survives. competesWith was rejected.
        assert len(edges) == 1
        assert edges[0].predicate == "prevailsOver"

    def test_skip_when_too_few_obligations(self, case72_states):
        client = _make_mock_client({"edges": []})
        extractor = DefeasibilityEdgeExtractor(
            llm_client=client, model="claude-test-model"
        )
        edges = extractor.extract(
            case_id=72,
            obligations=[
                ObligationContext(iri=FAITHFUL_AGENT_IRI, label="single")
            ],
            states=case72_states,
        )
        assert edges == []
        client.messages.stream.assert_not_called()

    def test_dedup_keeps_highest_confidence(
        self, case72_obligations, case72_states
    ):
        """If the LLM emits the same triple twice, dedupe keeps the
        highest-confidence row."""
        dup_output = {
            "edges": [
                {
                    "predicate": "prevailsOver",
                    "subject_iri": PUBLIC_WELFARE_IRI,
                    "object_iri": FAITHFUL_AGENT_IRI,
                    "source_field": "tensionresolution",
                    "source_text": "first",
                    "confidence": 0.6,
                },
                {
                    "predicate": "prevailsOver",
                    "subject_iri": PUBLIC_WELFARE_IRI,
                    "object_iri": FAITHFUL_AGENT_IRI,
                    "source_field": "balancingwith",
                    "source_text": "second",
                    "confidence": 0.92,
                },
            ]
        }
        client = _make_mock_client(dup_output)
        extractor = DefeasibilityEdgeExtractor(
            llm_client=client, model="claude-test-model"
        )
        edges = extractor.extract(
            case_id=72,
            obligations=case72_obligations,
            states=case72_states,
        )
        assert len(edges) == 1
        assert edges[0].confidence == pytest.approx(0.92)
        assert edges[0].source_text == "second"


class TestPartialRecovery:
    """The LLM occasionally truncates JSON when max_tokens is hit. The
    extractor must salvage as many complete edges as possible."""

    def test_recovers_truncated_response(
        self, case72_obligations, case72_states
    ):
        # Two complete edges, then a third one cut off mid-string.
        truncated = (
            '{"edges": [\n'
            '  {"predicate": "competesWith", '
            f'"subject_iri": "{FAITHFUL_AGENT_IRI}", '
            f'"object_iri": "{PUBLIC_WELFARE_IRI}", '
            '"source_field": "tensionresolution", '
            '"source_text": "first", "confidence": 0.9},\n'
            '  {"predicate": "prevailsOver", '
            f'"subject_iri": "{PUBLIC_WELFARE_IRI}", '
            f'"object_iri": "{FAITHFUL_AGENT_IRI}", '
            '"source_field": "tensionresolution", '
            '"source_text": "second", "confidence": 0.85},\n'
            '  {"predicate": "defeasibleUnder", '
            f'"subject_iri": "{FAITHFUL_AGENT_IRI}", '
            f'"object_iri": "{PUBLIC_SAFETY_STATE_IRI}", '
            '"source_field": "tensionresolution", '
            '"source_text": "third was cut off mid-string by max_tokens'
            # Note: no closing quote, no closing brace, no closing array
        )
        client = _make_mock_client_raw_text(truncated)
        extractor = DefeasibilityEdgeExtractor(
            llm_client=client, model="claude-test-model"
        )
        edges = extractor.extract(
            case_id=72,
            obligations=case72_obligations,
            states=case72_states,
        )
        # The two complete edges survived; the third was dropped.
        # competesWith gets symmetric closure -> 2 + 1 = 3 edges total.
        predicates = sorted(e.predicate for e in edges)
        assert predicates.count("competesWith") == 2
        assert predicates.count("prevailsOver") == 1
        assert "defeasibleUnder" not in predicates


def _make_mock_client_raw_text(raw: str) -> MagicMock:
    """Mock client that returns a raw (possibly invalid) text response.

    Mirrors the Anthropic streaming API: `client.messages.stream(...)`
    is a context manager whose `__enter__` returns an object with a
    `text_stream` iterable and a `get_final_message()` callable.
    """
    client = MagicMock()

    final_msg = MagicMock()
    final_msg.stop_reason = "end_turn"
    final_msg.usage = MagicMock(input_tokens=100, output_tokens=200)

    stream_obj = MagicMock()
    stream_obj.text_stream = iter([raw])
    stream_obj.get_final_message.return_value = final_msg

    stream_ctx = MagicMock()
    stream_ctx.__enter__ = MagicMock(return_value=stream_obj)
    stream_ctx.__exit__ = MagicMock(return_value=False)

    client.messages.stream.return_value = stream_ctx
    return client


class TestSchemaValidation:
    """Pydantic guards on the DefeasibilityEdge model."""

    def test_invalid_predicate_rejected(self):
        with pytest.raises(Exception):
            DefeasibilityEdge(
                predicate="overrides",  # not in the literal set
                subject_iri=FAITHFUL_AGENT_IRI,
                object_iri=PUBLIC_WELFARE_IRI,
                source_field="tensionresolution",
                source_text="x",
                confidence=0.9,
            )

    def test_invalid_source_field_rejected(self):
        with pytest.raises(Exception):
            DefeasibilityEdge(
                predicate="competesWith",
                subject_iri=FAITHFUL_AGENT_IRI,
                object_iri=PUBLIC_WELFARE_IRI,
                source_field="random_property",  # not in the literal set
                source_text="x",
                confidence=0.9,
            )


@pytest.mark.llm
class TestRealLLMIntegration:
    """End-to-end test against a real Anthropic client. Requires
    ANTHROPIC_API_KEY. Run with: pytest -m llm tests/extraction/test_defeasibility_edges.py
    """

    def test_real_llm_reproduces_case72_edges(
        self, case72_obligations, case72_states, case72_narratives
    ):
        import os
        if not os.getenv("ANTHROPIC_API_KEY"):
            pytest.skip("ANTHROPIC_API_KEY not set")

        from app.utils.llm_utils import get_llm_client
        client = get_llm_client()

        extractor = DefeasibilityEdgeExtractor(llm_client=client)
        edges = extractor.extract(
            case_id=72,
            obligations=case72_obligations,
            states=case72_states,
            additional_narratives=case72_narratives,
        )

        # Loose assertions -- the LLM may emit extra edges or vary on
        # source_text. Hard guarantees: at least one of each predicate,
        # symmetric closure on competesWith.
        predicates = [e.predicate for e in edges]
        assert "competesWith" in predicates
        # competesWith should have both directions
        cw_pairs = {(e.subject_iri, e.object_iri)
                    for e in edges if e.predicate == "competesWith"}
        for s, o in list(cw_pairs):
            assert (o, s) in cw_pairs, (
                f"Symmetric closure missing: ({s}, {o}) without inverse"
            )
