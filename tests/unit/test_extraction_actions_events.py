"""
Unit tests for DualActionsEventsExtractor.

Tests extraction of action and event classes and individuals.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestDualActionsEventsExtractor:
    """Tests for actions/events extraction service."""

    def test_extract_actions_events_returns_four_result_lists(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that extraction returns all four result types."""
        with patch('app.services.extraction.dual_actions_events_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_action_entities.return_value = []
            mock_mcp.return_value.get_all_event_entities.return_value = []

            from app.services.extraction.dual_actions_events_extractor import DualActionsEventsExtractor

            extractor = DualActionsEventsExtractor(llm_client=mock_llm_client)
            action_classes, action_individuals, event_classes, event_individuals = \
                extractor.extract_dual_actions_events(
                    case_text=sample_case_text,
                    case_id=sample_case_id,
                    section_type='facts'
                )

            assert isinstance(action_classes, list)
            assert isinstance(action_individuals, list)
            assert isinstance(event_classes, list)
            assert isinstance(event_individuals, list)

    def test_extract_actions_individuals_have_temporal_properties(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that action individuals have temporal tracking."""
        with patch('app.services.extraction.dual_actions_events_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_action_entities.return_value = []
            mock_mcp.return_value.get_all_event_entities.return_value = []

            from app.services.extraction.dual_actions_events_extractor import DualActionsEventsExtractor

            extractor = DualActionsEventsExtractor(llm_client=mock_llm_client)
            action_classes, action_individuals, event_classes, event_individuals = \
                extractor.extract_dual_actions_events(
                    case_text=sample_case_text,
                    case_id=sample_case_id,
                    section_type='facts'
                )

            if len(action_individuals) > 0:
                action = action_individuals[0]
                assert hasattr(action, 'performed_by')
                assert hasattr(action, 'temporal_interval')

    def test_extract_events_individuals_have_causal_properties(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that event individuals track causality."""
        with patch('app.services.extraction.dual_actions_events_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_action_entities.return_value = []
            mock_mcp.return_value.get_all_event_entities.return_value = []

            from app.services.extraction.dual_actions_events_extractor import DualActionsEventsExtractor

            extractor = DualActionsEventsExtractor(llm_client=mock_llm_client)
            action_classes, action_individuals, event_classes, event_individuals = \
                extractor.extract_dual_actions_events(
                    case_text=sample_case_text,
                    case_id=sample_case_id,
                    section_type='facts'
                )

            if len(event_individuals) > 0:
                event = event_individuals[0]
                assert hasattr(event, 'causal_triggers')
                assert hasattr(event, 'causal_results')

    def test_extract_action_classes_have_category(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that action classes define category."""
        with patch('app.services.extraction.dual_actions_events_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_action_entities.return_value = []
            mock_mcp.return_value.get_all_event_entities.return_value = []

            from app.services.extraction.dual_actions_events_extractor import DualActionsEventsExtractor

            extractor = DualActionsEventsExtractor(llm_client=mock_llm_client)
            action_classes, action_individuals, event_classes, event_individuals = \
                extractor.extract_dual_actions_events(
                    case_text=sample_case_text,
                    case_id=sample_case_id,
                    section_type='facts'
                )

            if len(action_classes) > 0:
                action_class = action_classes[0]
                assert hasattr(action_class, 'action_category')
                assert hasattr(action_class, 'volitional_requirement')

    def test_extract_stores_raw_response(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test raw response is stored for RDF conversion."""
        with patch('app.services.extraction.dual_actions_events_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_action_entities.return_value = []
            mock_mcp.return_value.get_all_event_entities.return_value = []

            from app.services.extraction.dual_actions_events_extractor import DualActionsEventsExtractor

            extractor = DualActionsEventsExtractor(llm_client=mock_llm_client)
            extractor.extract_dual_actions_events(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            assert extractor.last_raw_response is not None
