# Unified Case Pipeline -- Implementation Plan

**Started**: 2026-03-11
**Branch**: `unified-pipeline` (from `development`)

---

## Status Tracker

| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 1 | PSM rewrite + pipeline route/template | DONE | 15-substep hierarchy, 40 tests |
| 2 | Single-step Celery execution | DONE | SUBSTEP_DISPATCH, backfilled is_published |
| 3 | Interactive mode | DONE | WAITING_REVIEW, continue/stop, review bar |
| 4 | Step 4 substep expansion | DONE | 7 substeps dispatchable, force-cancel |
| 5 | Rollback and re-extraction | DONE | Cascade clearing, rerun, atomicity fix |
| 6 | Multi-case overview | DONE | Bulk progress bars, 5 SQL queries, 19 tests |
| 7 | URL migration + dead code removal | DONE | 11,522 lines removed, 7 commits, 631 tests |
| 8 | Codebase health (from repo audit) | NOT STARTED | See below |

631 tests pass, 2 skipped.

**Prior refactoring (Phases 1-4b on `development` branch, 14 commits not pushed):**
Editable install (46 sys.path hacks -> 0), OntServe config centralization (`ontserve_config.py`), legacy MCPClient gutted (727->144 lines), double-refresh fix, shared MCP transport, `run_all.py` extraction (1,713->360 lines), `qc_extraction.py` extraction (1,116->402 lines).

---

## Architecture Decisions

- **AD-1**: `PipelineStateManager` is the authoritative state source. `PipelineStatusService` retained for backward-compatible bulk queries.
- **AD-2**: Celery tasks are the only execution path. SSE streaming and blocking POST handlers are removed in Phase 7.
- **AD-3**: `step4_synthesis_service.py` is the unified Step 4 entry point. `step4_orchestration_service.py` retired in Phase 7.
- **AD-4**: Step 4 review pages stay, to be re-parented under `/cases/<id>/` in Phase 7.
- **AD-5**: Pipeline state is data-driven (artifacts in DB); pipeline mode is run-driven (`PipelineRun.config`).

---

## Phase 7: URL Migration + Dead Code Removal [NOT STARTED]

**Pre-read verification (2026-03-11)**: All files confirmed present. Dependency audit complete.

### Blast radius summary

- **24 templates** reference `scenario_pipeline` URLs (via `url_for` or hardcoded paths)
- **`_pipeline_steps.html`** is included by `base_step.html`, which is extended by ~20 templates
- **`interactive_builder.py`** is the blueprint definition hub -- shared by step1-3 AND step4/entity_review routes
- **`_case_pipeline_status.html`** is NOT dead -- included by `case_detail.html:79`

### 7a: Retire `step4_orchestration_service.py` + SSE `run_all.py`

Sole caller of `step4_orchestration_service.py` (1,413 lines) is `step4/run_all.py` (360 lines). No services, tasks, or tests depend on it. `step4_synthesis_service.py` handles all dispatch via Celery. Remove both files together. Update `step4/__init__.py` to remove `run_all` imports.

### 7b: Remove step1-3 page views and streaming routes

Files to remove entirely (all confirmed present, no external consumers):

| File | Lines | Notes |
|------|-------|-------|
| `app/routes/scenario_pipeline/step1.py` | 1,883 | Utility functions only used within scenario_pipeline package |
| `app/routes/scenario_pipeline/step2.py` | 940 | `_resolve_section_text` only called by step1_enhanced, step2_enhanced |
| `app/routes/scenario_pipeline/step3.py` | ~150 | No external callers |
| `app/routes/scenario_pipeline/step1_enhanced.py` | ~550 | Calls `_resolve_section_text` from step2 |
| `app/routes/scenario_pipeline/step2_enhanced.py` | ~550 | Calls `_resolve_section_text` from step2 |
| `app/templates/scenarios/step1c.html` | ~900 | Deprecated (routes commented out) |
| `app/templates/scenarios/step1c.html.clean` | stale | Backup file |
| `app/templates/scenarios/step1d.html` | ~1100 | Deprecated |
| `app/templates/scenarios/step1e.html` | ~370 | Deprecated |
| `app/templates/scenarios/step1_streaming.html` | ~200 | SSE streaming page |
| `app/templates/scenarios/step2_streaming.html` | ~200 | SSE streaming page |
| `app/templates/scenarios/step3_streaming.html` | ~200 | SSE streaming page |
| `app/templates/scenario_pipeline/builder.html` | ~200 | Outer frame for step views |

