"""Step-4 synthesis services.

Topical grouping (services modularization, Phase 5) of the loose Step-4 synthesis
modules: the Q&C leaf analyzers (question/conclusion/linker) + their row-storage
factory, rich analysis, FIRAC analysis, the synthesis dataclasses, step4 data
helpers, and the Celery synthesis orchestrator. Package marker only; import
concrete classes/functions from their submodules. (Distinct from the Phase-2
``synthesis/`` package and the ``case_synthesizer/`` package.)
"""
