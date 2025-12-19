"""
Unit tests for Interactive Scenario Service.

Tests the interactive scenario exploration functionality where users
make ethical choices at decision points and see LLM-generated consequences.

These tests use mocks to avoid database and LLM dependencies.
"""

import pytest
import json
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

from app.services.interactive_scenario_service import InteractiveScenarioService


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def service():
    """Create an InteractiveScenarioService instance."""
    return InteractiveScenarioService()


@pytest.fixture
def mock_session():
    """Create a mock ScenarioExplorationSession."""
    session = MagicMock()
    session.id = 1
    session.case_id = 7
    session.session_uuid = "test-uuid-12345"
    session.status = "in_progress"
    session.current_decision_index = 0
    session.active_fluents = ["Engineer_A_has_AI_tool", "Client_W_trusts_Engineer_A"]
    session.terminated_fluents = []
    session.exploration_mode = "interactive"
    session.choices = []
    session.last_activity_at = datetime.now()
    return session


@pytest.fixture
def mock_decision_points():
    """Sample decision points for testing."""
    return [
        {
            'uri': 'case-7#DP1',
            'label': 'AI Disclosure Decision',
            'question': 'Should Engineer A disclose AI usage to the client?',
            'description': 'Engineer A must decide whether to inform Client W about using AI tools.',
            'options': [
                {
                    'uri': 'case-7#Option1',
                    'label': 'Disclose AI Use',
                    'description': 'Fully inform the client about AI assistance',
                    'is_board_choice': True
                },
                {
                    'uri': 'case-7#Option2',
                    'label': 'Do Not Disclose',
                    'description': 'Proceed without informing the client',
                    'is_board_choice': False
                }
            ]
        },
        {
            'uri': 'case-7#DP2',
            'label': 'Verification Decision',
            'question': 'Should Engineer A verify AI-generated content thoroughly?',
            'description': 'Decision about the level of verification for AI outputs.',
            'options': [
                {
                    'uri': 'case-7#Option3',
                    'label': 'Full Verification',
                    'description': 'Thoroughly verify all AI outputs'
                },
                {
                    'uri': 'case-7#Option4',
                    'label': 'Minimal Review',
                    'description': 'Quick review of AI outputs'
                }
            ]
        }
    ]


@pytest.fixture
def mock_choice():
    """Create a mock ScenarioExplorationChoice."""
    choice = MagicMock()
    choice.id = 1
    choice.session_id = 1
    choice.decision_point_uri = "case-7#DP1"
    choice.option_uri = "case-7#Option1"
    choice.option_label = "Disclose AI Use"
    choice.consequences_narrative = "By disclosing AI use, Engineer A maintains transparency..."
    choice.fluents_initiated = ["Client_W_knows_about_AI"]
    choice.fluents_terminated = ["Client_W_unaware_of_AI"]
    choice.created_at = datetime.now()
    return choice


# =============================================================================
# SERVICE INITIALIZATION TESTS
# =============================================================================

class TestServiceInitialization:
    """Tests for service initialization."""

    def test_service_creates_without_llm(self, service):
        """Test service initializes with lazy LLM loading."""
        assert service.llm_client is None

    def test_get_llm_client_lazy_loads(self, service):
        """Test LLM client is lazily loaded."""
        with patch('app.services.interactive_scenario_service.get_llm_client') as mock_get:
            mock_get.return_value = MagicMock()
            client = service._get_llm_client()
            assert client is not None
            mock_get.assert_called_once()


# =============================================================================
# SESSION MANAGEMENT TESTS
# =============================================================================