**Utility function decision**: `_load_existing_extractions`, `_resolve_section_text`, and `extract_individual_concept` are ONLY called within the `scenario_pipeline` route package. No services or tasks use them. They go away with the package. Individual concept re-extraction is handled by the pipeline rerun endpoint.

### 7c: Untangle `interactive_builder.py`

This is the blueprint definition hub (`interactive_scenario_bp`). It registers routes for step1-3 AND step4/entity_review. Cannot simply delete.

**Approach**: Remove step1-3 route registrations and CSRF exemptions. Keep:
- Blueprint definition and registration
- Step4 route wiring (overview, step4 views, entity review)
- API endpoint wiring for step4 (run_all SSE endpoints removed in 7a, but step4_entities/step4_review API endpoints remain)
- `complete_analysis` route wiring

Also update `app/__init__.py` to remove `init_step1_csrf_exemption` and `init_step2_csrf_exemption` imports.

### 7d: Update template references (24 files)

Three categories:

**Delete** (step1-3 templates already removed in 7b): step1c, step1d, step1e, streaming templates, builder.html

**Rewrite** `_case_pipeline_status.html`: Currently shows links to `scenario_pipeline.step1/step2/step3`. Replace content with a link to `/cases/<id>/pipeline` (the new pipeline dashboard). This partial is included by `case_detail.html:79`.

**Update surviving templates** that reference `scenario_pipeline.*`:
- `_pipeline_steps.html` (included by `base_step.html` -> 20+ templates): Update step links to point to pipeline dashboard
- `entity_review.html`, `entity_review_pass2.html`: Update back-links from `scenario_pipeline.step1/step2` to pipeline dashboard
- `step4.html`, `step4_entities.html`, `step4_review.html`: Update hardcoded `/scenario_pipeline/` JS fetch URLs
- `provenance.html`, `complete_analysis.html`: Update nav links
- `pipeline_dashboard/index.html`, `queue.html`: Update case links
- `tools/provenance_viewer.html`, `prompt_editor_step4.html`: Update links
- `entity_review/enhanced_temporal_review.html`: Update step3 link
- `scenario_pipeline/_review_tab_precedents.html`: Update overview link
- `scenarios/entity_review_all.html`: Update synthesis link

### 7e: URL redirects

For bookmarked or externally linked URLs, add redirect stubs in `interactive_builder.py`:

| Old URL pattern | Redirect to |
|----------------|-------------|
| `/scenario_pipeline/case/<id>/step1` | `/cases/<id>/pipeline` |
| `/scenario_pipeline/case/<id>/step2` | `/cases/<id>/pipeline` |
| `/scenario_pipeline/case/<id>/step3` | `/cases/<id>/pipeline` |
| `/scenario_pipeline/case/<id>/step4` | existing (keep for now) |
| `/scenario_pipeline/case/<id>/provenance` | existing (keep for now) |

### 7f: Robustness fixes (all confirmed in pre-read)

1. **WAITING_REVIEW auto-fail**: `_get_active_run()` at `pipeline.py:61-70` explicitly skips WAITING_REVIEW. Add 24-hour staleness threshold (auto-complete, not auto-fail, since the extraction already succeeded).
2. **TOCTOU race on dispatch**: No advisory lock or unique constraint on `PipelineRun`. Fix: `pg_advisory_xact_lock(case_id)` wrapping the check + create in `case_pipeline_dispatch()`. Note: `PipelineQueue` has `UniqueConstraint('case_id', 'status')` but `PipelineRun` does not.
3. **Dead `run_all` branch**: `run_step4_substep_task` line 888 of `pipeline_tasks.py`. The `else` case (implicit fall-through for `mode='run_all'`) is unreachable. Add `logger.warning` for defensive clarity.

### Phase 7 execution order

