# Unified Case Pipeline -- Implementation Plan

**Started**: 2026-03-11
**Branch**: `unified-pipeline` (from `development`)
**DB backup**: `/tmp/ai_ethical_dm_pre_pipeline_20260311.sql` (469MB)

---

## Goal

Replace the development-era step extraction pages (`/scenario_pipeline/case/<id>/step1`, `/step2`, `/step3`) with a unified, per-case pipeline dashboard that:

1. Shows all substeps as a progressive status timeline (pending / running / complete / needs review / error)
2. Supports two modes: **automated** (runs all steps) and **interactive** (pauses after each for review)
3. Runs extraction in background via Celery (user does not need to stay on page)
4. Links completed steps to provenance and review pages for inspection
5. Enforces step ordering: cannot run a step until its prerequisites are complete
6. Supports rollback: re-extracting an earlier step clears all subsequent steps
7. Lives with the case (`/cases/<id>/pipeline`) rather than under `/scenario_pipeline/`

---

## Status Tracker

| Phase | Description | Status | Commit | Notes |
|-------|-------------|--------|--------|-------|
| 1a | Fix PipelineStateManager blockers | DONE | 318b5d2 | 15-substep flat hierarchy, 4 check types, section-aware |
| 1b | Validate PSM vs PSS agreement | DONE | 318b5d2 | 40 tests, 10 PSS cross-checks pass |
| 1c | Pipeline route | DONE | a336350 | `/cases/<id>/pipeline` + status API |
| 1d | Pipeline template | DONE | a336350 | Read-only grouped substep view |
| 1e | Link from case detail | DONE | a336350 | Pipeline Dashboard button |
| 1-review | Code review fixes | DONE | 5951f4e | transformation_result fix, dead code removal |
| 2-prereq | Backfill is_published | DONE | (data only) | Case 7: 344 entities backfilled |
| 2 | Single-step execution | DONE | 53032f6 | Dispatcher, API, template with polling |
| 2-review | Code review fixes | DONE | 9c6f929 | Terminal status, stale runs, prerequisites |
| 3 | Interactive mode | DONE | -- | WAITING_REVIEW status, continue/stop endpoints, review bar |
| 3-review | Code review fixes | DONE | -- | 4 issues: stuck run, stale detection, step name, review bar |
| 4-prereq | Fix stuck RUNNING detection | DONE | -- | 2.5h auto-fail + force-cancel endpoint + UI button |
| 4 | Step 4 substep expansion | DONE | -- | 7 substeps dispatchable, STEP4_MONOLITHIC empty, 11 new tests |
| 5 | Rollback and re-extraction | DONE | -- | Cascade clearing service, rerun endpoint + UI, 24 new tests |
| 6 | Multi-case overview | NOT STARTED | -- | Case list pipeline status enhancement |
| 7 | URL migration + dead code removal | NOT STARTED | -- | Remove old step pages, rewire nav |

---

## Architecture Decisions (Summary)

- **AD-1**: `PipelineStateManager` is the authoritative state source. `PipelineStatusService` retained for backward-compatible bulk queries (`get_bulk_simple_status()`).
- **AD-2**: Celery tasks are the only execution path. SSE streaming and blocking POST handlers are removed in Phase 7.
- **AD-3**: `step4_synthesis_service.py` is the unified Step 4 entry point. `step4_orchestration_service.py` retired in Phase 7.
- **AD-4**: Step 4 review pages (`step4_entities.html`, `step4_review.html`) stay, to be re-parented under `/cases/<id>/` in Phase 7. Currently under `/scenario_pipeline/`.
- **AD-5**: Pipeline state is data-driven (artifacts in DB); pipeline mode is run-driven (`PipelineRun.config`).

---

## Phase 4: Step 4 Substep Expansion

**Goal**: Break Step 4 into individually triggerable sub-phases in the pipeline view.

### 4-prereq: Fix stuck RUNNING run detection

