"""
Service for associating guidelines with document sections, with multi-metric
relevance calculation and explainable reasoning.

Split from a single 1,259-line module into a package; the public surface is
unchanged and re-exported below, so `from app.services.guideline_section_service
import GuidelineSectionService` resolves exactly as before. Internals:
  - service.py           (GuidelineSectionService: association/retrieval +
                         world/triple loading + reasoning + search)
  - relevance_scoring.py (RelevanceScoringMixin: term overlap, structural
                         relevance, LLM analysis, final combination, mock fallback)
"""

from .service import GuidelineSectionService

__all__ = ["GuidelineSectionService"]