1. **7a first** (remove orchestration service + run_all SSE -- isolated, no template deps)
2. **7b second** (remove step1-3 routes and templates -- bulk deletion)
3. **7c third** (untangle interactive_builder.py -- depends on 7b knowing what's gone)
4. **7d fourth** (update surviving template references -- depends on 7b/7c)
5. **7e fifth** (add redirect stubs -- depends on 7c)
6. **7f last** (robustness fixes -- independent, lowest risk)

After each sub-phase: run tests, code review, mechanical grep for broken `url_for` references.

### Phase 7 risk assessment

| Sub-phase | Risk | Reason |
|-----------|------|--------|
| 7a | Low | Single caller, no cascading deps |
| 7b | Medium | Bulk file deletion, must verify no hidden imports |
| 7c | High | Blueprint shared by step1-3 and step4. Untangling requires careful route registration audit. |
| 7d | High | 24 templates, easy to miss a reference. Mechanical grep mandatory. |
| 7e | Low | Additive (new redirect routes) |
| 7f | Low | Isolated fixes, well-defined scope |

---

## Phase 8: Codebase Health [NOT STARTED]

Open items from the 2026-03-10 repository audit. Independent of pipeline work.

| ID | Item | Priority |
|----|------|----------|
| P2.3 | Implement missing recommendation engine models or remove dead guards (`recommendation_engine.py:18-35`) | HIGH |
| P2.4 | Reduce per-test truncation overhead (118 tables truncated per test) | HIGH |
| P3.2 | Standardize API key retrieval (os.getenv -> current_app.config) | MEDIUM |
| P3.3 | Audit and remove unnecessary ImportError chains (post-editable-install) | MEDIUM |
| P4.1 | Remove orphaned templates (4 experiment/ + create_case.html) | LOW |
| P4.3 | Replace bare `except:` in index.py with `except Exception as e: logger.warning(...)` | LOW |
| R6 | Fix health check (TCP socket -> HTTP/MCP handshake) | LOW |
| R7 | Address LRU cache staleness in MCPEntityEnrichmentService | LOW |
| R4 | Connection pooling for OntServe DB (defer until O1 MCP write tools) | LOW |

---

## Key Lessons (from refactoring + pipeline work)

- **Editable install**: Use hatchling + `pip install -e .`. List all importable packages in `packages = [...]`.
- **Bulk edits miss edge cases**: When removing `import sys`, also check for `sys.exit`, `sys.argv`. Use grep, not heuristic judgment.
- **Pre-read before planning**: Phase 2 scope changed after discovering config already existed.
- **Circular imports are predictable**: Extracting services from Flask route packages triggers `__init__.py` cascades. Use lazy imports.
- **Pre-existing bugs get copied**: Code review catches issues during extraction that were latent in the original.
- **Flask `request` dependencies are easy to miss**: Always pre-read to find `request.args`, `session`, `current_app` usage.
- **Two-pass review**: (1) Code review agent on modified files, (2) mechanical grep for orphaned variables and unused imports.

---

## Key Patterns (from Phases 1-6)

- `SUBSTEP_DISPATCH` maps every PSM substep to (task_func_name, kwargs) -- all 15 entries individually dispatchable
- Three-way terminal status: `single` -> COMPLETED, `interactive` -> WAITING_REVIEW, `run_all` -> parent handles
- Tasks reset `current_step` to canonical PSM name before setting terminal status
- `clear_cascade` does NOT commit -- caller owns the transaction for atomicity with PipelineRun creation
- Any service importing from `app.routes.scenario_pipeline.step4.*` triggers circular import via `step4/__init__.py`. Use lazy imports.
- `get_bulk_progress(case_ids)` uses 5 fixed SQL queries regardless of case count (N+1 avoidance)
- Section-aware substeps (pass1_facts vs pass1_discussion) produce same entity types but are distinguished by `extraction_prompts.section_type`

---

## Key Files

| File | Role |
|------|------|
| `app/services/pipeline_state_manager.py` | 15-substep WORKFLOW_DEFINITION, CheckType enum, `get_bulk_progress` |
| `app/routes/cases/pipeline.py` | Dashboard, dispatch, continue, stop, force-cancel, rerun |
| `app/templates/cases/pipeline.html` | Status view, polling, review bar, force-cancel, re-run |
| `app/tasks/pipeline_tasks.py` | All Celery tasks including `run_step4_substep_task` |
| `app/services/step4_synthesis_service.py` | `run_step4_substep` + SUBSTEP_RUNNERS |
| `app/services/cascade_clearing_service.py` | BFS downstream walk, cascade preview, clearing |
| `app/models/pipeline_run.py` | WAITING_REVIEW status |

---

*Last updated: 2026-03-11*