`_get_active_run()` auto-fails PENDING/PAUSED runs after 10 minutes but does not detect stuck RUNNING runs. If a Celery worker dies mid-task (OOM, machine restart, Redis disconnect), the PipelineRun stays RUNNING permanently and blocks all future dispatches for that case. Add a second stale check for RUNNING runs with a longer timeout (2.5 hours, just above the `task_time_limit=7200` Celery setting). Alternatively, add a manual "Force Cancel" button that marks the run as FAILED.

### 4a: Decompose `run_step4_task`

Currently `run_step4_task` calls `run_step4_synthesis()` which runs all 7 sub-phases. Need to either:
- (a) Add individual Celery tasks per sub-phase, OR
- (b) Make `run_step4_synthesis()` accept a `substep` parameter to run a single sub-phase

Option (b) is lower risk. `step4_synthesis_service.py` already has a `progress_callback` -- extend it with a `stop_after` parameter.

### 4a-dispatch: Update SUBSTEP_DISPATCH and STEP4_MONOLITHIC

After decomposition, the `step4_provisions` entry in `SUBSTEP_DISPATCH` must change from "dispatch `run_step4_task` (runs all 7 sub-phases)" to "dispatch provisions-only task." Each of the 6 entries in `STEP4_MONOLITHIC` moves into `SUBSTEP_DISPATCH` with its own task mapping. `STEP4_MONOLITHIC` becomes empty (or is removed).

**Gotcha**: `run_step4_task` currently sets `step_name = "step4"` (not `"step4_provisions"`). New individual tasks must use PSM-aligned step names (`step4_provisions`, `step4_qc`, etc.) from the start, matching the `WORKFLOW_DEFINITION` keys. The JS `STEP_NAME_MAP` must also be extended.

### 4b: Ordering enforcement

Step 4 sub-phases have dependencies:
```
provisions --> precedents
           \-> qc --> transformation --> rich_analysis --> phase3 --> phase4
```

The `PipelineStateManager` already defines these prerequisites. The pipeline view disables "Run" buttons for sub-phases whose prerequisites are incomplete.

### 4c: Parallel execution (stretch goal)

Precedents and Q&C can run in parallel (both depend only on provisions). Defer unless trivial.

### Phase 4 Verification

- Each Step 4 sub-phase can be triggered individually
- Ordering is enforced
- Status shows per-sub-phase completion
- Review link after Q&C goes to Q&C tab in step4_review

### Phase 4 Implementation Notes (from prior reviews)

- Move entries from `STEP4_MONOLITHIC` to `SUBSTEP_DISPATCH` as individual tasks are created; `_find_next_substep()` will automatically start dispatching them.
- The review bar's `showReviewBar()` maps substep names to review page URLs. Add Step 4 sub-phase to review tab mappings (e.g., step4_qc -> Q&C tab).
- The `current_step` reset pattern (set canonical name before terminal status) should be standardized from the start.
- The three-way terminal status pattern (`single` -> COMPLETED, `interactive` -> WAITING_REVIEW, `run_all` -> no terminal) must be replicated in any new Step 4 sub-phase tasks.

---

## Phase 5: Rollback and Re-extraction

**Goal**: Allow re-running an earlier substep, with automatic clearing of downstream data.

### 5a: Cascade clearing

When re-extracting a substep, all substeps that depend on it (directly or transitively) must have their artifacts cleared. The dependency graph from `PipelineStateManager` defines what needs clearing.

Example: Re-running `pass1_facts` clears:
- pass1_discussion (depends on pass1_facts)
- pass2_facts, pass2_discussion (depend on pass1_facts)
- pass3, reconcile, commit_extraction (transitive)
- All Step 4 sub-phases, commit_synthesis (transitive)

Implementation: Walk the `prerequisites` graph from the target substep, collect all downstream substeps, then clear:

1. `temporary_rdf_storage` rows (entities) for affected extraction types
2. `extraction_prompts` rows for affected concept types
3. `ReconciliationRun` records (if `reconcile` is in the downstream set)
4. `is_published` flags reset to `false` on surviving `temporary_rdf_storage` rows (if `commit_extraction` or `commit_synthesis` is downstream)
5. `CaseOntologyCommit` records (if commit steps are downstream)

