"""
Unit tests for DualResourcesExtractor.

Tests extraction of resource classes and individuals with mock LLM responses.
"""

import pytest
import json
from unittest.mock import patch, MagicMock


class TestDualResourcesExtractor:
    """Tests for resource extraction service."""

    def test_extract_resources_returns_results(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that resource extraction returns both classes and individuals."""
        with patch('app.services.extraction.dual_resources_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_resource_entities.return_value = []

            from app.services.extraction.dual_resources_extractor import DualResourcesExtractor

            extractor = DualResourcesExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_resources(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            assert isinstance(classes, list)
            assert isinstance(individuals, list)

    def test_extract_resources_individual_structure(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that extracted resource individuals have required fields."""
        with patch('app.services.extraction.dual_resources_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_resource_entities.return_value = []

            from app.services.extraction.dual_resources_extractor import DualResourcesExtractor

            extractor = DualResourcesExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_resources(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            if len(individuals) > 0:
                individual = individuals[0]
                assert hasattr(individual, 'identifier')
                assert hasattr(individual, 'resource_class')
                assert hasattr(individual, 'confidence')

    def test_extract_resources_class_has_type(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that resource classes define resource type."""
        with patch('app.services.extraction.dual_resources_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_resource_entities.return_value = []

            from app.services.extraction.dual_resources_extractor import DualResourcesExtractor

            extractor = DualResourcesExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_resources(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            if len(classes) > 0:
                resource_class = classes[0]
                assert hasattr(resource_class, 'resource_type')
                assert hasattr(resource_class, 'label')
                assert hasattr(resource_class, 'definition')

    def test_extract_resources_discussion_section(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test resource extraction from discussion section."""
        with patch('app.services.extraction.dual_resources_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_resource_entities.return_value = []

            from app.services.extraction.dual_resources_extractor import DualResourcesExtractor

            extractor = DualResourcesExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_resources(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='discussion'
            )

            # Verify correct section was used
            calls = mock_llm_client.get_calls(extraction_type='resources')
            assert calls[0]['section_type'] == 'discussion'

    def test_extract_resources_stores_raw_response(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that raw LLM response is stored."""
        with patch('app.services.extraction.dual_resources_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_resource_entities.return_value = []

            from app.services.extraction.dual_resources_extractor import DualResourcesExtractor

            extractor = DualResourcesExtractor(llm_client=mock_llm_client)
            extractor.extract_dual_resources(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            assert extractor.last_raw_response is not None
