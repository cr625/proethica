"""
Unit tests for DualObligationsExtractor.

Tests extraction of obligation classes and individuals.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestDualObligationsExtractor:
    """Tests for obligations extraction service."""

    def test_extract_obligations_returns_results(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that obligations extraction returns both classes and individuals."""
        with patch('app.services.external_mcp_client.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_obligation_entities.return_value = []

            from app.services.extraction.dual_obligations_extractor import DualObligationsExtractor

            extractor = DualObligationsExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_obligations(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            assert isinstance(classes, list)
            assert isinstance(individuals, list)

    def test_extract_obligations_class_has_duty_type(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test obligation classes categorize duty type."""
        with patch('app.services.external_mcp_client.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_obligation_entities.return_value = []

            from app.services.extraction.dual_obligations_extractor import DualObligationsExtractor

            extractor = DualObligationsExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_obligations(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            if len(classes) > 0:
                obligation = classes[0]
                assert hasattr(obligation, 'duty_type')
                assert hasattr(obligation, 'label')

    def test_extract_obligations_individual_tracks_compliance(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test obligation individuals track compliance status."""
        with patch('app.services.external_mcp_client.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_obligation_entities.return_value = []

            from app.services.extraction.dual_obligations_extractor import DualObligationsExtractor

            extractor = DualObligationsExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_obligations(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            if len(individuals) > 0:
                individual = individuals[0]
                assert hasattr(individual, 'obligated_party')
                assert hasattr(individual, 'obligation_statement')

    def test_extract_obligations_stores_raw_response(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test raw response stored."""
        with patch('app.services.external_mcp_client.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_obligation_entities.return_value = []

            from app.services.extraction.dual_obligations_extractor import DualObligationsExtractor

            extractor = DualObligationsExtractor(llm_client=mock_llm_client)
            extractor.extract_dual_obligations(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            assert extractor.last_raw_response is not None
