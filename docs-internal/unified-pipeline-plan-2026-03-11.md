# Unified Case Pipeline -- Implementation Plan

**Started**: 2026-03-11
**Branch**: `unified-pipeline` (branch from `development` after DB backup)
**Depends on**: Refactoring Phases 1-4b complete (clean imports, centralized config, service extraction)

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
| 1a | Fix PipelineStateManager blockers | DONE | pending | 15-substep flat hierarchy, 4 check types, section-aware |
| 1b | Validate PSM vs PSS agreement | DONE | pending | 40 tests, 10 PSS cross-checks pass |
| 1c | Pipeline route | DONE | pending | `/cases/<id>/pipeline` + status API |
| 1d | Pipeline template | DONE | pending | Read-only grouped substep view |
| 1e | Link from case detail | DONE | pending | Pipeline Dashboard button |
| 2 | Single-step execution | NOT STARTED | -- | Celery dispatch per substep |
| 3 | Interactive mode | NOT STARTED | -- | Pause/resume, review links |
| 4 | Step 4 substep expansion | NOT STARTED | -- | 7 individual Step 4 phases |
| 5 | Rollback and re-extraction | NOT STARTED | -- | Cascade clearing, ordering constraints |
| 6 | Multi-case overview | NOT STARTED | -- | Case list pipeline status enhancement |
| 7 | URL migration + dead code removal | NOT STARTED | -- | Remove old step pages, rewire nav |

---

## Implementation Review Findings (2026-03-11)

Pre-implementation code review of `PipelineStateManager`, `PipelineStatusService`, Celery tasks, and LangGraph usage. Findings organized by severity.

### PSM Blocker 1: Section-level indistinguishability

`pass1_facts` and `pass1_discussion` both define identical tasks (`roles`, `states`, `resources`) with the same `artifact_types`. The `check_task_complete()` method queries `temporary_rdf_storage.extraction_type` -- but both sections produce entities with the same extraction_type values (`roles`, `states`, `resources`). There is no `section_type` column on `temporary_rdf_storage`.

The only section discriminator is `extraction_prompts.section_type` (values: `facts`, `discussion`). `PipelineStatusService._check_extraction_step()` already uses this approach (lines 108-120): it queries `extraction_prompts` grouped by `section_type` and checks which sections have prompts.

**Fix**: Add section-aware completion checking to PSM. Replace the current artifact-only check with a hybrid approach: query `extraction_prompts.section_type` for section-level completion (same approach as `PipelineStatusService`), and query `temporary_rdf_storage` for artifact counts. The `WorkflowStepDefinition` needs a `section_type` field (e.g., `'facts'` or `'discussion'` or `None` for steps that have no section split).

### PSM Blocker 2: Missing reconciliation and commit steps

`WORKFLOW_DEFINITION` defines 7 entries: `pass1_facts`, `pass1_discussion`, `pass2_facts`, `pass2_discussion`, `pass3`, `step4`, `step5`. Three substeps are completely absent:

- `reconcile` -- checked by `PipelineStatusService._check_reconcile()` via `ReconciliationRun` model, but not in PSM
- `commit_extraction` -- checked via `is_published=true` count in `temporary_rdf_storage`, but not in PSM
- `commit_synthesis` -- not tracked anywhere currently

Step 4's prerequisites list `['pass3']`, but should require reconciliation + commit. The pipeline jumps from temporal extraction directly to case analysis, skipping entity reconciliation and OntServe commit.

**Fix**: Add `reconcile`, `commit_extraction`, `commit_synthesis` as top-level entries in `WORKFLOW_DEFINITION`. Each uses a custom completion check (not the standard artifact_types approach):

- `reconcile`: check for `ReconciliationRun` record OR `is_published=true` count > 0 (backward compat for cases committed before reconciliation feature, matching PSS logic at `_check_reconcile()` lines 178-179)
- `commit_extraction`: check for `is_published=true` count > 0
- `commit_synthesis`: check for Step 4 entities with `is_published=true`

This requires extending `TaskDefinition` with an optional `check_function` field for custom completion logic, or adding `check_type` enum (`'artifacts'`, `'reconciliation_run'`, `'published_entities'`, `'extraction_prompts'`).

### PSM Blocker 3: Narrative always-complete bug

The `narrative` TaskDefinition has `artifact_types=[]` and `min_artifacts=0`:

```python
TaskDefinition('narrative', 'Narrative Construction',
               [], 'phase4_narrative',  # Check prompt, not entities
               prerequisites=['decision_points'], min_artifacts=0)
```

`check_task_complete()` computes `total_artifacts = sum(counts.get(atype, 0) for atype in [])` which is 0, then `0 >= 0` is `True`. The narrative task reports as complete even if it has never been run.

The comment says "Check prompt, not entities" but no prompt check is implemented. `PipelineStatusService._check_step4()` correctly checks `extraction_prompts WHERE concept_type LIKE 'phase4%'`.

**Fix**: Implement a prompt-based completion check for narrative. Either:
- (a) Add a `check_type = 'extraction_prompts'` path that queries `extraction_prompts` for the `prompt_concept_type`, or
- (b) Set `min_artifacts=1` and add a synthetic artifact type like `'phase4_narrative'` that maps to the prompt check

