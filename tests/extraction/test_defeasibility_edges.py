"""
Unit tests for DefeasibilityEdgeExtractor against a hand-annotated gold fixture.

The gold fixture is NSPE BER Case 76-4 (internal "case 72"), the original
hand-annotated defeasibility worked example: one symmetric competesWith pair,
one prevailsOver, one defeasibleUnder. These tests reproduce those triples with
a mock LLM client so the suite runs without API access. The case is a stable
gold input for exercising the extractor and is independent of which case the
paper draws.

Note: the KI2026 paper's Figure 1 worked example was moved to the current-Code
NSPE BER Case 04-8 (internal "case 86") -- see
OntServe/tests/integration/test_case_86_figure1.py. This extractor test was not
repointed, because Case 76-4's edges are hand-curated whereas Case 86's were
machine-extracted by the backfill, so Case 76-4 remains the better gold set for
testing the extractor itself.

A separate integration test (marked llm) exercises the real Anthropic client
against the same fixture. Skip when no API key is configured.
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


# Defeasibility now renders its prompt from the editable 'defeasibility_edges' DB template. The stub
# below keeps the OBLIGATIONS/STATES headers + the entity blocks so the prompt-content assertions in
# TestPromptBuilder stay meaningful; full-prompt fidelity is proven by the golden-diff verification,
# not by these unit tests.
_STUB_DEF_USER = (
    "Extract proethica-core v2.5.0 defeasibility edges from {{ case_tag }}.\n\n"
    "OBLIGATIONS (eligible for subject_iri and object_iri on competesWith / prevailsOver, and "
    "subject_iri on defeasibleUnder):\n{{ obligations_block }}\n\n"
    "STATES (eligible for object_iri on defeasibleUnder):\n{{ states_block }}\n\n"
    "ADDITIONAL NARRATIVE CONTEXT:\n{{ narratives_block }}\n"
)
_STUB_DEF_SYS = "SYSTEM\n{{ property_axioms_block }}"


@pytest.fixture(autouse=True)
def _stub_def_template(monkeypatch):
    """Stub the 'defeasibility_edges' template loader with an in-memory ExtractionPromptTemplate (which
    uses the real render/render_system code paths) so these tests need no DB / app context."""
    from app.models.extraction_prompt_template import ExtractionPromptTemplate
    import app.services.extraction.enhanced_prompts_defeasibility as defp
    monkeypatch.setattr(
        defp, "_load_defeasibility_template",
        lambda: ExtractionPromptTemplate(template_text=_STUB_DEF_USER, system_prompt=_STUB_DEF_SYS))


# ---------------------------------------------------------------------------
# Gold fixture: hand-annotated Case 76-4 (internal "case 72") defeasibility example
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
        from app.services.extraction.enhanced_prompts_defeasibility import property_axioms_block
        # The TTL block injected into the system prompt as {{ property_axioms_block }},
        # parsed live from proethica-core.ttl so it cannot drift (the hard-coded
        # predecessor omitted the prevailsOver characteristics).
        block = property_axioms_block()
        assert "owl:SymmetricProperty" in block
        assert "owl:AsymmetricProperty" in block
        assert "owl:IrreflexiveProperty" in block
        assert "rdfs:domain proeth-core:Obligation" in block
        assert "rdfs:range proeth-core:State" in block

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


class TestRun21ZeroYield:
    """Run-21 F2a regression suite: the extractor rode the powerful tier and
    returned a clean, well-formed empty edge list ({"edges": []}) while the
    lowercase-only narrative harvest starved the prompt of 14 of the 22
    available fragments. These tests lock the three fixes: the default-tier
    model assignment, the two-spelling harvest, and the zero-edge
    diagnostics/persistence."""

    def test_wellformed_empty_edges_is_clean_zero(
        self, case72_obligations, case72_states
    ):
        """Run 21's exact zero-yield shape: {"edges": []} parses cleanly,
        yields no edges, and leaves the raw response inspectable."""
        client = _make_mock_client_raw_text('{"edges": []}')
        extractor = DefeasibilityEdgeExtractor(
            llm_client=client, model="claude-test-model"
        )
        edges = extractor.extract(
            case_id=7,
            obligations=case72_obligations,
            states=case72_states,
        )
        assert edges == []
        assert extractor.last_raw_response == '{"edges": []}'

    def test_default_model_is_default_tier(self):
        """The ratified model split places the defeasibility extractor on the
        DEFAULT tier; the base-class powerful-tier default is overridden."""
        from model_config import ModelConfig
        extractor = DefeasibilityEdgeExtractor(llm_client=MagicMock())
        assert extractor._resolve_model() == ModelConfig.get_claude_model("default")
        # An explicitly pinned model still wins.
        pinned = DefeasibilityEdgeExtractor(llm_client=MagicMock(), model="claude-pinned")
        assert pinned._resolve_model() == "claude-pinned"

    def test_parse_case_graph_harvests_both_predicate_spellings(self):
        """The committed TTLs emit camelCase proeth:concreteExpression /
        proeth:constraintStatement; the harvest reads both spellings, keeps
        the canonical lowercase source_field, and dedupes a value asserted
        under both spellings on the same subject."""
        from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
        from app.services.extraction.defeasibility_pipeline import (
            PROETH, PROETH_CORE, parse_case_graph,
        )
        case_ns = Namespace("http://proethica.org/ontology/case/7#")
        g = Graph()
        principle = case_ns["Principle_P"]
        g.add((principle, RDFS.label, Literal("Principle P")))
        g.add((principle, PROETH["interpretation"], Literal("interpretation fragment")))
        g.add((principle, PROETH["concreteExpression"], Literal("camelCase concrete expression")))
        # Same value under BOTH spellings -> one narrative, not two.
        g.add((principle, PROETH["concreteexpression"], Literal("camelCase concrete expression")))
        constraint = case_ns["Constraint_C"]
        g.add((constraint, RDFS.label, Literal("Constraint C")))
        g.add((constraint, PROETH["constraintStatement"], Literal("camelCase constraint statement")))

        ents = parse_case_graph(g, 7)
        by_field = {}
        for n in ents.narratives:
            by_field.setdefault(n.source_field, []).append(n.text)
        assert by_field == {
            "interpretation": ["interpretation fragment"],
            "concreteexpression": ["camelCase concrete expression"],
            "constraintstatement": ["camelCase constraint statement"],
        }
        # Every harvested source_field is valid for the DefeasibilityEdge Literal.
        valid_fields = {"tensionresolution", "balancingwith", "interpretation",
                        "concreteexpression", "constraintstatement"}
        assert {n.source_field for n in ents.narratives} <= valid_fields

    _TTL_TWO_OBLIGATIONS = """\
