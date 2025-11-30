"""
Unit tests for DualRoleExtractor.

Tests extraction logic with mock LLM responses for fast, reliable testing.
"""

import pytest
import json
from unittest.mock import patch, MagicMock


class TestDualRoleExtractor:
    """Tests for role extraction service."""

    def test_extract_roles_from_facts_returns_results(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that role extraction returns both classes and individuals."""
        # Import here to avoid app context issues
        with patch('app.services.extraction.dual_role_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_role_entities.return_value = []

            from app.services.extraction.dual_role_extractor import DualRoleExtractor

            extractor = DualRoleExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_roles(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            # Verify we got results
            assert isinstance(classes, list)
            assert isinstance(individuals, list)
            assert len(individuals) > 0, "Should extract at least one role individual"

    def test_extract_roles_individual_structure(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that extracted role individuals have required fields."""
        with patch('app.services.extraction.dual_role_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_role_entities.return_value = []

            from app.services.extraction.dual_role_extractor import DualRoleExtractor

            extractor = DualRoleExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_roles(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            assert len(individuals) > 0
            individual = individuals[0]

            # Check required fields
            assert hasattr(individual, 'name')
            assert hasattr(individual, 'role_class')
            assert hasattr(individual, 'attributes')
            assert hasattr(individual, 'relationships')
            assert hasattr(individual, 'confidence')

    def test_extract_roles_class_structure(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that extracted role classes have required fields."""
        with patch('app.services.extraction.dual_role_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_role_entities.return_value = []

            from app.services.extraction.dual_role_extractor import DualRoleExtractor

            extractor = DualRoleExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_roles(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            # Our mock data has at least one new class
            if len(classes) > 0:
                role_class = classes[0]
                assert hasattr(role_class, 'label')
                assert hasattr(role_class, 'definition')
                assert hasattr(role_class, 'distinguishing_features')
                assert hasattr(role_class, 'confidence')

    def test_extract_roles_discussion_section(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test role extraction from discussion section uses correct fixture."""
        with patch('app.services.extraction.dual_role_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_role_entities.return_value = []

            from app.services.extraction.dual_role_extractor import DualRoleExtractor

            extractor = DualRoleExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_roles(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='discussion'
            )

            # Discussion section should have BER-related content
            assert isinstance(individuals, list)
            # Check that mock client was called with correct section type
            calls = mock_llm_client.get_calls(extraction_type='roles')
            assert len(calls) == 1
            assert calls[0]['section_type'] == 'discussion'

    def test_extract_roles_stores_raw_response(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that raw LLM response is stored for debugging."""
        with patch('app.services.extraction.dual_role_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_role_entities.return_value = []

            from app.services.extraction.dual_role_extractor import DualRoleExtractor

            extractor = DualRoleExtractor(llm_client=mock_llm_client)
            extractor.extract_dual_roles(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            raw_response = extractor.get_last_raw_response()
            assert raw_response is not None
            # Should be valid JSON
            data = json.loads(raw_response)
            assert 'new_role_classes' in data or 'role_individuals' in data

    def test_extract_roles_handles_empty_response(self, mock_llm_client_factory, sample_case_text, sample_case_id):
        """Test graceful handling when LLM returns no results."""
        with patch('app.services.extraction.dual_role_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_role_entities.return_value = []

            from app.services.extraction.dual_role_extractor import DualRoleExtractor

            # Create client with empty response
            empty_client = mock_llm_client_factory.create_with_overrides({
                'roles_facts': {'new_role_classes': [], 'role_individuals': []}
            })

            extractor = DualRoleExtractor(llm_client=empty_client)
            classes, individuals = extractor.extract_dual_roles(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            # Should return empty lists, not error
            assert classes == []
            assert individuals == []

    def test_extract_roles_links_individuals_to_new_classes(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that individuals are correctly linked to newly discovered classes."""
        with patch('app.services.extraction.dual_role_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_role_entities.return_value = []

            from app.services.extraction.dual_role_extractor import DualRoleExtractor

            extractor = DualRoleExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_roles(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            # Get class labels
            class_labels = {c.label for c in classes}

            # Check if any individuals are marked as using new classes
            for individual in individuals:
                if individual.role_class in class_labels:
                    assert individual.is_new_role_class is True

    def test_extraction_summary_generated(
        self, mock_llm_client, sample_case_text, sample_case_id
    ):
        """Test that extraction summary is correctly generated."""
        with patch('app.services.extraction.dual_role_extractor.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()
            mock_mcp.return_value.get_all_role_entities.return_value = []

            from app.services.extraction.dual_role_extractor import DualRoleExtractor

            extractor = DualRoleExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_roles(
                case_text=sample_case_text,
                case_id=sample_case_id,
                section_type='facts'
            )

            summary = extractor.get_extraction_summary(classes, individuals)

            assert 'candidate_classes_count' in summary
            assert 'individuals_count' in summary
            assert summary['individuals_count'] == len(individuals)