Option (a) is cleaner because it extends to other prompt-based tasks.

### Additional Issue 1: `transformation_classification` untracked

The `transformation_classification` entity type exists in `PipelineStatusService.STEP4_PHASE2_TYPES` and is produced by the extraction pipeline, but has no corresponding `TaskDefinition` in PSM. The substep table includes it as step 11 (`step4_transformation`), but PSM's current `step4` block jumps from Q&C directly to `rich_analysis`.

**Fix**: Add a `transformation` TaskDefinition under step4, with prerequisites `['questions', 'conclusions']` and artifact_types `['transformation_classification']`.

### Additional Issue 2: `to_dict()` missing artifact counts

`PipelineState.to_dict()` includes task completion booleans but not artifact counts. The pipeline view template needs counts for badges (e.g., "12 roles", "5 obligations").

**Fix**: Add `artifact_counts` to the task dict in `to_dict()`. Use the already-cached `get_artifact_counts()` result.

### Additional Issue 3: `precedent_case_reference` missing

No `precedents` TaskDefinition exists in PSM's `step4` block. The substep table lists it as step 9 (`step4_precedents`), and `PipelineStatusService.STEP4_PHASE2_TYPES` includes it, but PSM skips it entirely.

**Fix**: Add a `precedents` TaskDefinition with artifact_types `['precedent_case_reference']` and prerequisites `['provisions']`.

---

## Technology Observations

### Celery + Flask (confirmed correct)

The existing `celery_config.py` patterns are correct per current Flask documentation:
- `ContextTask` wrapping all tasks in `app.app_context()` -- standard pattern
- `worker_prefetch_multiplier=1` -- correct for long-running tasks
- Redis on `localhost:6379/1` (DB 1 to avoid OntExtract conflicts) -- fine
- `task_time_limit=7200`, `task_soft_time_limit=6000` -- appropriate for extraction tasks

`self.update_state(state='PROGRESS', meta={...})` is the documented Celery pattern for custom progress reporting. The project stores progress in `PipelineRun` (PostgreSQL) instead, which is more durable than Redis-backed `AsyncResult` metadata. No changes needed.

### LangGraph (observation, not blocking)

Current usage (v0.4.7): linear `StateGraph` with 7 stages for Step 3 temporal dynamics, compiled without checkpointer (`builder.compile()` with no arguments). This works but does not leverage:

- `interrupt()` -- pauses graph execution for human-in-the-loop review. Would align naturally with the interactive pipeline mode (pause after each Step 4 sub-phase for review).
- `Command(resume=...)` -- resumes from an interrupt point with new data. Would support the "Continue" button in interactive mode.
- `MemorySaver` / `SqliteSaver` / `PostgresSaver` -- persistent checkpointing. Would allow recovery from worker crashes mid-extraction.

**Decision**: The current linear graph is adequate for Phase 1-3 of this plan. Checkpointing and interrupt support would be valuable for Phase 3 (interactive mode) and Phase 4 (Step 4 substep expansion), but adding them is a separate enhancement, not a prerequisite. Flag for Phase 3 design review.

### Execution Path Consolidation

Three execution paths currently exist:
1. **SSE streaming** (`step*_enhanced.py`): user stays on page, receives events via EventSource
2. **Blocking POST** (`step1.py`, `step2.py`): user stays on page, Flask blocks until extraction completes
3. **Celery tasks** (`pipeline_tasks.py`): background execution, user does not need to stay on page

After this plan, only path 3 survives. The consolidation happens gradually:
- Phases 1-5: build pipeline view using Celery tasks, old pages still functional
- Phase 7: remove old pages and SSE/blocking handlers

Step 4 has a dual implementation:
- `step4_orchestration_service.py` (1,413 lines) -- HTTP/SSE path, used by UI streaming
- `step4_synthesis_service.py` (976 lines) -- Celery path, has `progress_callback`

After Phase 4 of this plan, `step4_synthesis_service.py` becomes the sole Step 4 execution path. `step4_orchestration_service.py` is retired in Phase 7.

---

## Architecture Decisions

### AD-1: `PipelineStateManager` is the authoritative state source (after blocker fixes)

Two state managers exist: `PipelineStatusService` (used by current UI) and `PipelineStateManager` (newer, unused by UI). The state manager is the better foundation because:

- It defines explicit `WorkflowStepDefinition` with task-level prerequisites
- It has `TaskDefinition` with `artifact_types`, `prerequisites`, and `min_artifacts`
- It has a `PipelineState` class with `can_start()` and `get_blockers()` methods
- It supports a `progress_callback` pattern (NeMo-compatible)

**However**: PSM currently has 3 blockers and 3 additional issues (see Implementation Review Findings above). Phase 1a fixes these before the pipeline view can be built. Phase 1b validates that the fixed PSM agrees with PSS on known cases.

`PipelineStatusService` remains available for backward compatibility (case listing bulk queries via `get_bulk_simple_status()`).

