# ProEthica Codebase Efficiency Analysis

## Prompt for Claude Code (Local Machine)

> You are working on the ProEthica codebase (~215K LOC across 607 Python files).
> This is a Flask + SQLAlchemy + Celery application for AI-powered ethical
> reasoning and case analysis. It uses Claude/OpenAI via LangChain, RDF/OWL
> ontologies via OntServe MCP, and a PostgreSQL backend.
>
> Below is a prioritized analysis of efficiency improvements, unused code, and
> modularization opportunities. Work through these in order, confirming each
> phase with the user before proceeding.

---

## 1. Formalism Decision: Keep the Current Hybrid (Don't Force Pydantic Everywhere)

The codebase already uses a **well-layered** 4-tier data formalism:

| Layer | Tool | Where | Count |
|-------|------|-------|-------|
| Persistence | SQLAlchemy `db.Model` | `app/models/` | 66 models, 52 with `to_dict()` |
| LLM I/O validation | Pydantic `BaseModel` | `app/services/extraction/schemas.py` | 13+ models |
| Internal processing | `@dataclass` | ~79 files across services | Dozens of types |
| Web input | WTForms | `app/forms.py` | Login, registration |

**Recommendation: Do NOT unify everything into Pydantic.** Here's why:

- **SQLAlchemy models** serve double-duty as schema definition + query interface.
  Replacing them with Pydantic + raw SQL would lose Flask-SQLAlchemy's
  relationship loading, migrations, and session management for no real gain.
- **Pydantic is already correctly placed** at the LLM boundary where validation
  matters most (parsing unpredictable JSON from Claude). The `UnifiedDualExtractor`
  already does graceful per-item fallback on `ValidationError`. This is good.
- **Dataclasses** are fine for internal DTOs that don't need validation. They're
  lighter than Pydantic and appropriate for pipeline intermediates.

**What TO do instead:**

1. **Standardize `to_dict()` across all 66 models.** 52 of 66 models have it but
   implementations vary. Create a `SerializableMixin` in `app/models/__init__.py`:

   ```python
   class SerializableMixin:
       """Consistent JSON serialization for all models."""
       def to_dict(self, exclude=None, include_relationships=False):
           exclude = exclude or set()
           result = {}
           for col in self.__table__.columns:
               if col.name not in exclude:
                   val = getattr(self, col.name)
                   if isinstance(val, datetime):
                       val = val.isoformat()
                   result[col.name] = val
           return result
   ```

2. **Add Pydantic response schemas for API routes** (optional, later). If you
   ever add a REST API layer, Pydantic response models would help. For now the
   server-rendered Jinja2 templates don't need them.

3. **Keep dataclasses for pipeline intermediates** but consider converting a few
   to `@dataclass(slots=True, frozen=True)` where immutability makes sense
   (e.g., `EntitySummary`, `Stakeholder`).

---

## 2. Unused Code to Remove (~30 files, ~8,000+ lines)

### 2a. Dead Extraction Files (Superseded by UnifiedDualExtractor)

The `UnifiedDualExtractor` explicitly states it "replaces the 7 near-identical
dual_*_extractor.py files." These are confirmed unused (0 imports from active code):

| File | Lines | Action |
|------|-------|--------|
| `app/services/extraction/dual_actions_extractor.py` | ~300 | Delete |
| `app/services/extraction/dual_capabilities_extractor.py` | ~300 | Delete |
| `app/services/extraction/dual_constraints_extractor.py` | ~300 | Delete |
| `app/services/extraction/dual_events_extractor.py` | ~300 | Delete |
| `app/services/extraction/dual_obligations_extractor.py` | ~300 | Delete |
| `app/services/extraction/dual_principles_extractor.py` | ~300 | Delete |
| `app/services/extraction/dual_resources_extractor.py` | ~300 | Delete |
| `app/services/extraction/dual_role_extractor.py` | ~300 | Delete |
| `app/services/extraction/dual_states_extractor.py` | ~300 | Delete |
| `app/services/extraction/enhanced_obligations_example.py` | 405 | Delete |
| `app/services/extraction/enhanced_prompts_actions_events.py` | ? | Delete |
| `app/services/extraction/migrate_to_atomic_framework.py` | ? | Delete |
| `app/services/extraction/provenance_aware_extraction.py` | ? | Delete |
| `app/services/extraction/roles_enhanced.py` | ? | Delete |

**Before deleting:** Verify `app/utils/dual_extractor_template_seeder.py` doesn't
dynamically import these. It appears to reference class names as strings for
seeding prompts, which should work fine after deletion since the
`UnifiedDualExtractor` uses the same DB prompt templates.

### 2b. Unused Services (0 imports from active code)

