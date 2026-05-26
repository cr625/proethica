"""Archived scenario_pipeline route handlers (dead, retained for reference).

``complete_analysis.py`` backed the orphan ``/case/<id>/complete`` route. It
was unreachable from any UI nav and broken at runtime (its
``CaseExtractionPipeline`` raised ImportError on missing seed modules). The
route now redirects to the live ``cases.case_pipeline`` dashboard. Archived
2026-05-26; see ``docs-internal/reextraction/prompt-inventory.md``.
"""