### AD-2: Celery tasks are the only execution path

Currently three paths exist: SSE streaming (UI), blocking POST (legacy), Celery tasks. After this work:

- **Celery tasks** are the only way to run extraction (background, with progress tracking)
- **SSE streaming handlers** are removed (`step1_enhanced.py`, `step2_enhanced.py`, `step3_enhanced.py`)
- **Blocking POST handlers** are removed (extraction functions in `step1.py`, `step2.py`)
- **`run_pipeline.py` script** is removed (called SSE endpoints via HTTP)

The pipeline view dispatches Celery tasks and polls for status. No SSE.

### AD-3: `step4_synthesis_service.py` is the unified Step 4 entry point

The Step 4 execution currently has two paths: `step4_orchestration_service.py` (HTTP/SSE) and `step4_synthesis_service.py` (Celery). After this work:

- `step4_synthesis_service.py` becomes the sole Step 4 execution path (already has `progress_callback` support)
- `step4_orchestration_service.py` can be retired or merged
- `step4/run_all.py` becomes a thin route (or is removed if pipeline view handles all dispatch)

### AD-4: Step 4 review pages stay, re-parented under `/cases/<id>/`

The Step 4 analytical/editing views (`step4_entities.html`, `step4_review.html` with 8 tabs) are not extraction pages. They are inspection and curation tools. They stay as-is but move to `/cases/<id>/review` (or similar) and are linked from the pipeline view.

### AD-5: Pipeline state is data-driven, pipeline mode is run-driven

- **What's complete** is always derived from actual artifacts in `temporary_rdf_storage`, `extraction_prompts`, and `ReconciliationRun` (via `PipelineStateManager`)
- **What mode we're in** (automated vs interactive) is stored on the `PipelineRun` record
- A case can have multiple `PipelineRun` records (history). The pipeline view shows current state regardless of how it got there.

---

## Substep Definitions

The complete pipeline has 15 substeps. The current `WORKFLOW_DEFINITION` covers 6 steps with significant gaps (see Implementation Review Findings). Phase 1a extends it to the full 15.

| # | Substep ID | Display Name | Prerequisites | Artifacts / Check | Section |
|---|-----------|-------------|---------------|-------------------|---------|
| 1 | `pass1_facts` | Pass 1 -- Facts | -- | roles, states, resources | facts |
| 2 | `pass1_discussion` | Pass 1 -- Discussion | pass1_facts | roles, states, resources | discussion |
| 3 | `pass2_facts` | Pass 2 -- Facts | pass1_facts | principles, obligations, constraints, capabilities | facts |
| 4 | `pass2_discussion` | Pass 2 -- Discussion | pass2_facts | principles, obligations, constraints, capabilities | discussion |
| 5 | `pass3` | Pass 3 -- Temporal | pass2_facts | temporal_dynamics_enhanced | -- |
| 6 | `reconcile` | Reconcile | pass3 | ReconciliationRun record | -- |
| 7 | `commit_extraction` | Commit Entities | reconcile | is_published=true count > 0 | -- |
| 8 | `step4_provisions` | Provisions | commit_extraction | code_provision_reference | -- |
| 9 | `step4_precedents` | Precedents | step4_provisions | precedent_case_reference | -- |
| 10 | `step4_qc` | Questions & Conclusions | step4_provisions | ethical_question, ethical_conclusion | -- |
| 11 | `step4_transformation` | Transformation | step4_qc | transformation_classification | -- |
| 12 | `step4_rich_analysis` | Rich Analysis | step4_transformation | causal_normative_link, question_emergence, resolution_pattern | -- |
| 13 | `step4_phase3` | Decision Points | step4_rich_analysis | canonical_decision_point | -- |
| 14 | `step4_phase4` | Narrative | step4_phase3 | extraction_prompts LIKE 'phase4%' | -- |
| 15 | `commit_synthesis` | Commit Synthesis | step4_phase4 | Step 4 entities with is_published=true | -- |

**Section column**: Steps 1-2 have facts/discussion variants. `PipelineStateManager` must use `extraction_prompts.section_type` to distinguish them (see Blocker 1). Steps 3+ have no section split.

**Parallelism**: `step4_precedents` and `step4_qc` can run in parallel (both depend only on provisions). The task ordering above is the minimum dependency graph, not necessarily sequential.

---

## Phase 1: Pipeline View (Read-Only)

**Goal**: Create the per-case pipeline page showing current extraction state. No execution capability yet -- purely a status dashboard derived from existing data.

### 1a: Fix PipelineStateManager blockers

**File**: `app/services/pipeline_state_manager.py`

Six changes required, in order:

**1a-i: Add `section_type` to `WorkflowStepDefinition`**

```python
@dataclass
class WorkflowStepDefinition:
    name: str
    display_name: str
    tasks: List[TaskDefinition]
    prerequisites: List[str] = field(default_factory=list)
    route_name: str = ""
    section_type: Optional[str] = None   # 'facts', 'discussion', or None
    step_group: str = ""                 # visual grouping for UI
```

Then set `section_type='facts'` on `pass1_facts`, `pass2_facts` and `section_type='discussion'` on `pass1_discussion`, `pass2_discussion`.

