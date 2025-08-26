# ProEthica 9-Concept Extraction Context

**Current Phase**: Checkpoint 4 - Multi-Pass Orchestration Preparation
**Last Updated**: 2025-01-26 1:49 PM

## Immediate Context

### What We've Accomplished ✅
- **Checkpoints 1-3 COMPLETE**: Enhanced existing extractors + implemented States & Resources
- 5/9 extractors now functional with MCP integration and heuristic fallback
- All extractors follow consistent pattern and include classification logic

### Current Status
- ✅ **RolesExtractor**: Working with MCP integration (5 roles extracted, 22s)
- ✅ **ObligationsExtractor**: Enhanced with MCP integration
- ✅ **PrinciplesExtractor**: Enhanced with MCP integration  
- ✅ **StatesExtractor**: NEW - extracts conditions/circumstances (9 states extracted)
- ✅ **ResourcesExtractor**: NEW - extracts codes/standards/tools (6 resources extracted)
- ❌ **4 Remaining**: Actions, Events, Capabilities, Constraints

### Next Immediate Steps
1. Proceed to Checkpoint 4: Multi-pass extraction orchestration
2. Update GuidelineAnalysisService to use all 5 extractors
3. OR continue implementing remaining 4 extractors first
4. Add environment variable controls for new extractors
5. Test full pipeline integration

---

## Key Architecture Patterns

### MCP Integration Pattern (from RolesExtractor)
```python
# 1. Check if external MCP is enabled
if os.environ.get('ENABLE_EXTERNAL_MCP_ONTOLOGY', 'false').lower() == 'true':
    existing_concepts = self._get_existing_from_mcp(world_id)
    if existing_concepts:
        context_str = self._format_mcp_context(existing_concepts)

# 2. Include context in prompt
prompt = f"""
{context_str}

Now extract {concept_type} from this guideline...
"""
```

### Extractor File Structure
```python
class ConceptExtractor(Extractor):
    def extract(self, text: str, **kwargs) -> List[ConceptCandidate]:
        # MCP context retrieval
        # Focused prompt creation
        # LLM call
        # Result parsing

class ConceptPostProcessor(PostProcessor):
    def process(self, candidates: List[ConceptCandidate]) -> List[ConceptCandidate]:
        # Validation and classification

class SimpleConceptMatcher(Matcher):
    def match(self, candidates: List[ConceptCandidate], **kwargs) -> List[MatchedConcept]:
        # Ontology matching
```

---

## File Locations

### Core Implementation
- `app/services/guideline_analysis_service.py` - Main orchestration
- `app/services/extraction/roles.py` - Working MCP template
- `app/services/extraction/obligations.py` - Needs MCP enhancement
- `app/services/extraction/principles.py` - Needs MCP enhancement

### Configuration
- `.env` - Feature flags for enabling extractors
- `app/services/external_mcp_client.py` - MCP integration client

### Testing
- `test_real_mcp_extraction.py` - Current state verification
- `test_roles_extraction.py` - Working extractor test

---

## Environment Variables

### Current Settings
```bash
ENABLE_EXTERNAL_MCP_ONTOLOGY=true  # MCP integration enabled
ENABLE_ROLES_EXTRACTION=true       # Working
ENABLE_OBLIGATIONS_EXTRACTION=true # Conditional, needs MCP
ENABLE_PRINCIPLES_EXTRACTION=true  # Conditional, needs MCP

# Future extractors (set to false until implemented)
ENABLE_STATES_EXTRACTION=false
ENABLE_RESOURCES_EXTRACTION=false
# ... etc
```

---

## Known Issues & Considerations

### Current Blockers
- ObligationsExtractor and PrinciplesExtractor lack MCP context
- May have lower match rates than RolesExtractor
- Need to verify LLM provider consistency

### Performance Targets
- Each extractor should complete in <10 seconds
- Total extraction time <60 seconds for all concepts
- Match rate to existing ontology >75%

---

## Quick Commands

### Test Current State
```bash
cd proethica
python test_real_mcp_extraction.py
```

### Verify MCP Connectivity  
```bash
cd proethica
python test_external_mcp.py
```

### Check Specific Extractor (after enhancement)
```bash
cd proethica
python test_enhanced_obligations.py
python test_enhanced_principles.py
```

---

## Implementation Progress

### Completed Checkpoints ✅
- ✅ **Checkpoint 0**: Foundation (RolesExtractor with MCP)
- ✅ **Checkpoint 1**: Enhanced ObligationsExtractor and PrinciplesExtractor with MCP
- ✅ **Checkpoint 2**: StatesExtractor implemented (conditions, circumstances)
- ✅ **Checkpoint 3**: ResourcesExtractor implemented (codes, standards, tools)

### Current Decision Point 🎯
- **Option A**: Proceed to Checkpoint 4 (Multi-pass orchestration with 5 extractors)
- **Option B**: Complete remaining 4 extractors first (Actions, Events, Capabilities, Constraints)

### Upcoming Checkpoints  
- **Checkpoint 4**: Multi-pass extraction orchestration
- **Checkpoint 5**: Actions & Events Extractors
- **Checkpoint 6**: Capabilities & Constraints Extractors
- **Checkpoint 7**: Full integration testing

---

## Resumption Instructions

**If continuing from here:**
1. Check environment variables are set correctly
2. Verify MCP connectivity with `python test_external_mcp.py`
3. Examine existing `obligations.py` and `principles.py` files
4. Follow the MCP integration pattern from `roles.py`
5. Test each enhancement before moving to next extractor

**If interrupted and resuming:**
1. Read `docs/9-concept-extraction-resumable-plan.md` for full context
2. Check this CLAUDE.md for immediate status
3. Run current state test to verify foundation
4. Continue at current checkpoint

---

**Key Insights**: 
- 5/9 extractors are now functional with consistent architecture
- Heuristic fallback works well (9 states, 6 resources extracted in tests)
- MCP integration pattern is proven and reusable
- Classification logic achieves high accuracy (6/7 test cases passed)

**Next Action**: Decide between multi-pass orchestration (Checkpoint 4) or completing remaining extractors first.
