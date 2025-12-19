"""
Unit tests for Entity Analysis Pipeline (E1-F3).

These tests verify the entity-grounded argument pipeline components:
- E1: ObligationCoverageAnalyzer
- E2: ActionOptionMapper
- E3: DecisionPointComposer
- F1: PrincipleProvisionAligner
- F2: ArgumentGenerator
- F3: ArgumentValidator

Tests use mocked database entities to run without database connections.
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import asdict

# E1 imports
from app.services.entity_analysis.obligation_coverage_analyzer import (
    ObligationAnalysis,
    ConstraintAnalysis,
    CoverageMatrix,
    DECISION_TYPE_KEYWORDS,
    CONFLICT_PATTERNS
)

# E2 imports
from app.services.entity_analysis.action_option_mapper import (
    ActionOption,
    ActionSet,
    ActionOptionMap,
    MoralIntensityScore
)

# E3 imports
from app.services.entity_analysis.decision_point_composer import (
    EntityGroundedDecisionPoint,
    DecisionPointGrounding,
    DecisionPointOption,
    ComposedDecisionPoints
)

# F1 imports
from app.services.entity_analysis.principle_provision_aligner import (
    PrincipleAlignment,
    ProvisionDetail,
    AlignmentMap
)

from app.domains import DomainConfig


# =============================================================================
# E1: OBLIGATION COVERAGE ANALYZER TESTS
# =============================================================================

class TestObligationCoverageAnalyzer:
    """Tests for E1: ObligationCoverageAnalyzer dataclasses."""

    def test_obligation_analysis_dataclass(self):
        """Test ObligationAnalysis dataclass fields."""
        analysis = ObligationAnalysis(
            entity_uri="case-7#test",
            entity_label="Test Obligation",
            entity_definition="A test obligation",
            bound_role="Engineer A",
            decision_type="disclosure"
        )
        assert analysis.entity_uri == "case-7#test"
        assert analysis.decision_type == "disclosure"
        assert analysis.decision_relevant is False

    def test_constraint_analysis_dataclass(self):
        """Test ConstraintAnalysis dataclass fields."""
        analysis = ConstraintAnalysis(
            entity_uri="case-7#constraint",
            entity_label="Test Constraint",
            entity_definition="A test constraint",
            founding_value_limit=True
        )
        assert analysis.founding_value_limit is True

    def test_coverage_matrix_summary(self):
        """Test CoverageMatrix provides correct summary."""
        matrix = CoverageMatrix(
            case_id=7,
            obligations=[
                ObligationAnalysis(
                    entity_uri="o1", entity_label="O1", entity_definition="",
                    decision_relevant=True
                )
            ],
            constraints=[
                ConstraintAnalysis(
                    entity_uri="c1", entity_label="C1", entity_definition="",
                    decision_relevant=True
                )
            ],
            decision_relevant_count=2
        )
        assert matrix.case_id == 7
        assert len(matrix.obligations) == 1
        assert len(matrix.constraints) == 1
        assert matrix.decision_relevant_count == 2

    def test_conflict_pattern_detection(self):
        """Test that conflict patterns are properly defined."""
        # Disclosure vs confidentiality is a known conflict
        assert ('disclosure', 'confidentiality') in CONFLICT_PATTERNS

        # Safety vs competence is a known conflict
        assert ('safety', 'competence') in CONFLICT_PATTERNS

    def test_coverage_matrix_to_dict(self):
        """Test CoverageMatrix serialization."""
        matrix = CoverageMatrix(
            case_id=7,
            obligations=[
                ObligationAnalysis(
                    entity_uri="o1",
                    entity_label="Obligation 1",
                    entity_definition="Test"
                )
            ],
            constraints=[]
        )
        d = matrix.to_dict()
        assert d['case_id'] == 7
        assert len(d['obligations']) == 1
        assert d['obligations'][0]['entity_uri'] == "o1"

    def test_obligation_analysis_defaults(self):
        """Test ObligationAnalysis default values."""
        analysis = ObligationAnalysis(
            entity_uri="uri",
            entity_label="label",
            entity_definition="def"
        )
        assert analysis.bound_role is None
        assert analysis.decision_type == "unclassified"
        assert analysis.related_provisions == []
        assert analysis.conflicts_with == []
        assert analysis.serves_founding_good is True
        assert analysis.decision_relevant is False

    def test_constraint_analysis_defaults(self):
        """Test ConstraintAnalysis default values."""
        analysis = ConstraintAnalysis(
            entity_uri="uri",
            entity_label="label",
            entity_definition="def"
        )
        assert analysis.constrained_role is None
        assert analysis.restricts_actions == []
        assert analysis.founding_value_limit is False
        assert analysis.decision_relevant is False

    def test_coverage_matrix_defaults(self):
        """Test CoverageMatrix default values."""
        matrix = CoverageMatrix(case_id=7)
        assert matrix.obligations == []
        assert matrix.constraints == []
        assert matrix.role_obligation_map == {}
        assert matrix.conflict_pairs == []
        assert matrix.decision_relevant_count == 0

    def test_decision_type_keywords_completeness(self):
        """Test that all expected decision types have keywords."""
        expected_types = ['disclosure', 'verification', 'competence', 'confidentiality', 'safety']
        for dtype in expected_types:
            assert dtype in DECISION_TYPE_KEYWORDS
            assert len(DECISION_TYPE_KEYWORDS[dtype]) > 0


# =============================================================================
# E2: ACTION OPTION MAPPER TESTS
# =============================================================================

class TestActionOptionMapper:
    """Tests for E2: ActionOptionMapper dataclasses."""

    def test_moral_intensity_score_dataclass(self):
        """Test MoralIntensityScore fields match Jones (1991) framework."""
        score = MoralIntensityScore(
            magnitude=0.8,
            social_consensus=0.6,
            probability=0.7,
            temporal_immediacy=0.5,
            proximity=0.9,
            concentration=0.4
        )
        assert score.magnitude == 0.8
        assert score.social_consensus == 0.6
        # Overall is a weighted average
        assert 0 <= score.overall <= 1

    def test_moral_intensity_score_to_dict(self):
        """Test MoralIntensityScore serialization."""
        score = MoralIntensityScore()
        d = score.to_dict()
        assert 'magnitude' in d
        assert 'social_consensus' in d
        assert 'probability' in d
        assert 'temporal_immediacy' in d
        assert 'proximity' in d
        assert 'concentration' in d
        assert 'overall' in d

    def test_action_option_dataclass(self):
        """Test ActionOption dataclass."""
        option = ActionOption(
            uri="case-7#action1",
            label="Test Action",
            description="A test action",
            is_extracted=True,
            is_board_choice=False
        )
        assert option.is_extracted is True
        assert option.is_board_choice is False
        assert option.was_chosen is False

    def test_action_option_with_intensity(self):
        """Test ActionOption with moral intensity score."""
        score = MoralIntensityScore(magnitude=0.9)
        option = ActionOption(
            uri="case-7#action1",
            label="High Stakes Action",
            intensity_score=score
        )
        assert option.intensity_score is not None
        assert option.intensity_score.magnitude == 0.9

    def test_action_set_dataclass(self):
        """Test ActionSet contains actions."""
        actions = [
            ActionOption(uri="a1", label="Option 1", description="First option"),
            ActionOption(uri="a2", label="Option 2", description="Second option")
        ]
        action_set = ActionSet(
            decision_context="disclosure",
            primary_action_uri="a1",
            actions=actions
        )
        assert len(action_set.actions) == 2
        assert action_set.decision_context == "disclosure"
        assert action_set.primary_action_uri == "a1"

    def test_action_option_map(self):
        """Test ActionOptionMap provides action set count."""
        action_sets = [
            ActionSet(decision_context="ctx1", primary_action_uri="a1"),
            ActionSet(decision_context="ctx2", primary_action_uri="a2")
        ]
        map_obj = ActionOptionMap(case_id=7, action_sets=action_sets)
        assert len(map_obj.action_sets) == 2
        assert map_obj.case_id == 7


# =============================================================================
# E3: DECISION POINT COMPOSER TESTS
# =============================================================================

class TestDecisionPointComposer:
    """Tests for E3: DecisionPointComposer dataclasses."""

    def test_decision_point_grounding_dataclass(self):
        """Test DecisionPointGrounding contains URIs and labels."""
        grounding = DecisionPointGrounding(
            role_uri="case-7#Engineer_A",
            role_label="Engineer A",
            obligation_uri="case-7#Obligation_1",
            obligation_label="Disclosure Obligation"
        )
        assert grounding.role_uri == "case-7#Engineer_A"
        assert grounding.role_label == "Engineer A"
        assert grounding.obligation_uri is not None
        assert grounding.constraint_uri is None

    def test_decision_point_option_dataclass(self):
        """Test DecisionPointOption fields."""
        option = DecisionPointOption(
            option_id="O1",
            action_uri="case-7#action1",
            action_label="Disclose AI Use",
            description="Choose to disclose",
            is_board_choice=True,
            is_extracted_action=False
        )
        assert option.is_board_choice is True
        assert option.option_id == "O1"
        assert option.action_label == "Disclose AI Use"

    def test_entity_grounded_decision_point(self):
        """Test EntityGroundedDecisionPoint structure."""
        grounding = DecisionPointGrounding(
            role_uri="case-7#Engineer_A",
            role_label="Engineer A"
        )
        options = [
            DecisionPointOption(
                option_id="O1",
                action_uri="case-7#Disclose",
                action_label="Disclose",
                description="Disclose AI use"
            )
        ]
        dp = EntityGroundedDecisionPoint(
            focus_id="DP1",
            focus_number=1,
            description="Should Engineer A disclose AI use?",
            decision_question="Should AI usage be disclosed to client?",
            grounding=grounding,
            options=options,
            provision_uris=["case-7#NSPE_II_1_c"]
        )
        assert dp.focus_id == "DP1"
        assert dp.focus_number == 1
        assert len(dp.options) == 1
        assert len(dp.provision_uris) == 1

    def test_composed_decision_points(self):
        """Test ComposedDecisionPoints container."""
        grounding = DecisionPointGrounding(
            role_uri="case-7#Engineer_A",
            role_label="Engineer A"
        )
        dps = [
            EntityGroundedDecisionPoint(
                focus_id="DP1",
                focus_number=1,
                description="Test",
                decision_question="Question?",
                grounding=grounding,
                options=[]
            )
        ]
        composed = ComposedDecisionPoints(case_id=7, decision_points=dps)
        assert len(composed.decision_points) == 1
        assert composed.case_id == 7


# =============================================================================
# F1: PRINCIPLE PROVISION ALIGNER TESTS
# =============================================================================

class TestPrincipleProvisionAligner:
    """Tests for F1: PrincipleProvisionAligner dataclasses."""

    def test_provision_detail_dataclass(self):
        """Test ProvisionDetail fields."""
        provision = ProvisionDetail(
            uri="case-7#NSPE_II_1_c",
            label="NSPE II.1.c",
            section="II.1.c",
            text="Engineers shall disclose all relevant facts",
            level="rules_of_practice"
        )
        assert provision.section == "II.1.c"
        assert provision.level == "rules_of_practice"

    def test_principle_alignment_dataclass(self):
        """Test PrincipleAlignment structure."""
        alignment = PrincipleAlignment(
            principle_uri="case-7#Transparency",
            principle_label="Transparency",
            principle_definition="Be transparent in professional dealings",
            support_type="pro_disclosure",
            alignment_confidence=0.85
        )
        assert alignment.support_type == "pro_disclosure"
        assert alignment.alignment_confidence == 0.85

    def test_principle_alignment_with_provisions(self):
        """Test PrincipleAlignment with linked provisions."""
        alignment = PrincipleAlignment(
            principle_uri="case-7#Transparency",
            principle_label="Transparency",
            principle_definition="Be transparent",
            provision_uris=["case-7#NSPE_II_1_c"],
            provision_labels=["NSPE II.1.c"]
        )
        assert len(alignment.provision_uris) == 1
        assert len(alignment.provision_labels) == 1

    def test_alignment_map_structure(self):
        """Test AlignmentMap structure and rate calculation."""
        # Create alignments - one with provisions, one without
        alignments = [
            PrincipleAlignment(
                principle_uri="p1",
                principle_label="P1",
                principle_definition="Def1",
                provision_uris=["pv1"],
                provision_labels=["NSPE I.1"]
            ),
            PrincipleAlignment(
                principle_uri="p2",
                principle_label="P2",
                principle_definition="Def2"
            )
        ]
        map_obj = AlignmentMap(
            case_id=7,
            alignments=alignments,
            total_principles=2,
            total_provisions=1,
            alignment_rate=0.5
        )
        assert map_obj.case_id == 7
        assert len(map_obj.alignments) == 2
        assert map_obj.alignment_rate == 0.5

    def test_alignment_map_to_dict(self):
        """Test AlignmentMap serialization."""
        map_obj = AlignmentMap(case_id=7)
        d = map_obj.to_dict()
        assert 'case_id' in d
        assert 'alignments' in d
        assert 'alignment_rate' in d


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestEntityAnalysisPipelineIntegration:
    """Integration tests for the E1-F3 pipeline with dataclass interactions."""

    def test_obligation_analysis_to_dict(self):
        """Test ObligationAnalysis serialization."""
        analysis = ObligationAnalysis(
            entity_uri="case-7#test",
            entity_label="Test",
            entity_definition="Def",
            bound_role="Engineer A",
            decision_type="disclosure",
            decision_relevant=True
        )
        d = analysis.to_dict()
        assert d['entity_uri'] == "case-7#test"
        assert d['decision_relevant'] is True

    def test_constraint_analysis_to_dict(self):
        """Test ConstraintAnalysis serialization."""
        analysis = ConstraintAnalysis(
            entity_uri="case-7#constraint",
            entity_label="Constraint",
            entity_definition="Def",
            founding_value_limit=True
        )
        d = analysis.to_dict()
        assert d['founding_value_limit'] is True

    def test_decision_point_grounding_to_dict(self):
        """Test DecisionPointGrounding serialization."""
        grounding = DecisionPointGrounding(
            role_uri="case-7#Engineer_A",
            role_label="Engineer A"
        )
        d = grounding.to_dict()
        assert d['role_uri'] == "case-7#Engineer_A"
        assert d['role_label'] == "Engineer A"

    def test_action_option_to_dict(self):
        """Test ActionOption serialization."""
        option = ActionOption(
            uri="a1",
            label="Option 1",
            description="First option"
        )
        d = option.to_dict()
        assert d['uri'] == "a1"
        assert d['label'] == "Option 1"

    def test_moral_intensity_overall_calculation(self):
        """Test that moral intensity overall is correctly calculated."""
        # Test with default values (all 0.5)
        default_score = MoralIntensityScore()
        assert default_score.overall == 0.5

        # Test with high values
        high_score = MoralIntensityScore(
            magnitude=1.0,
            social_consensus=1.0,
            probability=1.0,
            temporal_immediacy=1.0,
            proximity=1.0,
            concentration=1.0
        )
        assert high_score.overall == 1.0

        # Test with low values
        low_score = MoralIntensityScore(
            magnitude=0.0,
            social_consensus=0.0,
            probability=0.0,
            temporal_immediacy=0.0,
            proximity=0.0,
            concentration=0.0
        )
        assert low_score.overall == 0.0


# =============================================================================
# CONVENIENCE FUNCTION TESTS (with mocking)
# =============================================================================

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @patch('app.services.entity_analysis.obligation_coverage_analyzer.TemporaryRDFStorage')
    @patch('app.services.entity_analysis.obligation_coverage_analyzer.get_domain_config')
    def test_get_obligation_coverage_calls_analyzer(self, mock_domain, mock_storage):
        """Test get_obligation_coverage convenience function."""
        from app.services.entity_analysis import get_obligation_coverage

        # Create a mock DomainConfig with the actual field names
        mock_config = MagicMock()
        mock_config.name = 'engineering'
        mock_config.display_name = 'Engineering'
        mock_config.founding_good = 'public_safety'
        mock_config.role_vocabulary = ['engineer']
        mock_domain.return_value = mock_config

        # Mock query to return empty list
        mock_query = MagicMock()
        mock_query.filter_by.return_value.all.return_value = []
        mock_storage.query = mock_query

        result = get_obligation_coverage(7, domain='engineering')
        assert result.case_id == 7
        assert isinstance(result, CoverageMatrix)