**1a-ii: Add `check_type` to `TaskDefinition`**

```python
class CheckType(Enum):
    ARTIFACTS = "artifacts"                # Default: count in temporary_rdf_storage
    EXTRACTION_PROMPTS = "extraction_prompts"  # Check extraction_prompts table
    RECONCILIATION_RUN = "reconciliation_run"  # Check ReconciliationRun model
    PUBLISHED_ENTITIES = "published_entities"  # Check is_published=true count

@dataclass
class TaskDefinition:
    name: str
    display_name: str
    artifact_types: List[str]
    prompt_concept_type: str
    prerequisites: List[str] = field(default_factory=list)
    min_artifacts: int = 1
    check_type: CheckType = CheckType.ARTIFACTS
```

**1a-iii: Rewrite `check_task_complete()` to dispatch on `check_type`**

For `ARTIFACTS` (default): current behavior (count entities in `temporary_rdf_storage`).

For `EXTRACTION_PROMPTS`: query `extraction_prompts` WHERE `case_id` AND `concept_type` matches `prompt_concept_type`. Used by narrative task.

For `RECONCILIATION_RUN`: query `ReconciliationRun` WHERE `case_id`. Used by reconcile task.

For `PUBLISHED_ENTITIES`: query `temporary_rdf_storage` WHERE `case_id` AND `is_published=true`. The `extraction_type` filter depends on whether this is extraction commit (all types) or synthesis commit (Step 4 types only). Add an optional `published_types` field to `TaskDefinition`.

**Section-aware completion**: When the parent `WorkflowStepDefinition` has a `section_type`, the ARTIFACTS check additionally verifies that `extraction_prompts` has entries with matching `section_type` for the step's concept types. This mirrors the approach in `PipelineStatusService._check_extraction_step()` (lines 108-120).

**1a-iv: Flatten `WORKFLOW_DEFINITION` to 15 top-level steps**

**Structural change**: The current PSM uses a two-level hierarchy (`WorkflowStepDefinition` -> `TaskDefinition`). The pipeline view needs 15 independently addressable substeps. Rather than trying to encode the 15 substeps across mixed hierarchies (some top-level, some nested), flatten to 15 top-level `WorkflowStepDefinition` entries, each containing exactly one `TaskDefinition`.

This changes the public API:
- **Before**: `state.can_start('step4', 'questions')` (step + task)
- **After**: `state.can_start('step4_qc')` (step only, task parameter unused)

The `task` parameter on `can_start()`, `is_complete()`, `get_blockers()` becomes optional and rarely used. For steps with one task, `check_step_complete()` and `check_task_complete()` produce the same result. Cross-step prerequisites use step names (e.g., `prerequisites=['step4_provisions']`), not the old mixed `step4.provisions` addressing.

Steps like `pass1_facts` retain multiple sub-tasks for display purposes (roles, states, resources as individual badges), but the step-level completion check is what matters for prerequisite enforcement.

**Existing callers**: Search the codebase for `can_start(`, `is_complete(`, `get_blockers(`, `check_task_complete(`, `check_step_complete(` to find all call sites. Update any that use the two-argument form. The PSM docstring examples also need updating.

Add `reconcile`, `commit_extraction`, `commit_synthesis` as top-level workflow steps. Break `step4` into 7 individual workflow steps. Fix `narrative` to use `check_type=CheckType.EXTRACTION_PROMPTS`.

Full updated definition (15 entries):

- `pass1_facts` (section_type='facts', step_group='Pass 1')
- `pass1_discussion` (section_type='discussion', step_group='Pass 1')
- `pass2_facts` (section_type='facts', step_group='Pass 2')
- `pass2_discussion` (section_type='discussion', step_group='Pass 2')
- `pass3` (step_group='Pass 3')
- `reconcile` (step_group='Reconcile & Commit', check_type=RECONCILIATION_RUN)
- `commit_extraction` (step_group='Reconcile & Commit', check_type=PUBLISHED_ENTITIES)
- `step4_provisions` (step_group='Case Analysis', prerequisites=['commit_extraction'])
- `step4_precedents` (step_group='Case Analysis', prerequisites=['step4_provisions'])
- `step4_qc` (step_group='Case Analysis', prerequisites=['step4_provisions'])
- `step4_transformation` (step_group='Case Analysis', prerequisites=['step4_qc'])
- `step4_rich_analysis` (step_group='Case Analysis', prerequisites=['step4_transformation'])
- `step4_phase3` (step_group='Case Analysis', prerequisites=['step4_rich_analysis'])
- `step4_phase4` (step_group='Case Analysis', prerequisites=['step4_phase3'], check_type=EXTRACTION_PROMPTS)
- `commit_synthesis` (step_group='Publish', prerequisites=['step4_phase4'], check_type=PUBLISHED_ENTITIES)

**1a-v: Add artifact counts to `to_dict()`**

Include per-task artifact counts from the already-cached `get_artifact_counts()` result. The template uses these for badges.

**1a-vi: Remove `step5` from `WORKFLOW_DEFINITION`**