**OntServe consideration**: If entities were already committed to OntServe, re-extraction creates a local/remote mismatch. Two options: (a) require a re-commit after re-extraction (simpler -- OntServe entities are overwritten on next commit), or (b) add a revocation step that removes OntServe entities before re-extraction. Option (a) is sufficient if the pipeline always re-commits after re-extraction. The confirmation dialog should note that OntServe entities will be stale until re-committed.

### 5b: Re-extraction UI

Each completed substep box gets a "Re-run" button (with confirmation dialog listing what will be cleared). After clearing, the pipeline view updates to show downstream steps as pending.

### 5c: Individual concept re-extraction

The existing `extract_individual_concept()` in `step1.py` lets you re-run just "roles" within a pass. This survives as an action on the provenance page or within the review view -- not on the pipeline view itself.

### Phase 5 Verification

- Re-running pass1_facts clears all downstream data
- Confirmation dialog shows what will be cleared
- After clearing, downstream steps show as pending
- Individual concept re-extraction still works from provenance/review pages

---

## Phase 6: Multi-Case Pipeline Overview

**Goal**: Show pipeline status across all cases in a compact view.

### 6a: Enhanced case list

The existing case list at `/cases/` shows a simple status badge (Not Started / Extracted / Synthesized). Replace with a compact pipeline progress indicator per case -- a mini version of the per-case pipeline timeline.

Alternatively, add a dedicated page at `/pipeline/cases` showing all cases with their pipeline status in a table/grid view.

### 6b: Bulk actions

From the multi-case view:
- Select multiple cases and "Run All" (dispatches automated pipelines via Celery queue)
- This replaces the current `/pipeline/queue` functionality with a more integrated UI

### Phase 6 Verification

- Case list shows pipeline progress per case
- Can identify which cases need extraction, which are partially done
- Bulk run dispatches correctly

---

## Phase 7: URL Migration + Dead Code Removal

**Goal**: Clean up old code, migrate URLs, remove development-era step pages.

### 7a: URL migration

| Old URL | New URL | Action |
|---------|---------|--------|
| `/scenario_pipeline/case/<id>/step1` | -- | Remove (pipeline view replaces) |
| `/scenario_pipeline/case/<id>/step2` | -- | Remove |
| `/scenario_pipeline/case/<id>/step3` | -- | Remove |
| `/scenario_pipeline/case/<id>/step4` | `/cases/<id>/review` | Redirect |
| `/scenario_pipeline/case/<id>/provenance` | `/cases/<id>/provenance` | Redirect |
| `/scenario_pipeline/case/<id>/step4/review` | `/cases/<id>/review` | Redirect |

Add redirect stubs for old URLs that may be bookmarked or linked from external docs.

### 7b: Dead code removal

**NOTE**: This table must be re-verified before starting Phase 7. Several files listed in the original plan (`step1_enhanced.py`, `step2_enhanced.py`, `step3_enhanced.py`, `scripts/run_pipeline.py`, `step*_streaming.html` templates) were already removed during the 2026-03-01 dead code cleanup.

Files confirmed still present (verify before Phase 7):

| File | Action |
|------|--------|
| `app/routes/scenario_pipeline/step1.py` | Remove page views, blocking extraction. Keep `_load_existing_extractions`, `_resolve_section_text`, `extract_individual_concept` (move to service) |
| `app/routes/scenario_pipeline/step2.py` | Remove page views, blocking extraction. Keep `_resolve_section_text` (move to service) |
| `app/routes/scenario_pipeline/interactive_builder.py` | Remove step1-3 route wiring, keep step4+ wiring (or remove if step4 re-parented) |
| `app/templates/scenarios/step1c.html` | Remove |
| `app/templates/scenarios/step1d.html` | Remove |
| `app/templates/scenarios/step1e.html` | Remove |
| `app/templates/scenario_pipeline/builder.html` | Remove (or keep if step4 views still use it) |
| `app/templates/cases/_case_pipeline_status.html` | Remove (replaced by pipeline view) |

