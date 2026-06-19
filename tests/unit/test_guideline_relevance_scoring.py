"""
Golden-output characterization for the guideline relevance-scoring extraction
(plan: services-modularization.md, Phase 2 guideline_section_service).
_get_structural_relevance is a pure lookup matrix -- no DB/LLM/app context; called
unbound with a dummy self.
"""

from __future__ import annotations

from app.services.guideline_section_service.relevance_scoring import RelevanceScoringMixin


def _rel(section_type, entity_type):
    return RelevanceScoringMixin._get_structural_relevance(object(), section_type, entity_type)


def test_structural_relevance_matrix_values():
    assert _rel("facts", "condition") == 0.9
    assert _rel("discussion", "guideline") == 0.8
    assert _rel("conclusion", "guideline") == 0.9
    assert _rel("question", "condition") == 0.8


def test_structural_relevance_normalizes_section_type():
    # "discussion_1" normalizes to "discussion"
    assert _rel("discussion_1", "action") == 0.8


def test_structural_relevance_defaults_to_half():
    assert _rel("unknown_section", "condition") == 0.5   # unknown section
    assert _rel("facts", "unknown_entity") == 0.5        # unknown entity