Step 5 (Interactive Scenario) is not part of the extraction pipeline managed by this dashboard. It is a separate feature accessed independently.

**Verification**:
```bash
cd /home/chris/onto/proethica
PYTHONPATH=/home/chris/onto:$PYTHONPATH python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app.services.pipeline_state_manager import PipelineStateManager
    m = PipelineStateManager()
    s = m.get_pipeline_state(7)
    d = s.to_dict()
    for step, info in d['steps'].items():
        print(f'{step}: {info[\"status\"]}')
"
```

Expected: case 7 (fully extracted + synthesized) shows all 15 substeps as `complete`.

### 1b: Validate PSM vs PSS agreement

**Goal**: Confirm the fixed PSM produces correct state by cross-referencing against the battle-tested `PipelineStatusService`.

**Method**: Write a validation script (or test) that runs both `PipelineStateManager.get_pipeline_state()` and `PipelineStatusService.get_step_status()` for a set of known cases and compares results:

- Case 7: fully extracted + synthesized (expect all complete)
- Case 4: fully extracted + synthesized (second demo case)
- A partially extracted case (if available)
- A case with no extraction (expect all not_started)

**Comparison mapping** (PSS fields that have PSM counterparts):

| PSS field | PSM substep | Notes |
|-----------|-------------|-------|
| `step1.facts_complete` | `pass1_facts` complete | |
| `step1.discussion_complete` | `pass1_discussion` complete | |
| `step2.facts_complete` | `pass2_facts` complete | |
| `step2.discussion_complete` | `pass2_discussion` complete | |
| `step3.complete` | `pass3` complete | |
| `reconcile.complete` | `reconcile` complete | PSS uses OR (ReconciliationRun OR committed>0); PSM must replicate this |
| `reconcile.committed` | `commit_extraction` complete | |
| `step4.phase2_complete` | `step4_transformation` AND `step4_rich_analysis` both complete | PSS checks both `transformation_classification` and `rich_analysis` core types |
| `step4.phase3_complete` | `step4_phase3` complete | |
| `step4.phase4_complete` | `step4_phase4` complete | |

**Substeps with no PSS counterpart** (verify via direct DB queries instead):

| PSM substep | Verification method |
|-------------|-------------------|
| `step4_provisions` | `SELECT COUNT(*) FROM extraction_prompts WHERE concept_type='code_provision_reference' AND case_id=?` |
| `step4_precedents` | `SELECT COUNT(*) FROM extraction_prompts WHERE concept_type='precedent_case_reference' AND case_id=?` |
| `step4_qc` | `SELECT COUNT(*) FROM extraction_prompts WHERE concept_type IN ('ethical_question','ethical_conclusion') AND case_id=?` |
| `step4_transformation` | `SELECT COUNT(*) FROM extraction_prompts WHERE concept_type='transformation_classification' AND case_id=?` |
| `commit_synthesis` | `SELECT COUNT(*) FROM temporary_rdf_storage WHERE case_id=? AND is_published=true AND extraction_type IN (Step 4 types)` |

Any disagreement on the mapped fields is a bug in the PSM fix. Resolve before proceeding. Disagreements on unmapped fields require manual DB inspection.

**Output**: A test in `tests/test_pipeline_state_manager.py` that can be re-run after future changes.

### 1c: Create pipeline route

**File**: `app/routes/cases/pipeline.py` (new)

Register under the cases blueprint at `/cases/<int:case_id>/pipeline`.

```python
@bp.route('/<int:case_id>/pipeline')
def case_pipeline(case_id):
    case = Document.query.get_or_404(case_id)
    manager = PipelineStateManager()
    state = manager.get_pipeline_state(case_id)
    return render_template('cases/pipeline.html', case=case, pipeline_state=state.to_dict())
```

Also add an API endpoint for AJAX status polling:
```python
@bp.route('/<int:case_id>/pipeline/status')
def case_pipeline_status(case_id):
    manager = PipelineStateManager()
    state = manager.get_pipeline_state(case_id)
    return jsonify(state.to_dict())
```

Register in `app/routes/cases/__init__.py`.

### 1d: Create pipeline template

**File**: `app/templates/cases/pipeline.html` (new)

Progressive substep boxes grouped by `step_group`. Each box shows:
- Substep display name
- Status indicator (color-coded: gray=pending, green=complete, red=error)
- Entity count badge (for complete steps, from `artifact_counts` in state dict)
- Link to provenance page (for complete extraction steps)
- Link to review page (for complete Step 4 sub-phases)

Layout: Horizontal flow within groups, groups stacked vertically. Use the same Bootstrap card/badge patterns as the existing case detail and pipeline dashboard. Dependency arrows between groups (CSS-only, no JS library).

No execution controls yet -- read-only. The "Run" buttons come in Phase 2.

### 1e: Link from case detail page

**File**: `app/templates/case_detail.html`

Add a "Pipeline" link/button near the existing `_case_pipeline_status.html` component. Both coexist during transition; the old component is removed in Phase 7.

### Phase 1 Verification