Run `glob` to verify file existence before starting removal.

### 7c: Service extraction for surviving utility functions

| Function | Current Location | New Location |
|----------|-----------------|-------------|
| `_load_existing_extractions()` | `step1.py` | `app/services/extraction/extraction_utils.py` |
| `_resolve_section_text()` | `step2.py` (also used by enhanced) | Same service |
| `extract_individual_concept()` | `step1.py` | Same service (or keep in a slim route) |

### 7d: `step4_orchestration_service.py` retirement

After Phase 4, `step4_synthesis_service.py` becomes the sole Step 4 execution path. `step4_orchestration_service.py` (1,413 lines) and the SSE streaming in `step4/run_all.py` can be removed if all extraction goes through Celery.

### Phase 7 Verification

- All old URLs redirect correctly (or return appropriate errors)
- No broken imports
- No orphaned templates
- Full test suite passes
- The application starts and all pages render

---

## Execution Approach

Same as refactoring plan: implement each phase, add tests, run full suite, code review (2-pass), fix issues, update this plan with lessons learned, re-assess next phase.

After each phase:
1. Run `pytest tests/ -x -q` (must be 575+ passed, 0 failed)
2. Code review agent on modified files (bugs, orphaned imports, Flask context leaks)
3. Mechanical grep for orphaned variables and dead imports
4. Update Status Tracker table
5. Write Phase Review section with metrics, findings, lessons
6. Re-assess next phase scope based on findings

---

## Session Resume Instructions

**To resume**: Read this file first. Check the Status Tracker table for current phase. Phases 1-3 are complete with code review.

**Key files**:
- This plan: `docs-internal/unified-pipeline-plan-2026-03-11.md`
- State manager: `app/services/pipeline_state_manager.py` (15-substep WORKFLOW_DEFINITION, CheckType enum)
- Pipeline route: `app/routes/cases/pipeline.py` (dispatch, continue, stop endpoints)
- Pipeline template: `app/templates/cases/pipeline.html` (status view, polling, review bar)
- Celery tasks: `app/tasks/pipeline_tasks.py` (run_id, mode-aware terminal status)
- Pipeline run model: `app/models/pipeline_run.py` (WAITING_REVIEW status)
- Step 4 synthesis: `app/services/step4_synthesis_service.py`

**Key patterns established in Phases 1-3**:
- `SUBSTEP_DISPATCH` / `STEP4_MONOLITHIC` dicts in `pipeline.py` control dispatchability
- Three-way terminal status: `single` -> COMPLETED, `interactive` -> WAITING_REVIEW, `run_all` -> parent handles
- `_find_next_substep()` walks `WORKFLOW_DEFINITION` in insertion order, skips STEP4_MONOLITHIC
- Tasks reset `current_step` to canonical name before setting terminal status
- Stale detection targets PENDING/PAUSED only (not WAITING_REVIEW)
- CSRF exemption uses `app.view_functions[endpoint]` function refs, not string names

---

## Phase Reviews

### Phases 1-3 Key Lessons

**Data model findings**:
- `extraction_prompts.concept_type` uses plural forms (`roles`) matching `temporary_rdf_storage.extraction_type`, but `TaskDefinition.prompt_concept_type` uses singular (`role`). Section-aware checks must use `artifact_types` (plural).
- `transformation_classification` produces prompts but no entities in `temporary_rdf_storage`. Uses `CheckType.EXTRACTION_PROMPTS`.
- `commit_synthesis.published_types` must use `transformation_result` (not `transformation_classification`) -- the actual `extraction_type` value.
- `is_published` was not set for cases committed before auto_commit_service. Fixed with one-time backfill (case 7: 344 entities).

