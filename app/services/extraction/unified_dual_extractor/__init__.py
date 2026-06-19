"""unified_dual_extractor package.

Behavior-preserving split of the former ``unified_dual_extractor.py`` (services
modularization, 2026-06-19). The public dotted import path
``app.services.extraction.unified_dual_extractor`` is preserved: every symbol a
caller imported from the old module is re-exported here, so no call site changes.

Layout:
  config.py          per-concept tables + standalone prompt/context helpers
  prompt_building.py  PromptBuildingMixin   (template, prompt assembly, MCP load)
  llm_calls.py        LLMCallMixin          (streaming + tool-use LLM calls)
  parsing.py          ParsingMixin          (validation, normalization, JSON repair)
  matching.py         MatchingMixin         (ontology matching, linking)
  extractor.py        UnifiedDualExtractor   (__init__, extract orchestration)
"""
from app.services.extraction.unified_dual_extractor.config import (
    CONCEPT_CONFIG,
    CONCEPT_TYPE_TO_CORE_CATEGORY,
    CROSS_CONCEPT_DEPS,
    build_json_wrapper_suffix,
    format_cross_concept_context,
)
from app.services.extraction.unified_dual_extractor.extractor import (
    UnifiedDualExtractor,
)

__all__ = [
    "UnifiedDualExtractor",
    "CONCEPT_CONFIG",
    "CONCEPT_TYPE_TO_CORE_CATEGORY",
    "CROSS_CONCEPT_DEPS",
    "build_json_wrapper_suffix",
    "format_cross_concept_context",
]