@prefix proeth-core: <http://proethica.org/ontology/core#> .
@prefix proeth: <http://proethica.org/ontology/intermediate#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix case: <http://proethica.org/ontology/case/7#> .

case:Obl_A a proeth-core:Obligation ;
    rdfs:label "Obligation A" ;
    proeth:obligationStatement "A must do X." .

case:Obl_B a proeth-core:Obligation ;
    rdfs:label "Obligation B" .

case:Principle_P a proeth-core:Principle ;
    rdfs:label "Principle P" ;
    proeth:interpretation "lowercase-spelling fragment" ;
    proeth:concreteExpression "camelCase concrete expression fragment" .

case:Constraint_C a proeth-core:Constraint ;
    rdfs:label "Constraint C" ;
    proeth:constraintStatement "camelCase constraint statement fragment" .
"""

    class _StubExtractor:
        """Duck-typed extractor: fixed edge list, recorded prompt/response."""
        def __init__(self, edges, raw='{"edges": []}'):
            self._edges = edges
            self.last_raw_response = raw
            self.last_prompt = "STUB PROMPT"

        def extract(self, **_kw):
            return self._edges

        def _resolve_model(self):
            return "claude-stub-model"

    def _patched_save_prompt(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "app.models.extraction_prompt.ExtractionPrompt.save_prompt",
            classmethod(lambda _cls, **kw: calls.append(kw)),
        )
        return calls

    def test_zero_edges_logs_raw_response_and_persists(
        self, tmp_path, monkeypatch, caplog
    ):
        """A zero-edge run now leaves two diagnostics: a WARNING carrying the
        (truncated) raw response, and an extraction_prompts record
        (concept_type='defeasibility_edges') with prompt + raw response."""
        import logging
        from app.services.extraction.defeasibility_pipeline import (
            apply_defeasibility_edges,
        )
        ttl = tmp_path / "proethica-case-7.ttl"
        ttl.write_text(self._TTL_TWO_OBLIGATIONS, encoding="utf-8")
        calls = self._patched_save_prompt(monkeypatch)

        with caplog.at_level(
            logging.WARNING,
            logger="app.services.extraction.defeasibility_pipeline",
        ):
            res = apply_defeasibility_edges(
                7, ttl, extractor=self._StubExtractor([]), write_back=False,
            )

        assert res["status"] == "no_edges"
        # The two-spelling harvest fed all 3 fragments (1 lowercase + 2 camelCase).
        assert res["narratives"] == 3
        zero_warnings = [r for r in caplog.records if "ZERO edges" in r.getMessage()]
        assert len(zero_warnings) == 1
        assert '{"edges": []}' in zero_warnings[0].getMessage()
        assert len(calls) == 1
        kw = calls[0]
        assert kw["case_id"] == 7
        assert kw["concept_type"] == "defeasibility_edges"
        assert kw["prompt_text"] == "STUB PROMPT"
        assert kw["raw_response"] == '{"edges": []}'
        assert kw["llm_model"] == "claude-stub-model"
        assert kw["results_summary"] == {"edges_emitted": 0}

    def test_nonzero_edges_also_persist_without_zero_warning(
        self, tmp_path, monkeypatch, caplog
    ):
        import logging
        from app.services.extraction.defeasibility_pipeline import (
            apply_defeasibility_edges,
        )
        ttl = tmp_path / "proethica-case-7.ttl"
        ttl.write_text(self._TTL_TWO_OBLIGATIONS, encoding="utf-8")
        calls = self._patched_save_prompt(monkeypatch)
        case_ns = "http://proethica.org/ontology/case/7#"
        edge = DefeasibilityEdge(
            predicate="prevailsOver",
            subject_iri=f"{case_ns}Obl_A",
            object_iri=f"{case_ns}Obl_B",
            source_field="interpretation",
            source_text="A prevails",
            confidence=0.8,
        )

        with caplog.at_level(
            logging.WARNING,
            logger="app.services.extraction.defeasibility_pipeline",
        ):
            res = apply_defeasibility_edges(
                7, ttl, extractor=self._StubExtractor([edge], raw='{"edges": [...]}'),
                write_back=False,
            )

        assert res["status"] == "ok"
        assert res["edges_emitted"] == 1
        assert res["narratives"] == 3
        assert not [r for r in caplog.records if "ZERO edges" in r.getMessage()]
        assert len(calls) == 1
        assert calls[0]["results_summary"] == {"edges_emitted": 1}

    def test_persistence_failure_never_fails_the_applier(
        self, tmp_path, monkeypatch
    ):
        """Best-effort contract: a DB failure in the persistence hook is
        logged, not raised (the applier runs in the commit path and in
        standalone replays without an app context)."""
        from app.services.extraction.defeasibility_pipeline import (
            apply_defeasibility_edges,
        )
        ttl = tmp_path / "proethica-case-7.ttl"
        ttl.write_text(self._TTL_TWO_OBLIGATIONS, encoding="utf-8")

        def _boom(_cls, **_kw):
            raise RuntimeError("no app context")

        monkeypatch.setattr(
            "app.models.extraction_prompt.ExtractionPrompt.save_prompt",
            classmethod(_boom),
        )
        res = apply_defeasibility_edges(
            7, ttl, extractor=self._StubExtractor([]), write_back=False,
        )
        assert res["status"] == "no_edges"

    def test_seed_template_carries_decision_rubric_and_no_fabrication(self):
        """The editable template's decision rubric (worked competition/defeat
        example grounded in narrative fields) is present, and the
        no-fabrication posture is retained in both prompts."""
        import importlib.util
        from pathlib import Path
        seed_path = (
            Path(__file__).resolve().parents[2]
            / "docs-internal/scripts/seed_defeasibility_edges_template.py"
        )
        spec = importlib.util.spec_from_file_location("seed_def_tmpl", seed_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert "DECISION RUBRIC" in mod.TEMPLATE_TEXT
        assert "empty edges array ONLY" in mod.TEMPLATE_TEXT
        # Worked example maps narrative wording to all three predicates.
        assert "competesWith" in mod.TEMPLATE_TEXT
        assert "prevailsOver" in mod.TEMPLATE_TEXT
        assert "defeasibleUnder" in mod.TEMPLATE_TEXT
        # No-fabrication posture retained.
        assert "Do NOT invent edges" in mod.TEMPLATE_TEXT
        assert "verbatim source_text" in mod.SYSTEM_TEXT


@pytest.mark.llm
class TestRealLLMIntegration:
    """End-to-end test against a real Anthropic client. Requires
    ANTHROPIC_API_KEY. Run with: pytest -m llm tests/extraction/test_defeasibility_edges.py
    """

    @pytest.fixture(autouse=True)
    def _flask_app_context(self):
        """``get_llm_client`` reads ``current_app.config``; provide a context."""
        from app import create_app
        app = create_app("development")
        with app.app_context():
            yield

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


class TestJointEmission:
    """Joint-emission invariant (2026-07-08 defeasibility view review):
    defeasibleUnder presupposes a competing obligation (the core property
    definition says the State renders the obligation subject to override BY A
    COMPETING OBLIGATION), so a defeasibleUnder edge survives only when its
    subject participates in a competesWith or prevailsOver edge in the same
    extraction. Locks the guard that would have flagged the 9 of 15 gold
    cases carrying defeasibleUnder edges with no competition structure."""

    def _extract(self, output, case72_obligations, case72_states):
        client = _make_mock_client(output)
        extractor = DefeasibilityEdgeExtractor(
            llm_client=client, model="claude-test-model"
        )
        return extractor.extract(
            case_id=72,
            obligations=case72_obligations,
            states=case72_states,
        )

    def test_defeasible_under_alone_is_dropped(
        self, case72_obligations, case72_states
    ):
        output = {
            "edges": [
                {
                    "predicate": "defeasibleUnder",
                    "subject_iri": FAITHFUL_AGENT_IRI,
                    "object_iri": PUBLIC_SAFETY_STATE_IRI,
                    "source_field": "tensionresolution",
                    "source_text": "yields under risk",
                    "confidence": 0.8,
                },
            ]
        }
        assert self._extract(output, case72_obligations, case72_states) == []

    def test_defeasible_under_with_named_competitor_is_kept(
        self, case72_obligations, case72_states
    ):
        output = {
            "edges": [
                {
                    "predicate": "competesWith",
                    "subject_iri": FAITHFUL_AGENT_IRI,
                    "object_iri": PUBLIC_WELFARE_IRI,
                    "source_field": "tensionresolution",
                    "source_text": "the two duties stand in tension",
                    "confidence": 0.9,
                },
                {
                    "predicate": "defeasibleUnder",
                    "subject_iri": FAITHFUL_AGENT_IRI,
                    "object_iri": PUBLIC_SAFETY_STATE_IRI,
                    "source_field": "tensionresolution",
                    "source_text": "yields under risk",
                    "confidence": 0.8,
                },
            ]
        }
        edges = self._extract(output, case72_obligations, case72_states)
        by_pred = {}
        for e in edges:
            by_pred.setdefault(e.predicate, []).append(e)
        # competesWith closed symmetrically; the grounded defeasibleUnder kept.
        assert len(by_pred["competesWith"]) == 2
        assert len(by_pred["defeasibleUnder"]) == 1

    def test_prevails_over_participation_grounds_defeasible_under(
        self, case72_obligations, case72_states
    ):
        output = {
            "edges": [
                {
                    "predicate": "prevailsOver",
                    "subject_iri": PUBLIC_WELFARE_IRI,
                    "object_iri": FAITHFUL_AGENT_IRI,
                    "source_field": "tensionresolution",
                    "source_text": "the overriding public welfare obligation",
                    "confidence": 0.9,
                },
                {
                    "predicate": "defeasibleUnder",
                    "subject_iri": FAITHFUL_AGENT_IRI,
                    "object_iri": PUBLIC_SAFETY_STATE_IRI,
                    "source_field": "tensionresolution",
                    "source_text": "yields under risk",
                    "confidence": 0.8,
                },
            ]
        }
        edges = self._extract(output, case72_obligations, case72_states)
        preds = sorted(e.predicate for e in edges)
        assert preds == ["defeasibleUnder", "prevailsOver"]