**Flask/Celery patterns**:
- Flask-WTF `csrf.exempt()` requires function references via `app.view_functions[endpoint]`, not string endpoint names.
- Celery task `current_step` values (e.g., `"step1_facts_parallel"`) do not match PSM substep names (e.g., `"pass1_facts"`). JS mapping table (`STEP_NAME_MAP`) required.
- `run_step4_task` uses `step_name = "step4"` (not `"step4_provisions"`) -- a mismatch with the PSM substep name. Phase 4 individual tasks must use PSM-aligned names from the start.
- Context processors that inject DB-querying callables are wasteful. Use explicit template context from routes.

**Interactive mode design**:
- Dispatches individual substeps rather than modifying `run_full_pipeline_task` with interrupt logic. Avoids Celery task pause/resume complexity.
- WAITING_REVIEW falls through stale detection because the check only targets PENDING/PAUSED.
- `set_status()` does not set `completed_at` for WAITING_REVIEW -- duration continues counting during review.
- No DB migration needed: `config.mode` is JSONB, WAITING_REVIEW is a string value.

### Phase 4 Review

**Changes (4-prereq + 4a + 4a-dispatch + 4b)**:

*4-prereq (stuck RUNNING detection)*:
- `_get_active_run()` now auto-fails RUNNING runs stuck >2.5 hours (above `task_time_limit=7200` + 30min buffer)
- New `force-cancel` endpoint (`POST /cases/<id>/pipeline/force-cancel`) marks any active run as FAILED
- UI shows "Cancel" button after 5 minutes of RUNNING, calls force-cancel with confirmation dialog

*4a (decompose synthesis service)*:
- `step4_synthesis_service.py`: Added `SUBSTEP_RUNNERS` mapping (7 entries) and `run_step4_substep()` dispatcher
- Ported `_run_precedents()` from `step4_orchestration_service.py` -- was missing from synthesis service entirely
- Added precedent extraction to monolithic `run_step4_synthesis()` between provisions and Q&C
- Extracted `_get_all_case_entities()` as a shared module-level helper

*4a-dispatch (update dispatch maps)*:
- `SUBSTEP_DISPATCH`: 7 Step 4 entries added, all mapping to `run_step4_substep_task`
- `STEP4_MONOLITHIC`: now `set()` (empty)
- New Celery task `run_step4_substep_task` (name: `proethica.tasks.run_step4_substep`): dispatches to `run_step4_substep()`, uses PSM-aligned step names for `current_step`
- `_get_task_func()` updated to resolve the new task
- Template: removed "Part of Step 4" labels, all substeps get Run buttons
- JS: `PSM_SUBSTEP_NAMES` set for direct matching, `resolveRunningStep` handles `substep: message` progress format and legacy stage names

*4b (ordering enforcement)*:
- Already handled by PSM `prerequisites` in `WORKFLOW_DEFINITION`. The `can_start()` / `get_blockers()` checks enforce the dependency graph. No additional code needed.

**Findings**:
- Precedent extraction was absent from the synthesis service. The PSM defined `step4_precedents` but the monolithic `run_step4_synthesis` never called it. Cases extracted via `run_full_pipeline_task` were missing precedent data unless the old orchestration service was used separately.
- The old `run_step4_task` (monolithic) is retained for backward compatibility with `run_full_pipeline_task` and `resume_pipeline_task`. Phase 7 can remove it when those functions are refactored to use individual substep tasks.

**Test delta**: 575 -> 586 (+11 tests in `test_pipeline_dispatch.py`)

**Files modified**:
- `app/routes/cases/pipeline.py` (dispatch maps, stuck detection, force-cancel)
- `app/tasks/pipeline_tasks.py` (new `run_step4_substep_task`)
- `app/services/step4_synthesis_service.py` (`run_step4_substep`, `_run_precedents`, `SUBSTEP_RUNNERS`)
- `app/templates/cases/pipeline.html` (remove monolithic labels, force-cancel button, updated JS)
- `tests/test_pipeline_dispatch.py` (new, 11 tests)
- `docs-internal/unified-pipeline-plan-2026-03-11.md` (this update)

