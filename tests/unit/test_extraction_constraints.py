"""
Unit tests for DualConstraintsExtractor.

Tests extraction of constraint classes and individuals.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestDualConstraintsExtractor:
    """Tests for constraints extraction service."""

    def test_extract_constraints_returns_results(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that constraints extraction returns both classes and individuals."""
        with patch('app.services.external_mcp_client.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_constraint_entities.return_value = []

            from app.services.extraction.dual_constraints_extractor import DualConstraintsExtractor

            extractor = DualConstraintsExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_constraints(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            assert isinstance(classes, list)
            assert isinstance(individuals, list)

    def test_extract_constraints_class_has_type_and_flexibility(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test constraint classes define type and flexibility."""
        with patch('app.services.external_mcp_client.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_constraint_entities.return_value = []

            from app.services.extraction.dual_constraints_extractor import DualConstraintsExtractor

            extractor = DualConstraintsExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_constraints(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            if len(classes) > 0:
                constraint = classes[0]
                assert hasattr(constraint, 'constraint_type')
                assert hasattr(constraint, 'flexibility')

    def test_extract_constraints_individual_identifies_entity(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test constraint individuals identify constrained entity."""
        with patch('app.services.external_mcp_client.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_constraint_entities.return_value = []

            from app.services.extraction.dual_constraints_extractor import DualConstraintsExtractor

            extractor = DualConstraintsExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_constraints(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            if len(individuals) > 0:
                individual = individuals[0]
                assert hasattr(individual, 'constrained_entity')
                assert hasattr(individual, 'constraint_statement')

    def test_extract_constraints_stores_raw_response(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test raw response stored."""
        with patch('app.services.external_mcp_client.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_constraint_entities.return_value = []

            from app.services.extraction.dual_constraints_extractor import DualConstraintsExtractor

            extractor = DualConstraintsExtractor(llm_client=mock_llm_client)
            extractor.extract_dual_constraints(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            assert extractor.last_raw_response is not None
