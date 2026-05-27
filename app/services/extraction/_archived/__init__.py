"""Archived extraction code (dead, retained for reference).

These modules implemented the original "complete modular analysis" case
pipeline (``CaseExtractionPipeline`` / ``PassOrchestrator``) and its seed
prompt builders. They are SUPERSEDED by the live per-step pipeline:
``app/services/extraction/unified_dual_extractor.py`` renders the editable
``extraction_prompt_templates`` DB rows, driven by
``app/tasks/pipeline_tasks.py`` (run_step1/2/3_task) behind the
``cases.case_pipeline`` dashboard.

Why archived (2026-05-26): the only caller was the orphan
``/scenario_pipeline/case/<id>/complete`` route, which was unreachable from
any UI nav and already broken at runtime -- ``PassOrchestrator.__init__``
imports ``enhanced_prompts_actions`` and ``enhanced_prompts_events`` modules
that no longer exist, so instantiating ``CaseExtractionPipeline`` raised
ImportError. See ``docs-internal/reextraction/prompt-inventory.md``.

LIVE siblings NOT archived: ``enhanced_prompts_roles_resources.py`` (used by
the guideline analyzer via ``roles.py``/``resources.py``) and
``enhanced_prompts_defeasibility.py`` (used by the defeasibility-edge
extractor).
"""
