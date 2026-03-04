# ProEthica Codebase Improvement Roadmap

**Last verified**: 2026-03-03
**Branch**: `development`

## Current Metrics

| Metric | Value |
|--------|-------|
| Python files (`app/`) | 446 |
| Lines of code (`app/`) | 162,538 |
| Templates (total / archived) | 174 / 0 |
| Registered blueprints | 42 |
| URL rules | 540 |
| Files > 1,000 lines | 21 |
| Largest route file | `step1.py` (1,884 lines) |
| Largest service file | `guideline_analysis_service.py` (1,951 lines) |

Verification:
```bash
find app -name '*.py' -not -path '*__pycache__*' | wc -l
find app -name '*.py' -not -path '*__pycache__*' -exec cat {} + | wc -l
find app/templates -name '*.html' | wc -l
grep -c 'register_blueprint' app/__init__.py
```

---

## Completed Phases

### Phase 1: Dead Code Removal -- DONE

All items resolved across multiple sessions (2026-03-01 through 2026-03-03).

**Deleted route files** (7 files, ~1,877 lines):
- `cases_triple.py`, `debug_routes.py`, `entities.py`, `mcp_api.py` (unregistered blueprints)
- `characters.py`, `roles.py`, `resources.py`, `conditions.py`, `events.py` (legacy standalone CRUD, templates never existed)
- `admin_prompts.py` (all routes referenced missing `admin/prompts/` templates)

**Deleted service files** (2 files, ~1,373 lines):
- `enhanced_mcp_client.py`, `candidate_role_validation_service.py`

**Archived templates**: All 29 templates in 3 archive directories removed.

**Root artifacts resolved**:
- `models.py` renamed to `model_config.py` (collision with `app/models/`)
- `celery_config.py` -- kept, still imported by `health.py`, `pipeline_dashboard.py`, `pipeline_tasks.py`
- `ttl_triple_association/` -- kept, actively imported by `document_structure.py` and `prediction_service.py`

**Broken route cleanup**:
- `annotations.py`: removed `validation_dashboard` and `statistics` routes (missing `annotations/` template dir)
- `admin.py`: removed `audit_log` route and dashboard link (missing template, was hardcoded placeholder)

### Phase 2: Modularize `step4.py` -- DONE

`step4.py` (5,180 lines) replaced by `step4/` package (20 modules). Committed 2026-03-03.

```
app/routes/scenario_pipeline/step4/
    __init__.py, config.py, helpers.py, views.py,
    synthesis.py, entity_mgmt.py, provisions.py, precedents.py,
    decision_legacy.py, qc_extraction.py,
    run_all.py, streaming.py, phase3.py, phase4.py,
    conclusions.py, questions.py, complete_synthesis.py,
    transformation.py
```

### Phase 3: Modularize `worlds.py`, `cases.py`, `entity_review.py`, `scenarios.py` -- DONE

All four monolithic files replaced by packages. Committed 2026-03-03.

| Original | Lines | Package | Modules | Max Module |
|----------|-------|---------|---------|------------|
| `worlds.py` + 3 satellites | 4,683 | `worlds/` | 8 | `concepts.py` (1,241) |
| `cases.py` | 2,880 | `cases/` | 10 | `creation_processing.py` (785) |
| `entity_review.py` | 2,488 | `entity_review/` | 5 | `ontserve_ops.py` (830) |
| `scenarios.py` | 1,773 | `scenarios/` | 7 | `characters.py` (605) |

---

## Remaining Phases

### Phase 4: Service Consolidation

Minimum-intervention approach: delete confirmed dead files first, rename for clarity second, merge only where clearly duplicated.

#### 4a. MCP Clients (4 files, ~1,966 lines)

| File | Lines | Importers | Action |
|------|-------|-----------|--------|
| `mcp_client.py` | 745 | 11 | Keep -- primary general client |
| `external_mcp_client.py` | 318 | 20 | Keep -- pipeline extraction client |
| `ontserve_mcp_client.py` | 485 | 1 | Keep -- OntServe-specific API |
| `mcp_entity_enrichment_service.py` | 418 | 1 | Keep if imported; merge candidate |

#### 4b. Annotation Services (14 files, ~6,697 lines)

All 14 files are actively imported. Consolidation candidates (verify overlap first):
- `simple_annotation_service.py` (271) + `simplified_llm_annotation_service.py` (501)
- `intelligent_annotation_service.py` (585) + `llm_enhanced_annotation_service.py` (452)

**Target**: Reduce from 14 to ~10 files by merging confirmed duplicates.

#### 4c. LLM Services

Two independent patterns (`app/services/llm/` package vs `app/services/llm_service.py`). These serve different subsystems and should NOT be merged.

#### 4d. Case Synthesis (3 files, ~4,374 lines)

Distinct collaborating services. No merge needed. `decision_point_synthesizer.py` (1,609 lines) is a candidate for internal modularization if it grows.

