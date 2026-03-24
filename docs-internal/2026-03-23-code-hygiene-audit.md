# Code Hygiene Audit

**Date**: 2026-03-23
**Branch**: development
**Scope**: Full codebase audit (438 Python files, ~153K lines)

## Completed

### Tier 1 (commit `4195937`)

| Fix | Files | Detail |
|-----|-------|--------|
| Bare `except:` eliminated | 18 | 28 blocks converted to `except Exception:` with `logger.debug/warning` |
| Silent `except Exception: pass` in extraction | 10 | Import guards narrowed to `except ImportError:`; 24 LLM fallback chains now log at debug level |
| Hardcoded DB credentials removed | 2 | `ttl_triple_association/` services now read `DATABASE_URL` from environment |
| Config bypass fixed | 8 | `os.environ.get("ONTSERVE_*")` replaced with `current_app.config` (routes) or `ontserve_config` functions (services) |

### Tier 1b (commit `31336bf`)

| Fix | Files | Detail |
|-----|-------|--------|
| `print()` converted to `logger` | 23 | ~190 calls converted across routes, services, utils, models |

Excluded from conversion (intentional `print` usage):
- `app/__init__.py` -- startup diagnostics before logging is configured
- `ttl_triple_association/cli.py` -- CLI user-facing output
- Docstring examples and `if __name__ == '__main__':` blocks

### Tier 2 (commits `317f7a7`, `7373368`, `88ce9e7`)

| Fix | Files | Detail |
|-----|-------|--------|
| Inverted dependency fixed | 3 | 5 functions moved from `routes/step4/helpers.py` to `services/step4_data_helpers.py`; route module re-exports for backward compatibility |
| Fat model refactored | 2 | `TemporaryRDFStorage` 517 lines to 204 lines; `store_extraction_results` + helpers moved to `services/rdf_storage_service.py` |
| Helper service commits removed | 2 | `entity_merge_service.py` (3 commits removed), `step4_data_helpers.py` (1 commit removed) |
| Dead code removed | -- | `clear_case_session` (zero callers), `DecisionEngine`, `EnhancedDecisionEngine` (deleted in prior commits) |

---

## Remaining Work

### Tier 2 (continued)

**Transaction convention audit** -- 50 service files still contain `db.session.commit()`. The extraction pipeline helpers are fixed; the remaining files fall into two categories:

- *Entry-point services* (called from Celery tasks or routes): commits are appropriate. No change needed.
- *Helper services* (called by other services): commits should be removed, callers should own the boundary.

The convention: **services and models do not commit. Routes and Celery task entry points own the transaction.** Services that follow this convention already document it in their module docstring (`cascade_clearing_service`, `rdf_storage_service`, `entity_merge_service`, `step4_data_helpers`).

Files to audit next (helper services with internal commits, outside extraction pipeline):

| File | Commits | Called by |
|------|---------|----------|
| `embedding_service.py` | 6 | routes, other services |
| `temporary_concept_service.py` | 5 | routes |
| `simulation_storage.py` | 5 | routes |
| `entity_triple_service.py` | 4 | routes, services |
| `guideline_analysis_service.py` | 3 | routes |
| `case_synthesizer.py` | 3 | Celery tasks |
| `application_context_service.py` | 3 | routes |

Approach: audit each file individually. For each `db.session.commit()`, determine whether the caller already commits. Remove if redundant; leave if the service is a top-level entry point.

### Tier 3

| Item | Description | Effort |
|------|-------------|--------|
| **JSON response envelope** | Standardize API responses on `{"success": bool, "data": ..., "error": ...}`. Currently mixed: some use `{"error": str}`, some use `{"success": False, "message": ...}`, some return bare dicts. Add a `jsonify_response()` helper. | Medium |
| **Route fat trimming** | `cases/listing.py` has raw SQL via `db.engine.connect()` and duplicated metadata normalization between `list_cases()` and `search_cases()`. `prompt_builder.py` has 10 raw SQL queries where ORM would work. Move to service layer. | Medium |
| **psycopg2 in view.py** | `cases/view.py:145-160` opens a raw psycopg2 connection to OntServe inside a route handler. Move to `ontserve_commit_service.py` or a dedicated query service. | Low |
| **Stale placeholders** | `routes/index.py:90` serves `last_backup_time = "2024-06-07"`. `routes/dashboard.py:999` serves `confidence_average: 0.75`. Remove or replace with live values. | Low |
| **`step4_synthesis_service.py` importing from routes** | Line 506 imports from `routes/scenario_pipeline/step4/precedents.py`. Same inverted dependency pattern as the one fixed for `entity_graph_service.py`. | Low |

### Ongoing / Low Priority

| Item | Description |
|------|-------------|
| **Type annotations** | ~50% of functions lack return type annotations. No `mypy` enforcement. Add incrementally when touching files. |
| **Inline `from sqlalchemy import text`** | 4 occurrences in `interactive_scenario_service.py`. Could move to top-level imports. |
| **38 blueprints** | Route layer has 30 flat modules plus 4 package groups. Some consolidation may be warranted as legacy routes are retired. |
| **88 files over 500 lines** | Top 10 range from 1,198 to 1,951 lines. `guideline_analysis_service.py` (1,951) is the primary candidate for splitting. |