- Pipeline page loads for case 7 (demo case, fully extracted + synthesized) -- all 15 substeps green
- Pipeline page loads for a case with no extraction -- all 15 substeps gray
- Pipeline page loads for a partially extracted case -- correct mix of green/gray
- PSM and PSS agree on all test cases (Phase 1b test passes)
- Status API endpoint returns correct JSON
- All existing tests still pass (535+ passed, 0 failed)

### Phase 1 Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Section-aware check misidentifies facts/discussion | Medium | High | Phase 1b cross-validation against PSS |
| Reconciliation check false positive (backward compat path) | Low | Medium | PSS already handles this case; mirror logic |
| Narrative prompt check returns wrong concept_type | Low | Medium | Verify prompt_concept_type against actual DB values |
| New route conflicts with existing `/cases/<id>/...` routes | Low | Low | Verified no conflicts in `cases/__init__.py` |
| Template rendering slow (many DB queries per substep) | Medium | Low | PSM already batches artifact counts via single GROUP BY query; section check adds one more query |
| `to_dict()` returns stale cache after extraction | Low | Medium | `invalidate_cache()` called after Celery task completion (already in pipeline_tasks.py) |

---

## Phase 2: Single-Step Execution (Automated Mode)

**Goal**: Add execution controls. User can click "Run" on any available substep (or "Run All") to dispatch a Celery task.

### 2a: Substep-level Celery task dispatch

**File**: `app/tasks/pipeline_tasks.py`

The existing tasks (`run_step1_task`, `run_step2_task`, etc.) already handle individual steps. Need to add:

- A dispatcher function `run_substep_task(case_id, substep_id)` that maps substep IDs to existing Celery tasks
- `PipelineRun` creation for tracking (one run per dispatch, or one run for "Run All")
- Progress reporting via `PipelineRun.current_step` updates (already exists)

### 2b: Execution API endpoints

**File**: `app/routes/cases/pipeline.py`

Add POST endpoints:
- `POST /cases/<id>/pipeline/run` with `{substep: "pass1_facts"}` -- run single substep
- `POST /cases/<id>/pipeline/run-all` -- run all remaining substeps sequentially
- `GET /cases/<id>/pipeline/status` -- (already from 1c) poll for current state + active run

### 2c: Template execution controls

**File**: `app/templates/cases/pipeline.html`

Add to each substep box:
- "Run" button (enabled only when prerequisites met and not already running)
- "Run All" button at the top (dispatches all remaining in sequence)
- Status polling (JavaScript setInterval, 3-5 second refresh)
- Animated stripe on running substep
- Error display with retry button

### Phase 2 Dependencies

- Redis + Celery worker must be running
- Existing `pipeline_tasks.py` functions must work (they do -- tested during batch campaign)
- Need to verify each substep task can be called independently (currently `run_full_pipeline_task` calls `.apply()` sequentially)

### Phase 2 Verification

- Can start a single substep from the UI
- Substep runs in background, page shows progress
- Can run all remaining substeps
- Ordering is enforced (cannot run step2 before step1)
- PipelineRun record created and updated

---

## Phase 3: Interactive Mode

**Goal**: Add interactive mode where the pipeline pauses after each substep for user review.

### 3a: Mode toggle and waiting_review state

- Add `mode` field to `PipelineRun` model: `'automated'` or `'interactive'`
- Add `WAITING_REVIEW` to `PIPELINE_STATUS` enum
- In interactive mode, after each substep completes, set status to `waiting_review` instead of continuing to the next substep

### 3b: Review links

When a substep is in `waiting_review` state, the pipeline view shows:
- A "Review" link pointing to the appropriate page:
  - Pass 1-3 substeps: provenance page filtered to that pass
  - Reconcile: entity review page
  - Step 4 sub-phases: Step 4 review page (specific tab)
  - Commit: OntServe entity links
- A "Continue" button to resume the pipeline (dispatches next substep)
- A "Stop" button to halt the pipeline (user can resume later)

### 3c: Review page integration

The review/provenance pages need a "Back to Pipeline" link and optionally a "Continue Pipeline" button so the user can proceed without navigating back to the pipeline page.

### 3d: LangGraph integration assessment

Evaluate whether LangGraph's `interrupt()` / `Command(resume=...)` / checkpointing features (available in v0.4.7) would be beneficial for the interactive mode:
- `interrupt()` after each Step 4 sub-phase aligns with the pause-for-review pattern
- `PostgresSaver` checkpointer would allow crash recovery mid-extraction
- Decision: implement if the pattern simplifies Celery-based pause/resume logic. Otherwise defer.

### Phase 3 Verification

- Toggle between automated and interactive modes
- Pipeline pauses after each substep in interactive mode
- Review links go to correct pages
- Continue button dispatches next substep
- Stop button halts pipeline
- Can switch to automated mid-pipeline to finish remaining steps

---

## Phase 4: Step 4 Substep Expansion

**Goal**: Break Step 4 into individually triggerable sub-phases in the pipeline view.

### 4a: Decompose `run_step4_task`

