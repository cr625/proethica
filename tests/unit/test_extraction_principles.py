"""
Unit tests for DualPrinciplesExtractor.

Tests extraction of ethical principle classes and individuals.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestDualPrinciplesExtractor:
    """Tests for principles extraction service."""

    def test_extract_principles_returns_results(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that principles extraction returns both classes and individuals."""
        with patch('app.services.extraction.dual_principles_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_principle_entities.return_value = []

            from app.services.extraction.dual_principles_extractor import DualPrinciplesExtractor

            extractor = DualPrinciplesExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_principles(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            assert isinstance(classes, list)
            assert isinstance(individuals, list)

    def test_extract_principles_class_structure(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test principle classes have required philosophical fields."""
        with patch('app.services.extraction.dual_principles_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_principle_entities.return_value = []

            from app.services.extraction.dual_principles_extractor import DualPrinciplesExtractor

            extractor = DualPrinciplesExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_principles(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            if len(classes) > 0:
                principle = classes[0]
                assert hasattr(principle, 'label')
                assert hasattr(principle, 'definition')
                assert hasattr(principle, 'abstract_nature')
                assert hasattr(principle, 'value_basis')

    def test_extract_principles_individual_has_balancing(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test principle individuals track balancing with other principles."""
        with patch('app.services.extraction.dual_principles_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_principle_entities.return_value = []

            from app.services.extraction.dual_principles_extractor import DualPrinciplesExtractor

            extractor = DualPrinciplesExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_principles(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='discussion'
            )

            if len(individuals) > 0:
                individual = individuals[0]
                assert hasattr(individual, 'balancing_with')

    def test_extract_principles_stores_raw_response(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test raw response stored for RDF conversion."""
        with patch('app.services.extraction.dual_principles_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_principle_entities.return_value = []

            from app.services.extraction.dual_principles_extractor import DualPrinciplesExtractor

            extractor = DualPrinciplesExtractor(llm_client=mock_llm_client)
            extractor.extract_dual_principles(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            raw = extractor.get_last_raw_response()
            assert raw is not None
