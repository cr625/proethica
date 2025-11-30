"""
Unit tests for DualStatesExtractor.

Tests extraction of state classes and individuals with mock LLM responses.
"""

import pytest
import json
from unittest.mock import patch, MagicMock


class TestDualStatesExtractor:
    """Tests for state extraction service."""

    def test_extract_states_returns_results(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that state extraction returns both classes and individuals."""
        with patch('app.services.extraction.dual_states_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_state_entities.return_value = []

            from app.services.extraction.dual_states_extractor import DualStatesExtractor

            extractor = DualStatesExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_states(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            assert isinstance(classes, list)
            assert isinstance(individuals, list)

    def test_extract_states_from_facts_fixture(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test state extraction uses facts fixture correctly."""
        with patch('app.services.extraction.dual_states_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_state_entities.return_value = []

            from app.services.extraction.dual_states_extractor import DualStatesExtractor

            extractor = DualStatesExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_states(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            # Verify mock was called with correct params
            calls = mock_llm_client.get_calls(extraction_type='states')
            assert len(calls) == 1
            assert calls[0]['section_type'] == 'facts'

    def test_extract_states_individual_has_temporal_properties(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that state individuals have temporal tracking fields."""
        with patch('app.services.extraction.dual_states_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_state_entities.return_value = []

            from app.services.extraction.dual_states_extractor import DualStatesExtractor

            extractor = DualStatesExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_states(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            if len(individuals) > 0:
                individual = individuals[0]
                # States should have temporal properties
                assert hasattr(individual, 'identifier')
                assert hasattr(individual, 'state_class')
                assert hasattr(individual, 'active_period')
                assert hasattr(individual, 'triggering_event')

    def test_extract_states_class_has_persistence_type(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that state classes define persistence (inertial vs non-inertial)."""
        with patch('app.services.extraction.dual_states_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_state_entities.return_value = []

            from app.services.extraction.dual_states_extractor import DualStatesExtractor

            extractor = DualStatesExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_states(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            if len(classes) > 0:
                state_class = classes[0]
                assert hasattr(state_class, 'persistence_type')

    def test_extract_states_stores_raw_response(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that raw LLM response is accessible for debugging."""
        with patch('app.services.extraction.dual_states_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_state_entities.return_value = []

            from app.services.extraction.dual_states_extractor import DualStatesExtractor

            extractor = DualStatesExtractor(llm_client=mock_llm_client)
            extractor.extract_dual_states(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            assert extractor.last_raw_response is not None