Currently `run_step4_task` calls `run_step4_synthesis()` which runs all 7 sub-phases. Need to either:
- (a) Add individual Celery tasks per sub-phase, OR
- (b) Make `run_step4_synthesis()` accept a `substep` parameter to run a single sub-phase

Option (b) is lower risk. `step4_synthesis_service.py` already has a `progress_callback` -- extend it with a `stop_after` parameter.

### 4b: Ordering enforcement

Step 4 sub-phases have dependencies:
```
provisions --> precedents
           \-> qc --> transformation --> rich_analysis --> phase3 --> phase4
```

The `PipelineStateManager` already defines these prerequisites (after Phase 1a fixes). The pipeline view disables "Run" buttons for sub-phases whose prerequisites are incomplete.

### 4c: Parallel execution (stretch goal)

Precedents and Q&C can run in parallel (both depend only on provisions). The pipeline view could show them side-by-side and dispatch both simultaneously. Defer this unless the implementation is trivial.

### Phase 4 Verification

- Each Step 4 sub-phase can be triggered individually
- Ordering is enforced
- Status shows per-sub-phase completion
- Review link after Q&C goes to Q&C tab in step4_review

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

Implementation: Walk the `prerequisites` graph from the target substep, collect all downstream substeps, delete their artifacts from `temporary_rdf_storage` and `extraction_prompts`.

### 5b: Re-extraction UI

Each completed substep box gets a "Re-run" button (with confirmation dialog listing what will be cleared). After clearing, the pipeline view updates to show downstream steps as pending.

### 5c: Individual concept re-extraction

The existing `extract_individual_concept()` in `step1.py` lets you re-run just "roles" within a pass. This survives as an action on the provenance page or within the review view -- not on the pipeline view itself. The pipeline view operates at the substep level (pass1_facts, pass1_discussion), not individual concept types.

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

| File | Lines | Action |
|------|-------|--------|
| `app/routes/scenario_pipeline/step1.py` | 1,883 | Remove page views, blocking extraction. Keep `_load_existing_extractions`, `_resolve_section_text`, `extract_individual_concept` (move to service) |
| `app/routes/scenario_pipeline/step2.py` | 940 | Remove page views, blocking extraction. Keep `_resolve_section_text` (move to service) |
| `app/routes/scenario_pipeline/step1_enhanced.py` | 357 | Remove entirely |
| `app/routes/scenario_pipeline/step2_enhanced.py` | 404 | Remove entirely |
| `app/routes/scenario_pipeline/step3_enhanced.py` | ~200 | Remove entirely |
| `app/routes/scenario_pipeline/interactive_builder.py` | ~500 | Remove step1-3 route wiring, keep step4+ wiring (or remove if step4 re-parented) |
| `scripts/run_pipeline.py` | ~400 | Remove entirely (Celery replaces) |
| `app/templates/scenarios/step1_streaming.html` | 561 | Remove |
| `app/templates/scenarios/step1c.html` | 905 | Remove |
| `app/templates/scenarios/step1d.html` | 1,111 | Remove |
| `app/templates/scenarios/step1e.html` | 318 | Remove |
| `app/templates/scenarios/step2_streaming.html` | 577 | Remove |
| `app/templates/scenarios/step3_streaming.html` | 555 | Remove |
| `app/templates/scenario_pipeline/builder.html` | 268 | Remove (or keep if step4 views still use it) |
| `app/templates/cases/_case_pipeline_status.html` | 192 | Remove (replaced by pipeline view) |

**Estimated removal**: ~7,500+ lines of Python + ~4,500+ lines of templates

### 7c: Service extraction for surviving utility functions

Functions that survive the cleanup need to move from route files to service files:

| Function | Current Location | New Location |
|----------|-----------------|-------------|
| `_load_existing_extractions()` | `step1.py` | `app/services/extraction/extraction_utils.py` |
| `_resolve_section_text()` | `step2.py` (also used by enhanced) | Same service |
| `extract_individual_concept()` | `step1.py` | Same service (or keep in a slim route) |

### 7d: `step4_orchestration_service.py` retirement

After Phase 4 (Step 4 substep expansion), `step4_synthesis_service.py` becomes the sole Step 4 execution path. `step4_orchestration_service.py` (1,413 lines, created in Phase 4a of the refactoring) and the SSE streaming in `step4/run_all.py` can be removed.

Whether to do this depends on whether the Step 4 review pages still need the SSE streaming for in-page re-extraction. If all extraction goes through Celery, the SSE paths are dead.

### Phase 7 Verification

- All old URLs redirect correctly (or return appropriate errors)
- No broken imports
- No orphaned templates
- Full test suite passes
- The application starts and all pages render

---

## Existing Infrastructure Inventory

### What we build on (keep)