### Phase 5 Review

**Changes (5a + 5b)**:

*5a (cascade clearing service)*:
- New `app/services/cascade_clearing_service.py` with three public functions:
  - `get_downstream_substeps(target)`: BFS reverse-walk of WORKFLOW_DEFINITION prerequisites graph. Returns downstream substeps in WORKFLOW_DEFINITION order.
  - `get_cascade_preview(target)`: Builds confirmation dialog data (affected count, display names, will_clear_reconciliation, will_clear_commits).
  - `clear_cascade(case_id, target)`: Clears target + all downstream substep artifacts. Does NOT commit (caller-controlled transaction).
- Per-substep clearing handles all four CheckTypes:
  - ARTIFACTS: Delete TRS entities by extraction_type, with session-based scoping for section-aware substeps (uses extraction_session_id from extraction_prompts).
  - EXTRACTION_PROMPTS: Section-aware prompts by concept_type + section_type (Steps 1-2), step_number=3 (pass3), step_number=4 + prompt_concept_type (Step 4). Phase4 uses LIKE pattern for `phase4%`.
  - RECONCILIATION_RUN: Delete ReconciliationRun records (cascade deletes decisions).
  - PUBLISHED_ENTITIES: Reset is_published/committed_at/content_hash. Delete CaseOntologyCommit records.

*5b (re-run endpoint + UI)*:
- `GET /cases/<id>/pipeline/rerun-preview?substep=X`: Returns cascade preview for confirmation dialog
- `POST /cases/<id>/pipeline/rerun`: Calls clear_cascade, creates PipelineRun (with `rerun: true` in config), dispatches Celery task. Clearing + PipelineRun creation in same transaction.
- CSRF exemption added for rerun endpoint
- Template: Re-run button (orange arrow-counterclockwise icon) on completed substep cards. JS `rerunSubstep()` fetches preview, shows confirm() dialog listing all affected steps, then dispatches. Re-run buttons hidden during active runs.

**Code review findings (4 issues)**:
1. `commit_extraction` unpublishes ALL entities (published_types=None) -- analyzed as safe because step4_* substeps are always downstream when commit_extraction is in the clearing set, so synthesis entities get deleted regardless. Added clarifying comment.
2. `rerun-preview` has no auth decorator -- consistent with existing pattern (case_pipeline_status is also an unauthenticated GET). No change.
3. artifact_types vs prompt_concept_type for section-aware prompt clearing -- code is correct because extraction_prompts.concept_type uses plural forms matching artifact_types (confirmed in Phase 1 lessons).
4. `clear_cascade` committed before route could create PipelineRun -- fixed by removing db.session.commit() from clear_cascade, letting the route commit clearing + run creation atomically.

**Test delta**: 587 -> 611 (+23 tests in `test_cascade_clearing.py`, +1 in `test_pipeline_dispatch.py`)

**Files created**:
- `app/services/cascade_clearing_service.py` (cascade walker + clearing logic)
- `tests/test_cascade_clearing.py` (23 tests: dependency walker, preview, clearing, section scoping, step4 prompts)

**Files modified**:
- `app/routes/cases/pipeline.py` (rerun-preview + rerun endpoints, CSRF exemption)
- `app/templates/cases/pipeline.html` (re-run button, rerun JS functions, URL constants)
- `tests/test_pipeline_dispatch.py` (+1 CSRF exemption test)
- `docs-internal/unified-pipeline-plan-2026-03-11.md` (this update)

**Key patterns**:
- `clear_cascade` does NOT commit -- caller owns the transaction. This enables atomic clearing + PipelineRun creation in the rerun endpoint.
- Re-run uses the same dispatch path as single-step run (SUBSTEP_DISPATCH + _get_task_func) with `rerun: true` in PipelineRun config for provenance.
- Confirmation dialog is server-driven: the preview endpoint computes affected steps so the client doesn't need to duplicate the dependency graph.
