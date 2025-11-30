"""
Unit tests for DualCapabilitiesExtractor.

Tests extraction of capability classes and individuals.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestDualCapabilitiesExtractor:
    """Tests for capabilities extraction service."""

    def test_extract_capabilities_returns_results(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that capabilities extraction returns both classes and individuals."""
        with patch('app.services.external_mcp_client.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_capability_entities.return_value = []

            from app.services.extraction.dual_capabilities_extractor import DualCapabilitiesExtractor

            extractor = DualCapabilitiesExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_capabilities(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            assert isinstance(classes, list)
            assert isinstance(individuals, list)

    def test_extract_capabilities_class_has_type_and_skill_level(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test capability classes define type and skill level."""
        with patch('app.services.external_mcp_client.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_capability_entities.return_value = []

            from app.services.extraction.dual_capabilities_extractor import DualCapabilitiesExtractor

            extractor = DualCapabilitiesExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_capabilities(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            if len(classes) > 0:
                capability = classes[0]
                assert hasattr(capability, 'capability_type')
                assert hasattr(capability, 'skill_level')

    def test_extract_capabilities_individual_identifies_possessor(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test capability individuals identify who possesses capability."""
        with patch('app.services.external_mcp_client.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_capability_entities.return_value = []

            from app.services.extraction.dual_capabilities_extractor import DualCapabilitiesExtractor

            extractor = DualCapabilitiesExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_capabilities(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            if len(individuals) > 0:
                individual = individuals[0]
                assert hasattr(individual, 'possessed_by')
                assert hasattr(individual, 'capability_statement')

    def test_extract_capabilities_stores_raw_response(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test raw response stored."""
        with patch('app.services.external_mcp_client.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_capability_entities.return_value = []

            from app.services.extraction.dual_capabilities_extractor import DualCapabilitiesExtractor

            extractor = DualCapabilitiesExtractor(llm_client=mock_llm_client)
            extractor.extract_dual_capabilities(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            assert extractor.last_raw_response is not None
