#!/usr/bin/env python3
"""
Test GuidelineConceptTypeMapper basic functionality.

Note: The mapper uses database lookups for historical mappings.
These tests verify the mapper works without database access,
using only its static mapping rules.
"""

import pytest
from app.services.guideline_concept_type_mapper import GuidelineConceptTypeMapper


def test_type_mapper_initialization():
    """Test that type mapper initializes without errors."""
    mapper = GuidelineConceptTypeMapper()
    assert mapper is not None


def test_type_mapper_returns_result():
    """Test that type mapper returns a valid result object."""
    mapper = GuidelineConceptTypeMapper()
    result = mapper.map_concept_type("Role", "A professional role", "Engineer")

    assert result is not None
    assert hasattr(result, 'mapped_type')
    assert hasattr(result, 'confidence')
    assert hasattr(result, 'justification')


def test_type_mapper_exact_type_match():
    """Test that exact type names are recognized."""
    mapper = GuidelineConceptTypeMapper()

    # When LLM type exactly matches a core type, it should map correctly
    result = mapper.map_concept_type("Role", "A professional role", "Engineer")
    assert result.mapped_type == "role"
    assert result.confidence >= 0.8


def test_type_mapper_confidence_bounds():
    """Test that confidence scores are within valid range."""
    mapper = GuidelineConceptTypeMapper()

    result = mapper.map_concept_type("unknown", "Some description", "Concept X")
    assert 0.0 <= result.confidence <= 1.0


def test_type_mapper_handles_empty_input():
    """Test that type mapper handles empty/missing input gracefully."""
    mapper = GuidelineConceptTypeMapper()

    # Empty description - should not crash
    result = mapper.map_concept_type("unknown", "", "Some Concept")
    assert result.mapped_type is not None

    # Empty name - should not crash
    result = mapper.map_concept_type("unknown", "Some description", "")
    assert result.mapped_type is not None


def test_type_mapper_result_has_justification():
    """Test that mapping results include justification."""
    mapper = GuidelineConceptTypeMapper()

    result = mapper.map_concept_type("Principle", "An ethical principle", "Safety First")
    assert result.justification is not None
    assert len(result.justification) > 0