### Phase 5: Configuration Cleanup

| File | Lines | Status |
|------|-------|--------|
| `config.py` (root) | 110 | Canonical Flask config |
| `app/config/__init__.py` | 108 | Compat shim; duplicates some settings from root config |
| `app/config/codespace.py` | 66 | Codespace-specific, 0 external importers |
| `app/services/llm/config.py` | 87 | LLM-specific, internal |
| `celery_config.py` (root) | 109 | Actively imported by 3 files |
| `model_config.py` (root) | 79 | Renamed from models.py |

**Recommended**: Audit `app/config/__init__.py` importers. If few remain, inline and delete. `celery_config.py` is NOT dead -- imported by `health.py`, `pipeline_dashboard.py`, `pipeline_tasks.py`.

### Phase 6: Documentation Cleanup

#### Stale planning documents

11 completed-plan files in `docs-internal/` should move to `docs-internal/archive/`:
POST_DEMO_TODO, ENTITY_RESOLUTION_PLAN, EXTRACTION_QUALITY_IMPROVEMENTS, GUIDELINES_IMPROVEMENT_PLAN, PIPELINE_NAVIGATION, PIPELINE_STATE_ARCHITECTURE, PROVENANCE_VISUALIZATION_RESEARCH, STEP4_PIPELINE_REFERENCE, VALIDATION_FRAMEWORK_UNIFIED, PHASE2_EXTRACTION_PLAN, PHASE2_IMPLEMENTATION_STEPS.

Also review `docs-internal/upgrades/` -- `step4-partial-extraction-tracker.md` and `scenario-pipeline-unification-plan.md` are likely stale.

#### Active reference documents (keep)

ONTOLOGY_OBJECT_PROPERTIES, VERIFICATION_CRITERIA, verify-case-reference, SERVER_SETUP, STYLE, TERMINOLOGY_SUMMARY, ACADEMIC_FRAMEWORKS, EXTRACTION_QUEUE, PIPELINE_PROMPT, NGINX_CACHING, CODEBASE_ANALYSIS, ONTSERVE_INTEGRATION_GUIDE.

### Other Known Issues

**Unregistered blueprint**: `documents_web_bp` defined in `app/routes/documents.py` (line 26) but never registered. Routes `/documents/download/<id>` and `/documents/status/<id>` are unreachable. Either register or fold into `documents_bp`.

**Orphaned templates** (7 confirmed): `world_dashboard.html`, `case_extracted_content.html`, `create_case_triple.html`, `guideline_triples_review.html`, `scenarios/step1.html`, `scenarios/step4.html`, `scenarios/step5.html`.

**`ttl_triple_association/`** at project root: Actively imported by `document_structure.py` and `prediction_service.py`. Should be relocated into `app/` for consistency, but is not dead code.

---

## Remaining Oversized Files

No CRITICAL-threshold (>2,000 lines) route files remain. Current oversized files:

| File | Lines | Severity | Notes |
|------|-------|----------|-------|
| `app/services/guideline_analysis_service.py` | 1,951 | HIGH | God-class pattern |
| `app/routes/scenario_pipeline/step1.py` | 1,884 | HIGH | Single concern (extraction) |
| `app/services/extraction/unified_dual_extractor.py` | 1,845 | HIGH | Core extractor |
| `app/routes/scenario_pipeline/step4/run_all.py` | 1,713 | HIGH | Batch execution |
| `app/services/decision_point_synthesizer.py` | 1,609 | HIGH | Single class |
| `app/services/ontserve_commit_service.py` | 1,568 | HIGH | Integration service |
| `app/services/case_synthesizer.py` | 1,506 | HIGH | Refactored 2026-02-22 |
| `app/services/auto_commit_service.py` | 1,259 | MEDIUM | |
| `app/services/guideline_section_service.py` | 1,257 | MEDIUM | |
| `app/routes/worlds/concepts.py` | 1,241 | MEDIUM | |

These are all single-concern files where further splitting would add complexity without clear benefit.

---

## Metrics History

| Metric | Pre-cleanup (Mar 1) | Post-cleanup (Mar 1) | Current (Mar 3) |
|--------|---------------------|---------------------|-----------------|
| Python files (`app/`) | ~457 | 424 | 446 |
| LOC (`app/`) | ~175,000 | 165,962 | 162,538 |
| Largest route file | 5,180 | 5,180 | 1,884 |
| Files > 1,000 lines | -- | 24 | 21 |
| Templates (total / archived) | ~256 / 29 | 227 / 29 | 174 / 0 |
| Registered blueprints | -- | 47 | 42 |
| URL rules | -- | 574 | 540 |

---

## Running the Maintenance Audit

Use the `repo-maintenance` agent to verify current state:

```
Run the repo-maintenance agent with a full audit (all 10 checks)
```

The agent produces a structured report with severity ratings, specific file paths, and recommended actions. It tracks deltas between runs to measure progress.