| Component | File | Role in new design |
|-----------|------|--------------------|
| `PipelineStateManager` | `app/services/pipeline_state_manager.py` | Primary state source (after Phase 1a fixes) |
| `PipelineStatusService` | `app/services/pipeline_status_service.py` | Bulk queries for case list; Phase 1b validation oracle |
| `PipelineRun` model | `app/models/pipeline_run.py` | Run tracking + mode |
| `PipelineQueue` model | `app/models/pipeline_run.py` | Batch queue management |
| Celery tasks | `app/tasks/pipeline_tasks.py` | All extraction execution |
| `step4_synthesis_service.py` | `app/services/step4_synthesis_service.py` | Step 4 execution |
| Step 4 review templates | `app/templates/scenario_pipeline/step4_*.html` | Analytical/editing views |
| Provenance view | `app/routes/provenance.py` + template | Extraction inspection |
| Pipeline dashboard | `app/routes/pipeline_dashboard.py` + template | Multi-case management |
| `concept_extraction_service.py` | `app/services/extraction/` | Core extraction logic |
| `unified_dual_extractor.py` | `app/services/extraction/` | Dual-pass extraction |

### What gets removed

See Phase 7b table above.

### What gets modified

| Component | Modification |
|-----------|-------------|
| `PipelineStateManager` | Extended workflow definition, section-aware checks, custom check types |
| `PipelineRun` model | Add `mode` field, `WAITING_REVIEW` status |
| `pipeline_tasks.py` | Add substep-level dispatch, interactive pause |
| Case detail template | Link to pipeline view |
| Case list template | Compact pipeline status per case |

---

## Execution Approach

Same as refactoring plan: implement each phase, add tests, run full suite, code review (2-pass), fix issues, update this plan with lessons learned, re-assess next phase.

After each phase:
1. Run `pytest tests/ -x -q` (must be 535+ passed, 0 failed)
2. Code review agent on modified files (bugs, orphaned imports, Flask context leaks)
3. Mechanical grep for orphaned variables and dead imports
4. Update Status Tracker table
5. Write Phase Review section with metrics, findings, lessons
6. Re-assess next phase scope based on findings

---

## Session Resume Instructions

**To resume**: Read this file first. Check the Status Tracker table. Phase 1 has five sub-phases (1a-1e). Read the Implementation Review Findings section for blocker context. Later phases are refined after each prior phase completes.

**Key files**:
- This plan: `docs-internal/unified-pipeline-plan-2026-03-11.md`
- Refactoring plan (for context): `docs-internal/refactor-plan-2026-03-10.md`
- State manager: `app/services/pipeline_state_manager.py`
- Status service: `app/services/pipeline_status_service.py` (validation oracle)
- Celery tasks: `app/tasks/pipeline_tasks.py`
- Step 4 synthesis: `app/services/step4_synthesis_service.py`

**Branch setup**: Create `unified-pipeline` branch from `development` after DB backup. See "Branch and Backup" section below.

---

## Branch and Backup

Before starting implementation:

```bash
# 1. Backup ProEthica database
PGPASSWORD=PASS pg_dump -h localhost -U postgres -d ai_ethical_dm -f /tmp/ai_ethical_dm_pre_pipeline_$(date +%Y%m%d).sql

# 2. Create feature branch
cd /home/chris/onto/proethica
git checkout development
git checkout -b unified-pipeline
```

The database backup is precautionary. Phases 1-5 do not modify the database schema (PSM changes are code-only). Phase 3 adds a `mode` column to `PipelineRun`, which is the first schema change. Back up again before that phase.

---

## Phase Reviews

### Phase 1 Review (2026-03-11)

**Commits**: 318b5d2 (1a+1b), a336350 (1c-e)
**Test count**: 575 passed, 2 skipped (was 535 before)

**Metrics**:
- `pipeline_state_manager.py`: 580 -> 480 lines (flattened, but denser)
- 40 new tests: 19 structural, 4 API mock, 4 to_dict, 12 PSM-vs-PSS integration, 1 convenience method
- Template: 234 lines (cases/pipeline.html)
- Route: 30 lines (cases/pipeline.py)

**Findings during implementation**:
1. `extraction_prompts.concept_type` uses plural forms (`roles`) matching `temporary_rdf_storage.extraction_type`, but `TaskDefinition.prompt_concept_type` uses singular (`role`). The section-aware check must use `artifact_types` (plural), not `prompt_concept_type` (singular).
2. `transformation_classification` produces prompts but no entities in `temporary_rdf_storage`. Must use `CheckType.EXTRACTION_PROMPTS`, not `CheckType.ARTIFACTS`.
3. `is_published` is not set for cases committed before the auto_commit_service tracked it (e.g., case 7). `commit_extraction` and `commit_synthesis` correctly report `not_started` for these cases; this is a data gap in old cases, not a PSM bug.
4. Code review caught: section check was using all tasks' artifact_types instead of the current task's. Fixed before commit.

**Lessons for Phase 2**:
- The `commit_extraction` prerequisite breaks the dependency chain for old cases (Step 4 substeps show `can_start=False` even though they ran). Phase 2 must handle this: either backfill `is_published` for existing cases, or add a "skip commit" override for the pipeline view.
- The `prompt_concept_type` vs `artifact_types` naming mismatch is confusing. Consider renaming `prompt_concept_type` to `provenance_key` in a future cleanup.
- Provenance route uses `provenance.provenance_case`, not the originally-assumed `provenance.provenance_view`. Always verify endpoint names against `app.url_map` before writing templates.