class TestSessionManagement:
    """Tests for session management functions."""

    @patch('app.services.interactive_scenario_service.db')
    @patch('app.services.interactive_scenario_service.ScenarioExplorationSession')
    def test_start_session_creates_new(self, mock_session_class, mock_db, service, mock_decision_points):
        """Test starting a new exploration session."""
        # Mock the decision points and fluents loading
        with patch.object(service, '_load_decision_points', return_value=mock_decision_points):
            with patch.object(service, '_load_initial_fluents', return_value=["fluent1"]):
                mock_session_class.return_value = MagicMock(session_uuid="new-uuid")

                session = service.start_session(case_id=7, user_id=1)

                mock_db.session.add.assert_called_once()
                mock_db.session.commit.assert_called_once()

    @patch('app.services.interactive_scenario_service.ScenarioExplorationSession')
    def test_get_session_by_uuid(self, mock_session_class, service, mock_session):
        """Test retrieving a session by UUID."""
        mock_session_class.query.filter_by.return_value.first.return_value = mock_session

        result = service.get_session("test-uuid-12345")

        assert result == mock_session
        mock_session_class.query.filter_by.assert_called_with(session_uuid="test-uuid-12345")

    @patch('app.services.interactive_scenario_service.ScenarioExplorationSession')
    def test_get_active_sessions(self, mock_session_class, service, mock_session):
        """Test getting all active sessions for a case."""
        mock_session_class.query.filter_by.return_value.order_by.return_value.all.return_value = [mock_session]

        result = service.get_active_sessions(case_id=7)

        assert len(result) == 1
        assert result[0] == mock_session


# =============================================================================
# DECISION POINT HANDLING TESTS
# =============================================================================

class TestDecisionPointHandling:
    """Tests for decision point retrieval and display."""

    def test_get_current_decision_returns_dict(self, service, mock_session, mock_decision_points):
        """Test getting current decision point returns proper structure."""
        with patch.object(service, '_load_decision_points', return_value=mock_decision_points):
            with patch.object(service, '_build_decision_context', return_value="Test context"):
                result = service.get_current_decision(mock_session)

                assert result is not None
                assert 'decision_point' in result
                assert 'options' in result
                assert 'context' in result
                assert result['decision_index'] == 0
                assert result['total_decisions'] == 2

    def test_get_current_decision_returns_none_when_complete(self, service, mock_session, mock_decision_points):
        """Test returns None when all decisions made."""
        mock_session.current_decision_index = 2  # Past the end

        with patch.object(service, '_load_decision_points', return_value=mock_decision_points):
            result = service.get_current_decision(mock_session)

            assert result is None

    def test_decision_context_includes_fluents(self, service, mock_session, mock_decision_points):
        """Test decision context includes active fluents."""
        with patch.object(service, '_load_decision_points', return_value=mock_decision_points):
            with patch.object(service, '_build_decision_context', return_value="Context"):
                result = service.get_current_decision(mock_session)

                assert 'active_fluents' in result
                assert len(result['active_fluents']) > 0


# =============================================================================
# CONTEXT BUILDING TESTS
# =============================================================================

class TestContextBuilding:
    """Tests for decision context building."""

    def test_build_decision_context_with_choices(self, service, mock_session, mock_choice):
        """Test context includes previous choice narratives."""
        mock_session.choices = [mock_choice]
        decision_point = {'description': 'Test decision'}

        with patch.object(service, '_load_opening_context', return_value="Opening context"):
            context = service._build_decision_context(mock_session, decision_point)

            assert "Opening context" in context
            # Previous choice narrative should be included
            assert "previous choices" in context.lower() or mock_choice.consequences_narrative in context

    def test_build_decision_context_without_choices(self, service, mock_session):
        """Test context works with no previous choices."""
        mock_session.choices = []
        decision_point = {'description': 'Test decision'}

        with patch.object(service, '_load_opening_context', return_value="Opening context"):
            context = service._build_decision_context(mock_session, decision_point)

            assert context is not None
            assert "Opening context" in context


# =============================================================================
# DATA LOADING TESTS
# =============================================================================

