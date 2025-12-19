"""
Unit tests for Case Synthesizer Service.

Tests the unified synthesis pipeline that:
1. Gathers entities from Passes 1-3 (Entity Foundation)
2. Loads analytical extraction from Parts A-D
3. Synthesizes decision points using E1-E3 + LLM refinement
4. Constructs narrative elements

These tests use mocks to avoid database and LLM dependencies.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from dataclasses import asdict

from app.services.case_synthesizer import (
    EntitySummary,
    EntityFoundation,
    TimelineEvent,
    ScenarioSeeds,
    CaseNarrative,
    LLMTrace,
    CausalNormativeLink,
    QuestionEmergenceAnalysis,
    ResolutionPatternAnalysis,
    TransformationAnalysis,
    CaseSynthesisModel
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def entity_summary():
    """Sample entity summary."""
    return EntitySummary(
        uri="case-7#Engineer_A",
        label="Engineer A",
        definition="Licensed professional engineer",
        entity_type="Roles"
    )


@pytest.fixture
def entity_foundation():
    """Sample entity foundation with all entity types."""
    return EntityFoundation(
        roles=[
            EntitySummary(uri="case-7#Engineer_A", label="Engineer A", definition="PE", entity_type="Roles"),
            EntitySummary(uri="case-7#Client_W", label="Client W", definition="Client", entity_type="Roles")
        ],
        states=[
            EntitySummary(uri="case-7#AI_In_Use", label="AI In Use", definition="AI tools active", entity_type="States")
        ],
        resources=[
            EntitySummary(uri="case-7#AI_Software", label="AI Software", definition="AI tool", entity_type="Resources")
        ],
        principles=[
            EntitySummary(uri="case-7#Transparency", label="Transparency", definition="Be transparent", entity_type="Principles")
        ],
        obligations=[
            EntitySummary(uri="case-7#Disclosure_Obl", label="Disclosure Obligation", definition="Must disclose", entity_type="Obligations")
        ],
        constraints=[
            EntitySummary(uri="case-7#Competence_Constraint", label="Competence Constraint", definition="Must be competent", entity_type="Constraints")
        ],
        capabilities=[],
        actions=[
            EntitySummary(uri="case-7#Adopt_AI", label="Adopt AI", definition="Decision to use AI", entity_type="Actions")
        ],
        events=[
            EntitySummary(uri="case-7#Discovery", label="Quality Discovery", definition="Found issues", entity_type="Events")
        ]
    )


@pytest.fixture
def timeline_event():
    """Sample timeline event."""
    return TimelineEvent(
        sequence=1,
        phase_label="Action Phase",
        description="Engineer A decides to use AI tools",
        entity_uris=["case-7#Adopt_AI"],
        entity_labels=["Adopt AI"],
        event_type="action"
    )


@pytest.fixture
def scenario_seeds():
    """Sample scenario seeds."""
    return ScenarioSeeds(
        protagonist="Engineer A",
        protagonist_uri="case-7#Engineer_A",
        setting="Environmental engineering consulting firm",
        inciting_incident="Engineer B retires, leaving Engineer A without mentorship",
        key_tensions=["Disclosure vs Efficiency", "Competence vs Time Pressure"],
        resolution_path="Board determined disclosure was required"
    )


@pytest.fixture
def llm_trace():
    """Sample LLM trace."""
    return LLMTrace(
        phase=2,
        phase_name="Analytical Extraction",
        stage="provisions",
        prompt="Extract code provisions from the text...",
        response='{"provisions": [...]}',
        model="claude-3-sonnet"
    )


@pytest.fixture
def causal_normative_link():
    """Sample causal-normative link."""
    return CausalNormativeLink(
        action_id="case-7#Adopt_AI",
        action_label="Adopt AI Software",
        fulfills_obligations=["case-7#Efficiency_Obl"],
        violates_obligations=["case-7#Competence_Obl"],
        guided_by_principles=["case-7#Technological_Prudence"],
        constrained_by=["case-7#Safety_Constraint"],
        agent_role="Engineer A",
        reasoning="Engineer A used AI without full competence",
        confidence=0.85
    )


@pytest.fixture
def question_emergence():
    """Sample question emergence analysis."""
    return QuestionEmergenceAnalysis(
        question_uri="case-7#Q1",
        question_text="Was Engineer A's use of AI ethical?",
        data_events=["case-7#Discovery"],
        data_actions=["case-7#Adopt_AI"],
        involves_roles=["case-7#Engineer_A", "case-7#Client_W"],
        competing_warrants=[("Disclosure_Obl", "Efficiency_Principle")],
        data_warrant_tension="AI use triggers both disclosure and efficiency warrants",
        competing_claims="Disclose vs proceed without disclosure",
        rebuttal_conditions="If client explicitly waived disclosure",
        emergence_narrative="The question emerged due to tension between transparency and efficiency",
        confidence=0.9
    )


@pytest.fixture
def resolution_pattern():
    """Sample resolution pattern analysis."""
    return ResolutionPatternAnalysis(
        conclusion_uri="case-7#Conclusion_1",
        conclusion_text="Engineer A was not ethical in failing to disclose",
        answers_questions=["case-7#Q1"],
        determinative_principles=["Transparency", "Disclosure"],
        determinative_facts=["AI was used", "Client was not informed"],
        cited_provisions=["NSPE II.1.c"],
        weighing_process="Disclosure obligation outweighed efficiency concerns",
        resolution_narrative="The Board weighed transparency against efficiency",
        confidence=0.95
    )


@pytest.fixture
def transformation_analysis():
    """Sample transformation analysis."""
    return TransformationAnalysis(
        transformation_type="transfer",
        confidence=0.88,
        reasoning="Responsibility transferred from Engineer A to Board",
        pattern_description="Classic transfer pattern where individual ethics become institutional",
        evidence=["Board took over ethical determination", "Engineer deferred to institutional judgment"]
    )


# =============================================================================
# ENTITY SUMMARY TESTS
# =============================================================================

class TestEntitySummary:
    """Tests for EntitySummary dataclass."""

    def test_entity_summary_fields(self, entity_summary):
        """Test EntitySummary has all required fields."""
        assert entity_summary.uri == "case-7#Engineer_A"
        assert entity_summary.label == "Engineer A"
        assert entity_summary.definition == "Licensed professional engineer"
        assert entity_summary.entity_type == "Roles"

    def test_entity_summary_defaults(self):
        """Test EntitySummary has proper defaults."""
        summary = EntitySummary(uri="test", label="Test")
        assert summary.definition == ""
        assert summary.entity_type == ""


# =============================================================================
# ENTITY FOUNDATION TESTS
# =============================================================================

class TestEntityFoundation:
    """Tests for EntityFoundation dataclass."""

    def test_entity_foundation_summary(self, entity_foundation):
        """Test EntityFoundation provides correct summary counts."""
        summary = entity_foundation.summary()

        assert summary['pass1']['roles'] == 2
        assert summary['pass1']['states'] == 1
        assert summary['pass1']['resources'] == 1
        assert summary['pass1']['total'] == 4

        assert summary['pass2']['principles'] == 1
        assert summary['pass2']['obligations'] == 1
        assert summary['pass2']['constraints'] == 1
        assert summary['pass2']['total'] == 3

        assert summary['pass3']['actions'] == 1
        assert summary['pass3']['events'] == 1
        assert summary['pass3']['total'] == 2

        assert summary['total'] == 9

    def test_entity_foundation_to_dict(self, entity_foundation):
        """Test EntityFoundation serialization."""
        d = entity_foundation.to_dict()

        assert 'roles' in d
        assert 'states' in d
        assert 'resources' in d
        assert 'principles' in d
        assert 'obligations' in d
        assert 'constraints' in d
        assert 'capabilities' in d
        assert 'actions' in d
        assert 'events' in d
        assert 'summary' in d

    def test_entity_foundation_defaults(self):
        """Test EntityFoundation has empty defaults."""
        foundation = EntityFoundation()
        assert foundation.roles == []
        assert foundation.states == []
        assert foundation.resources == []
        assert foundation.role_obligation_bindings == []
        assert foundation.action_obligation_map == {}


# =============================================================================
# TIMELINE EVENT TESTS
# =============================================================================

class TestTimelineEvent:
    """Tests for TimelineEvent dataclass."""

    def test_timeline_event_fields(self, timeline_event):
        """Test TimelineEvent has all fields."""
        assert timeline_event.sequence == 1
        assert timeline_event.phase_label == "Action Phase"
        assert timeline_event.event_type == "action"
        assert len(timeline_event.entity_uris) == 1

    def test_timeline_event_to_dict(self, timeline_event):
        """Test TimelineEvent serialization."""
        d = timeline_event.to_dict()
        assert d['sequence'] == 1
        assert d['event_type'] == "action"

    def test_timeline_event_defaults(self):
        """Test TimelineEvent defaults."""
        event = TimelineEvent(
            sequence=1,
            phase_label="Test",
            description="Test event"
        )
        assert event.entity_uris == []
        assert event.entity_labels == []
        assert event.event_type == "event"


# =============================================================================
# SCENARIO SEEDS TESTS
# =============================================================================

class TestScenarioSeeds:
    """Tests for ScenarioSeeds dataclass."""

    def test_scenario_seeds_fields(self, scenario_seeds):
        """Test ScenarioSeeds has all fields."""
        assert scenario_seeds.protagonist == "Engineer A"
        assert "Environmental" in scenario_seeds.setting
        assert len(scenario_seeds.key_tensions) == 2

    def test_scenario_seeds_to_dict(self, scenario_seeds):
        """Test ScenarioSeeds serialization."""
        d = scenario_seeds.to_dict()
        assert 'protagonist' in d
        assert 'setting' in d
        assert 'inciting_incident' in d
        assert 'key_tensions' in d

    def test_scenario_seeds_defaults(self):
        """Test ScenarioSeeds defaults."""
        seeds = ScenarioSeeds(
            protagonist="Test",
            protagonist_uri="uri",
            setting="Setting",
            inciting_incident="Incident"
        )
        assert seeds.key_tensions == []
        assert seeds.resolution_path == ""


# =============================================================================
# CASE NARRATIVE TESTS
# =============================================================================

class TestCaseNarrative:
    """Tests for CaseNarrative dataclass."""

    def test_case_narrative_fields(self, timeline_event, scenario_seeds):
        """Test CaseNarrative structure."""
        narrative = CaseNarrative(
            case_summary="A case about AI ethics in engineering.",
            timeline=[timeline_event],
            scenario_seeds=scenario_seeds
        )
        assert len(narrative.timeline) == 1
        assert narrative.scenario_seeds is not None

    def test_case_narrative_to_dict(self, timeline_event, scenario_seeds):
        """Test CaseNarrative serialization."""
        narrative = CaseNarrative(
            case_summary="Summary",
            timeline=[timeline_event],
            scenario_seeds=scenario_seeds
        )
        d = narrative.to_dict()
        assert 'case_summary' in d
        assert 'timeline' in d
        assert 'scenario_seeds' in d

    def test_case_narrative_without_seeds(self, timeline_event):
        """Test CaseNarrative without scenario seeds."""
        narrative = CaseNarrative(
            case_summary="Summary",
            timeline=[timeline_event]
        )
        d = narrative.to_dict()
        assert d['scenario_seeds'] is None


# =============================================================================
# LLM TRACE TESTS
# =============================================================================

class TestLLMTrace:
    """Tests for LLMTrace dataclass."""

    def test_llm_trace_fields(self, llm_trace):
        """Test LLMTrace has all fields."""
        assert llm_trace.phase == 2
        assert llm_trace.phase_name == "Analytical Extraction"
        assert llm_trace.stage == "provisions"
        assert "claude" in llm_trace.model

    def test_llm_trace_truncates_long_content(self):
        """Test LLMTrace truncates long prompts/responses in to_dict."""
        long_content = "x" * 1000
        trace = LLMTrace(
            phase=1,
            phase_name="Test",
            stage="test",
            prompt=long_content,
            response=long_content,
            model="test"
        )
        d = trace.to_dict()
        assert len(d['prompt']) <= 503  # 500 + "..."
        assert len(d['response']) <= 503

    def test_llm_trace_timestamp(self, llm_trace):
        """Test LLMTrace has timestamp."""
        assert llm_trace.timestamp is not None
        d = llm_trace.to_dict()
        assert 'timestamp' in d


# =============================================================================
# CAUSAL NORMATIVE LINK TESTS
# =============================================================================

class TestCausalNormativeLink:
    """Tests for CausalNormativeLink dataclass."""

    def test_causal_link_fields(self, causal_normative_link):
        """Test CausalNormativeLink has all fields."""
        assert causal_normative_link.action_id == "case-7#Adopt_AI"
        assert len(causal_normative_link.fulfills_obligations) == 1
        assert len(causal_normative_link.violates_obligations) == 1
        assert causal_normative_link.confidence == 0.85

    def test_causal_link_to_dict(self, causal_normative_link):
        """Test CausalNormativeLink serialization."""
        d = causal_normative_link.to_dict()
        assert 'action_id' in d
        assert 'fulfills_obligations' in d
        assert 'violates_obligations' in d
        assert 'agent_role' in d


# =============================================================================
# QUESTION EMERGENCE ANALYSIS TESTS
# =============================================================================

class TestQuestionEmergenceAnalysis:
    """Tests for QuestionEmergenceAnalysis dataclass."""

    def test_question_emergence_fields(self, question_emergence):
        """Test QuestionEmergenceAnalysis Toulmin structure."""
        assert question_emergence.question_uri == "case-7#Q1"
        assert len(question_emergence.data_events) == 1
        assert len(question_emergence.data_actions) == 1
        assert len(question_emergence.competing_warrants) == 1
        assert question_emergence.data_warrant_tension != ""

    def test_question_emergence_to_dict(self, question_emergence):
        """Test QuestionEmergenceAnalysis serialization."""
        d = question_emergence.to_dict()
        assert 'question_uri' in d
        assert 'competing_warrants' in d
        # Tuples should be converted to lists
        assert isinstance(d['competing_warrants'][0], list)

    def test_question_emergence_defaults(self):
        """Test QuestionEmergenceAnalysis defaults."""
        analysis = QuestionEmergenceAnalysis(
            question_uri="q1",
            question_text="Test?"
        )
        assert analysis.data_events == []
        assert analysis.competing_warrants == []
        assert analysis.confidence == 0.0


# =============================================================================
# RESOLUTION PATTERN ANALYSIS TESTS
# =============================================================================

class TestResolutionPatternAnalysis:
    """Tests for ResolutionPatternAnalysis dataclass."""

    def test_resolution_pattern_fields(self, resolution_pattern):
        """Test ResolutionPatternAnalysis fields."""
        assert resolution_pattern.conclusion_uri == "case-7#Conclusion_1"
        assert len(resolution_pattern.determinative_principles) == 2
        assert len(resolution_pattern.cited_provisions) == 1
        assert resolution_pattern.weighing_process != ""

    def test_resolution_pattern_to_dict(self, resolution_pattern):
        """Test ResolutionPatternAnalysis serialization."""
        d = resolution_pattern.to_dict()
        assert 'conclusion_uri' in d
        assert 'weighing_process' in d
        assert 'determinative_facts' in d


# =============================================================================
# TRANSFORMATION ANALYSIS TESTS
# =============================================================================

class TestTransformationAnalysis:
    """Tests for TransformationAnalysis dataclass."""

    def test_transformation_analysis_fields(self, transformation_analysis):
        """Test TransformationAnalysis fields."""
        assert transformation_analysis.transformation_type == "transfer"
        assert transformation_analysis.confidence == 0.88
        assert len(transformation_analysis.evidence) == 2

    def test_transformation_analysis_to_dict(self, transformation_analysis):
        """Test TransformationAnalysis serialization."""
        d = transformation_analysis.to_dict()
        assert d['transformation_type'] == "transfer"
        assert 'pattern_description' in d


# =============================================================================
# CASE SYNTHESIS MODEL TESTS
# =============================================================================

class TestCaseSynthesisModel:
    """Tests for CaseSynthesisModel dataclass."""

    def test_synthesis_model_basic(self, entity_foundation, transformation_analysis):
        """Test CaseSynthesisModel basic construction."""
        model = CaseSynthesisModel(
            case_id=7,
            case_title="AI in Engineering Practice",
            entity_foundation=entity_foundation,
            transformation=transformation_analysis
        )
        assert model.case_id == 7
        assert model.entity_foundation is not None
        assert model.transformation_type == "transfer"

    def test_synthesis_model_summary(self, entity_foundation):
        """Test CaseSynthesisModel provides summary."""
        model = CaseSynthesisModel(
            case_id=7,
            case_title="Test Case",
            entity_foundation=entity_foundation,
            provisions=[{"code": "NSPE II.1"}],
            questions=[{"text": "Q1?"}],
            conclusions=[{"text": "C1"}]
        )
        # Model should have summary method
        summary = model.summary()
        assert 'entity_counts' in summary or summary is not None

    def test_synthesis_model_phases(self, entity_foundation, transformation_analysis, resolution_pattern, causal_normative_link):
        """Test CaseSynthesisModel contains all phases."""
        model = CaseSynthesisModel(
            case_id=7,
            case_title="Test",
            entity_foundation=entity_foundation,  # Phase 1
            provisions=[],  # Phase 2
            questions=[],
            conclusions=[],
            transformation=transformation_analysis,
            causal_normative_links=[causal_normative_link],  # Phase 2b
            resolution_patterns=[resolution_pattern],
            canonical_decision_points=[],  # Phase 3
            narrative=None  # Phase 4
        )
        assert model.entity_foundation is not None  # Phase 1
        assert model.transformation is not None  # Phase 2
        assert len(model.causal_normative_links) == 1  # Phase 2b

    def test_synthesis_model_defaults(self):
        """Test CaseSynthesisModel defaults."""
        model = CaseSynthesisModel(
            case_id=7,
            case_title="Test",
            entity_foundation=EntityFoundation()
        )
        assert model.provisions == []
        assert model.questions == []
        assert model.conclusions == []
        assert model.transformation is None
        assert model.causal_normative_links == []
        assert model.question_emergence == []
        assert model.resolution_patterns == []
        assert model.canonical_decision_points == []
        assert model.narrative is None
        assert model.llm_traces == []

    def test_synthesis_model_transformation_type_property(self, entity_foundation, transformation_analysis):
        """Test transformation_type backwards compatibility property."""
        # With transformation
        model = CaseSynthesisModel(
            case_id=7,
            case_title="Test",
            entity_foundation=entity_foundation,
            transformation=transformation_analysis
        )
        assert model.transformation_type == "transfer"

        # Without transformation
        model_no_trans = CaseSynthesisModel(
            case_id=7,
            case_title="Test",
            entity_foundation=entity_foundation
        )
        assert model_no_trans.transformation_type == ""


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_entity_foundation(self):
        """Test EntityFoundation with no entities."""
        foundation = EntityFoundation()
        summary = foundation.summary()
        assert summary['total'] == 0

    def test_timeline_with_many_events(self):
        """Test timeline with multiple events."""
        events = [
            TimelineEvent(sequence=i, phase_label=f"Phase {i}", description=f"Event {i}")
            for i in range(10)
        ]
        narrative = CaseNarrative(case_summary="Test", timeline=events)
        assert len(narrative.timeline) == 10

    def test_question_emergence_with_multiple_warrants(self):
        """Test question with multiple competing warrant pairs."""
        analysis = QuestionEmergenceAnalysis(
            question_uri="q1",
            question_text="Complex question?",
            competing_warrants=[
                ("W1", "W2"),
                ("W3", "W4"),
                ("W5", "W6")
            ]
        )
        d = analysis.to_dict()
        assert len(d['competing_warrants']) == 3

    def test_causal_link_with_no_violations(self):
        """Test causal link that fulfills without violating."""
        link = CausalNormativeLink(
            action_id="a1",
            action_label="Good action",
            fulfills_obligations=["o1", "o2"],
            violates_obligations=[]
        )
        assert len(link.fulfills_obligations) == 2
        assert len(link.violates_obligations) == 0