| File | Lines | Notes |
|------|-------|-------|
| `app/services/async_concept_extraction_service.py` | ? | Never imported |
| `app/services/code_provision_pattern_matcher.py` | ? | Never imported |
| `app/services/code_provision_validator.py` | ? | Never imported |
| `app/services/enhanced_mcp_client.py` | 972 | Superseded by `ontserve_mcp_client.py` |
| `app/services/guideline_analysis_service_clean.py` | ~400 | Variant of main service, unused |
| `app/services/guideline_analysis_service_dynamic.py` | ~500 | Variant of main service, unused |
| `app/services/guideline_concept_type_mapper.py` | ? | Never imported |
| `app/services/guideline_deletion_service.py` | ? | Never imported |
| `app/services/rdf_extraction_converter.py` | 2,151 | Never imported (!) - verify |
| `app/services/scenario_population_service.py` | ? | Never imported |
| `app/services/experiment/patch_prediction_service.py` | ? | Experimental dead code |
| `app/services/experiment/prediction_service_clean.py` | ? | Experimental dead code |
| `app/services/experiment/prediction_service_fixed.py` | ? | Experimental dead code |
| `app/services/case_processing/pipeline_steps/nspe_extraction_step_improved.py` | ? | "Improved" variant never used |
| `app/services/temporal_dynamics/extractors/temporal_extractor.py` | ? | Never imported |

**Special note on `rdf_extraction_converter.py`:** At 2,151 lines this is the
5th largest file and has zero imports. Verify it's truly dead before deleting.

### 2c. Unused Routes

| File | Notes |
|------|-------|
| `app/routes/experiment_double_blind.py` | Never registered in blueprint |
| `app/routes/update_pipeline_route.py` | Never registered in blueprint |

### 2d. Orphaned Test

| File | Issue |
|------|-------|
| `tests/unit/test_extraction_actions_events.py` | Imports `DualActionsEventsExtractor` which doesn't exist |

---

## 3. Large Files That Need Modularization

### Priority 1: `app/routes/scenario_pipeline/step4.py` (5,177 lines, 80 functions, 44 routes)

This is the single largest file and mixes multiple concerns. Split into:

```
app/routes/scenario_pipeline/
    step4/
        __init__.py          # Blueprint registration, imports sub-blueprints
        synthesis.py         # Core synthesis routes (generate, stream, review)
        questions.py         # Question extraction and Q-C flow routes
        conclusions.py       # Conclusion analysis routes
        provisions.py        # Provision linking and NSPE code routes
        precedents.py        # Precedent discovery routes
        entity_graph.py      # Entity visualization routes
        helpers.py           # _count_conclusion_types, shared utilities
```

**Approach:** Flask blueprints can be nested. Register a parent `step4_bp` and
import routes from sub-modules. Each sub-module adds routes to the same blueprint.

### Priority 2: `app/routes/worlds.py` (3,691 lines, 57 functions, 44 routes)

Split into:

```
app/routes/worlds/
    __init__.py              # worlds_bp registration
    core.py                  # CRUD for worlds
    guidelines.py            # Guideline analysis and annotation
    extraction.py            # Concept extraction routes
    triples.py               # Triple generation and management
    embedding.py             # Embedding-related routes
```

**Note:** `worlds_extract_only.py`, `worlds_direct_concepts.py`, and
`worlds_generate_triples.py` already exist as partial splits. Finish the job.

### Priority 3: `app/routes/cases.py` (2,880 lines, 38 functions, 36 routes)

Split into:

```
app/routes/cases/
    __init__.py              # cases_bp registration
    core.py                  # CRUD for cases
    deconstruction.py        # Case deconstruction routes
    synthesis.py             # Case synthesis routes
    import_export.py         # URL import, case data export
```

### Priority 4: `app/services/guideline_analysis_service.py` (1,951 lines, 45 functions)

This is a god-class. Split by analysis phase:

```
app/services/guideline_analysis/
    __init__.py
    structure_analyzer.py    # Document structure analysis
    concept_extractor.py     # Concept extraction from guidelines
    triple_generator.py      # Triple generation
    annotation_linker.py     # Linking annotations to ontology
    batch_processor.py       # Batch/bulk analysis operations
```

### Priority 5: `app/services/rdf_extraction_converter.py` (2,151 lines)

If confirmed unused, delete. If used via dynamic import or CLI, split into:

```
app/services/rdf_conversion/
    __init__.py
    concept_converter.py     # Concept-to-RDF conversion
    triple_builder.py        # Triple construction
    serializer.py            # RDF serialization formats
```

---

## 4. Duplicate Functionality to Consolidate

### 4a. Annotation Services (14 files!)