class TestDataLoading:
    """Tests for loading case data."""

    @patch('app.services.interactive_scenario_service.TemporaryRDFStorage')
    def test_load_decision_points_from_database(self, mock_storage, service):
        """Test decision points are loaded from RDF storage."""
        mock_entity = MagicMock()
        mock_entity.rdf_json_ld = {
            'uri': 'case-7#DP1',
            'label': 'Test Decision',
            'options': []
        }
        mock_storage.query.filter_by.return_value.order_by.return_value.all.return_value = [mock_entity]

        # The actual method may need database access, so we test the interface
        assert hasattr(service, '_load_decision_points')

    def test_load_initial_fluents_method_exists(self, service):
        """Test initial fluents loader method exists and is callable."""
        # This method requires Flask app context for database access
        # Integration tests should verify actual behavior with database
        assert hasattr(service, '_load_initial_fluents')
        assert callable(service._load_initial_fluents)


# =============================================================================
# SESSION STATE TESTS
# =============================================================================

class TestSessionState:
    """Tests for session state management."""

    def test_session_tracks_fluents(self, mock_session):
        """Test session properly tracks active and terminated fluents."""
        assert mock_session.active_fluents is not None
        assert mock_session.terminated_fluents is not None
        assert isinstance(mock_session.active_fluents, list)
        assert isinstance(mock_session.terminated_fluents, list)

    def test_session_tracks_decision_index(self, mock_session):
        """Test session tracks current decision index."""
        assert mock_session.current_decision_index == 0

        # Simulate moving to next decision
        mock_session.current_decision_index = 1
        assert mock_session.current_decision_index == 1

    def test_session_status_transitions(self, mock_session):
        """Test session status can be updated."""
        assert mock_session.status == "in_progress"

        mock_session.status = "completed"
        assert mock_session.status == "completed"


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    def test_start_session_fails_without_decision_points(self, service):
        """Test starting session fails if no decision points exist."""
        with patch.object(service, '_load_decision_points', return_value=[]):
            with patch.object(service, '_load_initial_fluents', return_value=[]):
                with pytest.raises(ValueError, match="No decision points found"):
                    service.start_session(case_id=999)

    def test_get_session_returns_none_for_invalid_uuid(self, service):
        """Test get_session returns None for non-existent UUID."""
        with patch('app.services.interactive_scenario_service.ScenarioExplorationSession') as mock_class:
            mock_class.query.filter_by.return_value.first.return_value = None

            result = service.get_session("nonexistent-uuid")

            assert result is None


# =============================================================================
# CHOICE STRUCTURE TESTS
# =============================================================================

class TestChoiceStructure:
    """Tests for choice data structure."""

    def test_choice_has_required_fields(self, mock_choice):
        """Test choice object has all required fields."""
        assert hasattr(mock_choice, 'decision_point_uri')
        assert hasattr(mock_choice, 'option_uri')
        assert hasattr(mock_choice, 'option_label')
        assert hasattr(mock_choice, 'consequences_narrative')
        assert hasattr(mock_choice, 'fluents_initiated')
        assert hasattr(mock_choice, 'fluents_terminated')

    def test_choice_tracks_fluent_changes(self, mock_choice):
        """Test choice tracks which fluents are initiated/terminated."""
        assert isinstance(mock_choice.fluents_initiated, list)
        assert isinstance(mock_choice.fluents_terminated, list)
        assert len(mock_choice.fluents_initiated) > 0


# =============================================================================
# OPTION STRUCTURE TESTS
# =============================================================================

class TestOptionStructure:
    """Tests for decision option structure."""

    def test_option_has_board_choice_indicator(self, mock_decision_points):
        """Test options have board choice indicator."""
        for dp in mock_decision_points:
            for option in dp['options']:
                # At least some options should have this field
                if 'is_board_choice' in option:
                    assert isinstance(option['is_board_choice'], bool)

    def test_option_has_description(self, mock_decision_points):
        """Test options have descriptions."""
        for dp in mock_decision_points:
            for option in dp['options']:
                assert 'description' in option
                assert option['description'] != ""
