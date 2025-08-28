# ProEthica 9-Concept Extraction Context

**Current Phase**: NSPE Entity Extraction & Pre-loaded Ontologies Complete 🎯
**Last Updated**: 2025-08-27
**Status**: ✅ **NSPE Integration Complete** | 🚀 **Pre-loaded Ontology System Operational** | 🗂️ Directory Cleanup

## 🎯 **LATEST ACHIEVEMENT: NSPE Entity Extraction Complete** ✅

**Major transformation accomplished - shift from on-the-fly to pre-loaded ontologies:**

### **NSPE Code of Ethics Processing Results**
- **94 Total Entities Extracted** across 8 concept types from authoritative NSPE source
- **Formal Tuple Validated**: Complete D=(R,P,O,S,Rs,A,E,Ca,Cs) implementation 
- **Ontology Architecture**: Three-tier system (proethica-core → proethica-intermediate → engineering-ethics)
- **Performance Enhancement**: Eliminated on-the-fly extraction overhead
- **Authoritative Source**: All concepts derived from official NSPE Code of Ethics

### **Ontology Infrastructure Improvements**
- **Naming Consolidated**: Successfully fixed proeth-core → proethica-core with 9 classes + 10 properties
- **Enhanced OntServe**: Added settings management separate from TTL editing
- **Route Handling**: Fixed BuildErrors in settings interface
- **Database Management**: Direct database scripts for ontology administration

### **NSPE Entity Distribution**
**Extracted entities now populate ontologies for immediate use:**
- **proethica-core**: Formal tuple specification (Role, Principle, Obligation, etc.)
- **proethica-intermediate**: 94 specific NSPE concepts + existing 99 classes
- **engineering-ethics**: Domain-specific engineering ethical concepts

**Concept Breakdown:**
- **Principles**: 13 (Public Safety Paramount, Professional Competence, etc.)
- **Obligations**: 23 (Hold paramount public safety, etc.) 
- **Actions**: 23 (Approve Documents, Report Violations, etc.)
- **Capabilities**: 16 (Engineering Competence, Professional Judgment, etc.)
- **Events**: 8 (Safety Risk Identified, Conflict Discovered, etc.)
- **States**: 4 (Judgment Overruled, Conflict of Interest, etc.)
- **Resources**: 4 (NSPE Code of Ethics, Registration Laws, etc.)
- **Constraints**: 3 (Registration Requirements, Legal Limits, etc.)

## 🗂️ **DIRECTORY ORGANIZATION GUIDELINES**

**Organizational Directive**: Minimize files in application root directories:
- **Test files** linked to pytest → `tests/` directory
- **Temporary/experimental files** → `scratch/` directory  
- **Scripts** → `scripts/` directory
- **Documents** → moved to `/home/chris/onto/docs/proethica/` (consolidated)
- **Root directory** → Keep only essential application files (run.py, requirements.txt, config files, etc.)

## Immediate Context

### What We've Accomplished ✅
- **NSPE ENTITY EXTRACTION COMPLETE**: 94 authoritative ethical concepts extracted from NSPE Code of Ethics
- **ONTOLOGY TRANSFORMATION**: Shifted from on-the-fly to pre-loaded ontology approach
- **FORMAL TUPLE VALIDATED**: Complete D=(R,P,O,S,Rs,A,E,Ca,Cs) implementation in proethica-core
- **ENHANCED ONTSERVE**: Settings management and proper route handling added
- **ALL 9 EXTRACTORS COMPLETE**: Full formal methodology implementation
- **Generalized LLM Splitting**: Intelligent compound concept decomposition without hardcoded patterns
- **LangChain Orchestration**: Multi-stage processing pipeline (Split → Validate → Filter)
- **Test Framework Ready**: Complete testing setup for enhanced splitting validation

### Current System Status
- ✅ **NSPE Pre-loaded System**: 94 authoritative concepts ready for immediate use
- ✅ **Formal Tuple Architecture**: proethica-core with D=(R,P,O,S,Rs,A,E,Ca,Cs) specification
- ✅ **All 9 Concept Types**: R, P, O, S, Rs, A, E, Ca, Cs - ALL WORKING
- ✅ **Production Deployment**: Live web interface with enhanced performance (no extraction overhead)
- ✅ **MCP Integration**: External ontology context functioning
- ✅ **3-Pass Orchestration**: Entities → Normative → Behavioral working
- ✅ **Enhanced OntServe**: Settings management and route handling fixed
- 🆕 **Enhanced Splitting**: GeneralizedConceptSplitter ready for testing

### 🧪 Testing Framework Ready (Next Steps When Returning)
**Test files organized in proper directories:**
- `tests/test_enhanced_roles.py` - Comprehensive comparison test (moved from root)
- `scratch/enhanced_roles_integration.py` - Integration helper (moved from root)
- `concept_splitter.py` - Generalized LLM splitting implementation (check app/services/extraction/)
- `langchain_orchestrator.py` - Multi-stage pipeline (check app/services/extraction/)
- `enhanced_obligations_example.py` - Full integration example (check scratch/)

**To run enhanced splitting tests:**
```bash
cd /home/chris/onto/proethica
python scratch/enhanced_roles_integration.py  # Check readiness
python tests/test_enhanced_roles.py         # Run comparison
```

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
- `tests/test_real_mcp_extraction.py` - Current state verification (moved from root)
- `tests/test_roles_extraction.py` - Working extractor test (moved from root)

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
python tests/test_real_mcp_extraction.py
```

### Verify MCP Connectivity  
```bash
cd proethica
python tests/test_external_mcp.py
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
2. Verify MCP connectivity with `python tests/test_external_mcp.py`
3. Examine existing `obligations.py` and `principles.py` files
4. Follow the MCP integration pattern from `roles.py`
5. Test each enhancement before moving to next extractor

**If interrupted and resuming:**
1. Read `/home/chris/onto/docs/proethica/system-status.md` for full context
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