There are **14 separate annotation-related services**. Audit and consolidate:

| Keep | Merge Into It |
|------|---------------|
| `document_annotation_service.py` | `simple_annotation_service.py`, `simplified_llm_annotation_service.py` |
| `intelligent_annotation_service.py` | `llm_enhanced_annotation_service.py` |
| `ontserve_annotation_service.py` | Keep separate (external integration) |
| `synthesis_annotation_service.py` | Keep separate (different domain) |
| `guideline_annotation_orchestrator.py` | Keep (orchestrates others) |
| `definition_based_annotation_service.py` | Consider merging into base |
| `llm_annotation_approval_service.py` | Keep (approval workflow) |

Target: reduce from 14 to 7-8 files.

### 4b. MCP Client Variants (5 files)

| File | Status |
|------|--------|
| `mcp_client.py` | Original - check if still used |
| `enhanced_mcp_client.py` (972 lines) | **Unused** - delete |
| `ontserve_mcp_client.py` | Active - primary client |
| `external_mcp_client.py` | Separate concern (external access) |
| `mcp_entity_enrichment_service.py` | Uses MCP for enrichment |

Target: delete `enhanced_mcp_client.py`, verify if `mcp_client.py` can be
merged into `ontserve_mcp_client.py`.

### 4c. Question Services (5 files)

| File | Notes |
|------|-------|
| `question_analyzer.py` | Analysis logic |
| `question_extraction_service.py` | Extraction logic |
| `question_conclusion_linker.py` | Linking logic |
| `question_conclusion_linking_service.py` | **Likely duplicate of above** |
| `scenario_pipeline/question_based_decisions.py` | Pipeline-specific |

Verify if `question_conclusion_linker.py` and `question_conclusion_linking_service.py`
are doing the same thing. Consolidate if so.

### 4d. Duplicate Helper in step4.py

`_count_conclusion_types()` (line 1076) and `_count_conclusion_types_from_list()`
(line 1085) do nearly the same thing. Keep only the more flexible version.

---

## 5. Execution Plan (Work in Phases)

### Phase 1: Dead Code Removal (~1-2 hours)

```
1. Delete the 9 dual_*_extractor.py files + 5 other dead extraction files
2. Delete the 3 dead experiment/ files
3. Delete enhanced_mcp_client.py, guideline_analysis_service_clean.py,
   guideline_analysis_service_dynamic.py
4. Delete or archive other confirmed-unused services
5. Fix/remove orphaned test file
6. Run tests to verify nothing breaks
7. Commit: "Remove ~30 unused files superseded by unified extractor and consolidation"
```

### Phase 2: Modularize step4.py (~2-3 hours)

```
1. Create app/routes/scenario_pipeline/step4/ directory
2. Move routes into thematic sub-modules
3. Create __init__.py that registers all routes on the same blueprint
4. Verify all imports and URL references still work
5. Run full test suite
6. Commit: "Split step4.py (5177 lines) into 7 focused modules"
```

### Phase 3: Modularize worlds.py and cases.py (~2-3 hours)

```
1. Same pattern as step4 - create subdirectory, split by concern
2. Integrate with existing partial splits (worlds_extract_only.py, etc.)
3. Test and commit each separately
```

### Phase 4: Service Consolidation (~2-3 hours)

```
1. Audit annotation services - merge where functionality overlaps
2. Consolidate MCP clients
3. Consolidate question services
4. Verify no regressions
```

### Phase 5: Model Standardization (~1 hour)

```
1. Create SerializableMixin in app/models/__init__.py
2. Apply to all 66 models (replace custom to_dict with mixin)
3. Add slots=True to appropriate dataclasses
4. Test serialization paths
```

---

## 6. Quick Wins (Can Do Immediately)

1. **Delete the 9 dead `dual_*_extractor.py` files** - confirmed replaced by
   `UnifiedDualExtractor`, zero active imports
2. **Delete `enhanced_mcp_client.py`** - 972 lines, zero imports
3. **Delete guideline service variants** - `_clean.py` and `_dynamic.py` unused
4. **Consolidate `_count_conclusion_types` functions** in step4.py
5. **Remove commented-out routes** in `interactive_builder.py` and `step4.py`

These 5 actions alone remove ~5,000+ lines with zero risk of regression.

---

## Metrics Summary

| Metric | Current | After Phase 1 | After All |
|--------|---------|---------------|-----------|
| Python files | 607 | ~577 | ~570 |
| Total LOC | 215,526 | ~207,000 | ~200,000 |
| Largest file | 5,177 lines | 5,177 lines | ~800 lines |
| Unused service files | ~30 | 0 | 0 |
| Annotation services | 14 | 14 | 8 |
