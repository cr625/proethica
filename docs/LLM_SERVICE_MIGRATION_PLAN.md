# LLM Service Migration Plan

**Created:** November 16, 2025
**Status:** Phase 0 - Planning
**Goal:** Migrate from deprecated llm_service.py to centralized LLM manager

---

## Current State Analysis

### Deprecated Services (Point to non-existent /shared/llm_orchestration/)
- `app/services/llm_service.py` (imported by 24 files)
- `app/services/claude_service.py` (imported by some of those 24)

### New Infrastructure (Created this session)
- ✅ `app/services/llm/manager.py` - Centralized LLM manager
- ✅ `app/services/llm/config.py` - Configuration with timeout handling
- ✅ `app/services/llm/response.py` - Unified response format

### Files Importing llm_service.py (24 total)

**Core Services (8 files):**
1. `app/services/claude_service.py` - Also deprecated
2. `app/services/direct_llm_service.py`
3. `app/services/conversation_to_case_service.py`
4. `app/services/firac_analysis_service.py`
5. `app/services/case_role_matching_service.py`
6. `app/services/role_description_service.py`
7. `app/services/document_annotation_pipeline.py`
8. `app/services/unified_agent_service.py`

**Annotation Services (5 files):**
9. `app/services/definition_based_annotation_service.py`
10. `app/services/enhanced_guideline_association_service.py`
11. `app/services/simplified_llm_annotation_service.py`
12. `app/services/llm_annotation_approval_service.py`
13. `app/services/llm_enhanced_annotation_service.py`

**Experimental/Agents (6 files):**
14. `app/services/experiment/patch_prediction_service.py`
15. `app/services/experiment/prediction_service.py`
16. `app/services/experiment/prediction_service_fixed.py`
17. `app/services/experiment/llm_service_fix.py`
18. `app/services/experiment/prediction_service_clean.py`
19. `app/services/agents/case_creation_agent.py`

**Other (5 files):**
20. `app/services/ethics_committee_agent.py`
21. `app/services/simulation_controller.py`
22. `app/routes/scenario_pipeline/view_timeline.py`
23. `app/routes/simulation.py`
24. `app/routes/agent.py`

---

## Migration Strategy (OntExtract Pattern)

Following OntExtract's infrastructure-first approach:

### Phase 0: Create Compatibility Layer ✅
**Status:** COMPLETE (LLM manager exists)

Create `app/services/llm/` infrastructure:
- ✅ manager.py - Unified LLM interface
- ✅ config.py - Timeout and retry configuration
- ✅ response.py - Standardized response format

### Phase 1: Convert llm_service.py to Compatibility Wrapper
**Timeline:** Next task
**Effort:** Low
**Risk:** Low

Convert `llm_service.py` from deprecated service to compatibility wrapper:
```python
# app/services/llm_service.py
from app.services.llm.manager import LLMManager

# Compatibility types
class Message:
    """Wrapper for backward compatibility"""
    pass

class Conversation:
    """Wrapper for backward compatibility"""
    pass

class LLMService:
    """Compatibility wrapper - delegates to LLMManager"""
    def __init__(self):
        self.manager = LLMManager()
        # Delegate all methods to manager
```

**Benefits:**
- Zero breaking changes
- 24 files continue working
- Foundation for gradual migration
- Remove deprecation warnings

### Phase 2: Migrate Core Services (Incremental)
**Timeline:** After Phase 1
**Effort:** Medium
**Risk:** Medium

Migrate high-value files one at a time:
1. Start with simplest: `case_role_matching_service.py`
2. Test thoroughly
3. Move to next file
4. Repeat

**Pattern per file:**
```python
# Before
from app.services.llm_service import LLMService
llm = LLMService()

# After
from app.services.llm.manager import LLMManager
llm = LLMManager()
```

### Phase 3: Clean Up Experimental Files
**Timeline:** After Phase 2
**Effort:** Low
**Risk:** Low

Either migrate or remove experimental services:
- 5 prediction service variants (likely duplicates)
- 1 llm_service_fix.py (experiment)

### Phase 4: Remove Compatibility Layer
**Timeline:** When no direct imports remain
**Effort:** Low
**Risk:** Low

Once all files migrated, remove the wrapper.

---

## Success Criteria

### Phase 1 Complete When:
- [ ] llm_service.py is a thin wrapper over LLMManager
- [ ] All 24 files still work (no breaking changes)
- [ ] Deprecation warnings removed
- [ ] Tests pass

### Phase 2 Complete When:
- [ ] 8 core services migrated to LLMManager directly
- [ ] 5 annotation services migrated
- [ ] Integration tests pass

### Phase 3 Complete When:
- [ ] Experimental duplicates removed or consolidated
- [ ] Only actively-used services remain

### Phase 4 Complete When:
- [ ] No files import llm_service.py directly
- [ ] llm_service.py removed
- [ ] Documentation updated

---

## Benefits of This Approach

1. **Zero Breaking Changes** - Compatibility wrapper keeps everything working
2. **Incremental Migration** - Migrate one file at a time, test, move on
3. **Low Risk** - Can rollback any single migration without affecting others
4. **Follows OntExtract** - Infrastructure first, incremental refactoring
5. **Enables Multi-Domain** - Centralized LLM makes domain switching easier

---

## Next Steps

1. ✅ Create this migration plan
2. ⏳ Implement Phase 1: Convert llm_service.py to compatibility wrapper
3. ⏳ Test that all 24 files still work
4. ⏳ Begin Phase 2: Migrate one core service as proof of concept

---

## References

- [LLM_MANAGER_DESIGN.md](LLM_MANAGER_DESIGN.md) - Centralized LLM manager design
- [PROGRESS.md](../PROGRESS.md) - Session progress tracking
- [OntExtract REFACTORING_PROGRESS.md](https://github.com/MatLab-Research/OntExtract/blob/development/REFACTORING_PROGRESS.md) - Pattern we're following
