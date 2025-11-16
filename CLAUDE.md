# ProEthica Multi-Section Extraction System

**Last Updated**: November 16, 2025
**Current Phase**: Repository Cleanup & LLM Centralization Refactoring 🔧
**Active Branch**: `claude/continue-work-01ABZAYgwMqQW9dPfdkrrAPo`
**Test Cases**: Case 8 (All systems functional, dependency management complete)

---

## 🚨 ACTIVE REFACTORING SESSION (November 16, 2025)

**Current Work:** Repository cleanup and LLM centralization for multi-domain expansion

**⚠️ CRITICAL - Use Correct Branch:**
```bash
git checkout claude/continue-work-01ABZAYgwMqQW9dPfdkrrAPo
```

**Session Progress:** See **[PROGRESS.md](PROGRESS.md)** for detailed session status

**Completed This Session:**
- ✅ Dependency management (requirements.txt, pyproject.toml)
- ✅ LangChain 1.0 migration (langchain-classic installed, all imports updated)
- ✅ Empty section handling fix in scenario pipeline
- ⏳ **NEXT:** Repository cleanup (remove ~39 MB of archives/backups)

**Goal:** Prepare codebase for easier multi-domain support (engineering → law, medical, etc.)

---

## System Status (Core Features)

**Current Phase**: Step 4 Parts D-F Complete ✅, Step 5 Stages 1-6 Complete ✅
**Active Development**: Refactoring for multi-domain expansion
**Test Cases**: Case 8 (Parts D-E-F verified, Step 5 Stages 1-6 functional)

---

## System Status

### LATEST: Step 4 Parts D-F Complete ✅ + Step 5 Refactoring Complete ✅ (November 1, 2025)

**Status**: Step 4 analytical engine fully complete, Step 5 now operates as presentation layer referencing Step 4 analysis

**Key Achievement**: Complete architectural separation of analysis (Step 4) from presentation (Step 5), eliminating redundant LLM calls

**Completed November 1, 2025**:
- ✅ **Part F: TransformationClassifier** - Classifies case transformation type and symbolic significance
  - Service implementation complete with comprehensive case pattern analysis
  - Database persistence to `case_transformation`
  - Classifies: transfer/stalemate/oscillation/phase_lag (Marchais-Roubelat & Roubelat 2015, p. 550)
  - Case 8 results: phase_lag transformation (confidence 0.92), pattern_id: client_frame_impermeability
- ✅ **Step 5 Refactoring** - Stages 4-6 now reference Step 4 database analysis (no re-analysis)
  - Stage 4: Decision Identification → References Part D (institutional analysis)
  - Stage 5: Causal Chain Integration → References Part E (action-rule mapping)
  - Stage 6: Normative Framework → References Part F (transformation classification)
  - New method: `identify_decisions_from_step4_analysis()` in `decision_identifier.py`
  - Database queries replace redundant LLM calls
  - **Performance**: ~70% reduction in LLM usage, significantly faster execution

**Completed October 31, 2025**:
- ✅ **Part D: InstitutionalRuleAnalyzer** - Analyzes principle tensions, obligation conflicts, constraining factors
- ✅ **Part E: ActionRuleMapper** - Maps three-rule framework to ProEthica concepts
- ✅ **Technical Infrastructure**: Timeout configuration, entity attribute helpers, SSE streaming integration

**What This Means**:
- Step 4 performs comprehensive case analysis to understand board reasoning
- Step 5 presents Step 4 analysis in scenario format for clearer visualization
- Scenario format reveals ethical problem structure more clearly than narrative text
- Enables analytical pattern extraction and cross-case comparison

**Data Flow Architecture**:
```
Passes 1-3: Extract 9 concepts from Facts + Discussion
            ↓
Step 4: Comprehensive Case Analysis (ANALYTICAL ENGINE)
  - Part A-C: Provisions, Q&A, Entity Graph (COMPLETE)
  - Part D: Institutional Rule Analysis - P tensions, O conflicts, Cs factors
  - Part E: Action-Rule Mapping - A/Ca/Rs, P/O/Cs, S/R/Rs/E rules
  - Part F: Transformation Classification - Transfer/Stalemate/Oscillation/Phase_Lag
            ↓
Step 5: Interactive Scenario Generation (PRESENTATION LAYER)
  - Stage 1-3: Data, Timeline, Participants (COMPLETE)
  - Stage 4: Decision Points → References Part D
  - Stage 5: Causal Chains → References Part E
  - Stage 6: Normative Framework → References Part F
  - Stage 7-9: Assembly, Interactive Model, Validation
```


## Step 4: Enhanced Case Analysis & Synthesis

**New Architecture**: Step 4 now performs comprehensive case analysis preparing for BOTH scenario generation AND standalone case analysis.

### Current Status

**Part A: Code Provisions** ✅ COMPLETE
- Extract provisions from References
- Link to all entity types
- Provision linking to 9-concept entities

**Part A-bis: Precedent Citation Extraction** ✅ COMPLETE (October 31, 2025)
- Hybrid extraction: HTML markup (primary) + LLM (fallback)
- Extract from `<a>` tags in Discussion/Conclusions sections
- Capture full NSPE URLs, case numbers, titles, years, context
- **Services**: `HTMLPrecedentExtractor`, `PrecedentCitationExtractor.extract_hybrid()`
- **Storage**: `TemporaryRDFStorage` with `extraction_type='precedent_case_reference'`
- **Display**: Clickable links on Step 4 review page with citation highlighting
- **Performance**: 11 cases extracted in ~0.1s (vs 30+s for LLM-only)

**Part B: Questions & Conclusions** ✅ COMPLETE
- Extract ethical questions
- Extract board conclusions
- Entity tagging and linking

**Part C: Enhanced Entity Graph** ✅ COMPLETE (October 31, 2025)
- Moved to AFTER Part D (uses all synthesis data)
- Includes: provisions, precedents, questions, conclusions, principles, obligations, constraints
- Edges: provision→entity, provision→precedent, question→conclusion, principle↔principle (tensions), obligation↔obligation (conflicts)
- **Service**: `EnhancedEntityGraphBuilder`
- **UI**: Enhanced controls (zoom, filters, tooltips) - JavaScript pending implementation
- **Display**: 900px canvas with Simple/Enhanced view toggle

**Part D: Institutional Rule Analysis** ✅ COMPLETE (October 31, 2025)
- Analyze principle tensions (P1 vs P2) - 2 tensions in Case 8
- Map obligation conflicts (O1 vs O3) - 3 conflicts in Case 8
- Identify constraint influences (Cs) - 5 factors in Case 8
- **Service**: `app/services/case_analysis/institutional_rule_analyzer.py`
- **Database**: `case_institutional_analysis`
- **Key Implementation Notes**:
  - Uses `_get_entity_attr()` for dual TemporaryRDFStorage/OntServe compatibility
  - Omits URIs from LLM prompts (URIs cause Anthropic API disconnections)
  - Includes obligation statements and NSPE Code section references
  - Integrated into Step 4 SSE streaming synthesis

**Part E: Action-Rule Mapping** ✅ COMPLETE (October 31, 2025)
- Map Action Rule (A, Ca, Rs): What was done/not done - 3 taken, 2 not taken
- Map Institutional Rule (P, O, Cs): Why justified/opposed - 7 obligations invoked
- Map Operations Rule (S, R, Rs, E): How context shaped actions
- Map Steering Rule: Transformation points - 5 identified
- **Service**: `app/services/case_analysis/action_rule_mapper.py`
- **Database**: `case_action_mapping`
- **Three-Rule Framework** (Marchais-Roubelat & Roubelat 2015):
  - Action Rule: WHAT happened (actions taken/not taken, alternatives, constraints)
  - Institutional Rule: WHY it happened (justifications, oppositions, obligations)
  - Operations Rule: HOW context shaped it (situational, organizational, events)
  - Steering Rule: Case transformation (decision points, rule shifts)

**Part F: Transformation Classification** ✅ COMPLETE (November 1, 2025)
- Classify transformation type: transfer/stalemate/oscillation/phase_lag (Marchais-Roubelat & Roubelat 2015)
- Extract symbolic significance and pattern templates for cross-case comparison
- **Service**: `app/services/case_analysis/transformation_classifier.py`
- **Database**: `case_transformation`
- Case 8 results: phase_lag (0.92 confidence), client_frame_impermeability pattern

### Implementation Progress

**Week 2 Complete**:
- ✅ Stage 3 Participant Mapping with LLM enhancement
- ✅ Database: `scenario_participants` + `scenario_relationship_map`
- ✅ Migration: [013_create_scenario_participants.sql](db_migration/013_create_scenario_participants.sql)

**Week 3 Complete** (October 31, 2025):
- ✅ Architecture reorganization documented
- ✅ Database schema: [014_create_step4_enhanced_analysis.sql](db_migration/014_create_step4_enhanced_analysis.sql)
- ✅ **Part D: InstitutionalRuleAnalyzer** - Complete with testing on Case 8
- ✅ **Part E: ActionRuleMapper** - Complete with testing on Case 8
- ✅ **Technical fixes**:
  - httpx.Timeout configuration (180s read timeout) in llm_utils.py
  - Entity attribute helper method for TemporaryRDFStorage compatibility
  - URI removal from prompts to prevent API disconnections

**Week 4 Complete** (November 1, 2025):
- ✅ **Part F: TransformationClassifier** - Complete with testing on Case 8
- ✅ **Step 5 Refactoring** - Stages 4-6 now reference Step 4 database analysis
  - Created `identify_decisions_from_step4_analysis()` method in decision_identifier.py
  - Modified generate_scenario.py Stages 4-6 to query database instead of re-analyzing
  - Eliminated redundant LLM calls (70% reduction in LLM usage)
- ✅ **Participant Mapping URI Fix** - Replaced full URIs with short IDs (p0, p1, p2) in prompts
  - **Critical lesson**: URIs in LLM prompts cause massive bloat and API timeouts
  - Example: `http://proethica.org/ontology/case/8#Client_X` → `p0` (75 chars → 2 chars)
  - 12 participants × 75 chars/URI = 900 chars saved just in participant IDs
  - Fix: Use short IDs in prompts, map back to full objects after LLM response
- ✅ **Database Transaction Fix** - Added `db.session.flush()` after DELETE operations
  - Ensures DELETEs complete before INSERTs to prevent unique constraint violations

### Technical Lessons Learned: Parts D-E-F + Step 5 Refactoring

**Key Debugging Insights** (October 31 - November 1, 2025):

1. **Entity Attribute Naming**:
   - **Issue**: TemporaryRDFStorage uses `entity_label`, `entity_uri`, `entity_definition`
   - **NOT**: Standard SQLAlchemy/OntServe naming (`label`, `uri`, `definition`)
   - **Solution**: Created `_get_entity_attr()` helper that checks both naming conventions
   - **Pattern**: `temp_name = f'entity_{attr_name}'` → check `entity_*` first, then fallback to standard

2. **Anthropic API Disconnection Root Cause**:
   - **Initial hypothesis**: Entity labels too long → **INCORRECT**
   - **Actual cause**: URIs in prompts (~75 chars × 37 entities = 2,775 chars overhead)
   - **Evidence**: Part E works with full labels but NO URIs; Part D failed with URIs
   - **Fix**: Removed URI lines from Part D formatting methods
   - **Result**: Prompt size reduced by ~2.6KB, API disconnections eliminated

3. **Timeout Configuration**:
   - **Issue**: Default read timeout (~60 seconds) too short for LLM processing
   - **Initial fix attempt**: `timeout=180.0` (float) → Didn't work (only sets default, not read timeout)
   - **Correct fix**: `timeout=Timeout(connect=10.0, read=180.0, write=180.0, pool=180.0)`
   - **Key insight**: httpx requires explicit Timeout object with separate connect/read/write/pool values

4. **Design Pattern for Future Services**:
   ```python
   def _get_entity_attr(self, entity: Any, attr_name: str, default: Any = None) -> Any:
       """Check both TemporaryRDFStorage (entity_*) and OntServe (standard) naming."""
       temp_val = getattr(entity, f'entity_{attr_name}', None)
       if temp_val is not None:
           return temp_val
       std_val = getattr(entity, attr_name, None)
       if std_val is not None:
           return std_val
       return default
   ```

5. **Prompt Optimization Strategy**:
   - Include: Entity labels (essential for LLM understanding)
   - Include: Obligation statements and code sections (provide context)
   - **Exclude**: URIs (repetitive, verbose, not needed for analysis)
   - **Result**: Smaller prompts that focus on semantic content rather than structural metadata

6. **URI Bloat in Participant Prompts** (Critical Step 5 Fix - November 1, 2025):
   - **Issue**: Participant enhancement LLM call timing out after 3 minutes of retries
   - **Initial hypothesis**: Prompt too long overall → **INCORRECT**
   - **Actual cause**: Full URIs as participant IDs in JSON payload
   - **Evidence**:
     - Original: `"participant_id": "http://proethica.org/ontology/case/8#Client_X"` (75 chars)
     - 12 participants × 75 chars = 900 chars just for IDs
     - Includes background, motivations, ethical_tensions, character_arc for each → further multiplied
   - **Fix**: Use short IDs in prompts, map back to objects after LLM response
     - Prompt: `"p0": {"name": "Client X", "background": "...", ...}`
     - Response parsing: Map `p0` → actual participant object using index
     - Result: 900 chars → 36 chars for IDs (96% reduction in ID overhead)
   - **Key insight**: URIs serve as database identifiers, NOT semantic content for LLMs
   - **Pattern for all future prompts**: Never include URIs unless specifically needed for entity disambiguation
   - **Files affected**: `participant_mapper.py` (_create_enhancement_prompt method)

7. **LLM Model Timeout with Complex Reasoning** (RESOLVED - November 2, 2025):
   - **Initial symptoms**: Step 5 LLM call timing out with `APIConnectionError` after 3 minutes
   - **Investigation expanded**: Same issue found in Step 4 Action Rule Mapper (Case 10)
   - **Pattern discovered**: Sonnet 4.5 has reproducible timeout with ANY complex reasoning task
   - **Root causes identified**: **Two separate issues**
     1. **JSON response parsing bug** (reproducible):
        - LLM returns markdown-wrapped JSON: `` ```json {...} ``` ``
        - Step 5 code tried to parse directly → failed on markdown markers
        - Error: `Expecting value: line 1 column 1 (char 0)`
        - **Fix**: Enhanced JSON parsing with markdown detection (Step 5 only; Step 4 already had this)
     2. **Sonnet 4.5 timeout with complex reasoning** (reproducible, NOT prompt-length related):
        - Direct API test: FAILED after 181.7 seconds with `APIConnectionError`
        - Same prompt with Sonnet 4: SUCCESS in 45 seconds
        - Affects: Step 4 Parts D-F AND Step 5 Stage 3 (all complex multi-entity reasoning)
        - Prompt size irrelevant: 7,432 chars = only ~2,500 tokens (1.25% of 200K context)
        - **Not intermittent**: 100% failure rate with Sonnet 4.5, 100% success with Sonnet 4
        - **Hypothesis**: Undocumented bug or processing limitation in Sonnet 4.5 for complex reasoning
        - **Fix**: Use Sonnet 4 for ALL ProEthica LLM calls
   - **Key debugging breakthrough**: User's suggestion to test saved payload directly
     - Standalone API test without SDK retries revealed consistent failure
     - Proved it was model-specific, not code/network/intermittent issue
   - **Final model decision**: **Universal Sonnet 4 across ProEthica**
     - All Step 4 services: institutional_rule_analyzer, action_rule_mapper, transformation_classifier
     - All Step 5 services: participant_mapper
     - Benefit: 75% faster (45s vs 180s), 100% reliable, actually cheaper ($3/MTok vs $5/MTok)
     - Trade-off: None - no quality degradation observed
   - **Debugging infrastructure built** (valuable for future issues):
     - Binary encoding analysis, raw request payload logging
     - httpx debug logging, standalone test suite
     - Comprehensive documentation: [chapter3_notes.md](docs/chapter3_notes.md), [STEP5_PARTICIPANT_ENHANCEMENT_FIX.md](docs/STEP5_PARTICIPANT_ENHANCEMENT_FIX.md)
   - **Status**: ✅ FULLY RESOLVED - All ProEthica LLM calls now use Sonnet 4 with robust JSON parsing

---

## Step 5: Analytical Scenario Generation (Visualization Layer)

**Purpose**: Transform Step 4 analysis into scenario format that reveals board reasoning structure

**Key Architectural Decision** (October 31, 2025):
- **Step 4 = Analytical Engine** (comprehensive case analysis with Parts D-F)
- **Step 5 = Visualization Layer** (scenario format for board reasoning)
- **Step 6 = Precedent Discovery** (planned - uses Step 5 scenarios for precise matching)

**Stage Progress** (November 3, 2025):
- ✅ **Stages 1-6 COMPLETE** (Data → Timeline → Participants → Decisions → Causal → Normative)
  - Stage 1: Data Collection (172 entities on Case 8)
  - Stage 2: Timeline Construction (8 entries, 3 phases)
  - Stage 3: Participant Mapping (12 participants, LLM-enhanced with Sonnet 4)
  - Stage 4: Decision Identification (references Step 4 Part D institutional analysis)
  - Stage 5: Causal Integration (references Step 4 Part E action mapping)
  - Stage 6: Normative Framework (references Step 4 Part F transformation)
- ⏳ **Stages 7-9 NEXT** (Assembly → Interactive Model → Validation)

**Implementation Details:**
- All LLM calls use **Sonnet 4** (`claude-sonnet-4-20250514`) - reliable for complex reasoning tasks
- Sonnet 4.5 had reproducible timeouts with multi-entity reasoning (see [chapter3_notes.md](docs/chapter3_notes.md))
- UI: Alert-based generation log (consistent with Step 4), collapsible architecture info
- Database: `scenario_participants`, `scenario_timeline`, `scenario_relationship_map` tables

**Next Steps:** See **[SCENARIO_NEXT_STEPS.md](docs/SCENARIO_NEXT_STEPS.md)** for Stages 7-9 implementation roadmap

**Benefits of This Architecture**:
- Scenario format reveals reasoning structure hidden in narrative text
- Step 4 provides analytical depth, Step 5 makes it visually accessible
- Enables cross-case pattern analysis and precedent discovery
- No redundant LLM analysis - Step 5 visualizes Step 4's work

---

## Architecture Documentation

**Project Goals** (READ THIS FIRST):
- **[PROJECT_GOALS.md](docs/PROJECT_GOALS.md)** - Clarifies primary purpose: case analysis (not pedagogy)

**Step 4 Enhanced**:
- Architecture: [STEP4_ENHANCED_SYNTHESIS.md](docs/STEP4_ENHANCED_SYNTHESIS.md) - NEW
- Original plan: [STEP4_WHOLE_CASE_SYNTHESIS_PLAN.md](docs/STEP4_WHOLE_CASE_SYNTHESIS_PLAN.md)

**Action-Based Framework**:
- Mapping: [ACTION_BASED_SCENARIO_MAPPING.md](docs/ACTION_BASED_SCENARIO_MAPPING.md)
- Integration: [ACTION_BASED_INTEGRATION_SUMMARY.md](docs/ACTION_BASED_INTEGRATION_SUMMARY.md)

**Step 5 Scenario Generation**:
- **Action Plan**: [SCENARIO_NEXT_STEPS.md](docs/SCENARIO_NEXT_STEPS.md) - **START HERE** - Stages 7-9 roadmap
- Architecture: [SCENARIO_SYNTHESIS_ARCHITECTURE_REVISED.md](docs/SCENARIO_SYNTHESIS_ARCHITECTURE_REVISED.md)

---

## Next Steps

**Current Focus**: Implement Step 5 Stages 7-9 (Scenario Assembly, Interactive Model, Validation)

**Completed** (Week 3-4):
1. ✅ Part D: InstitutionalRuleAnalyzer - Principle tensions, obligation conflicts, constraints
2. ✅ Part E: ActionRuleMapper - Three-rule framework mapping
3. ✅ Part F: TransformationClassifier - Case transformation type and symbolic significance
4. ✅ Step 5 Refactoring: Stages 4-6 now reference Step 4 database analysis
5. ✅ URI Fix: Replaced full URIs with short IDs in participant mapping prompts

**Next** (Step 5 Stages 7-9):
1. ⏳ Stage 7: Scenario Assembly
   - Combine timeline, participants, decisions, causal chains, normative framework
   - Generate complete scenario structure using Step 4 analytical foundation
   - Create decision tree with branching alternatives
   - Link scenario components to Step 4 analysis
2. ⏳ Stage 8: Interactive Model Generation
   - Create interactive decision points
   - Generate discussion questions from Step 4 questions/conclusions
   - Build consequence visualization from causal chains
   - Link to NSPE Code provisions
3. ⏳ Stage 9: Validation
   - Verify scenario completeness
   - Check entity coverage
   - Validate decision tree structure
   - Quality metrics

**Benefits of This Plan**:
- Step 4 provides comprehensive case analysis to understand board reasoning
- Step 5 visualizes analysis in scenario format for better pattern recognition
- Scenario format reveals ethical problem structure more clearly than narrative text
- Enables systematic extraction of transformation patterns and reasoning structures
- Supports cross-case comparison and precedent discovery

---

## Key Documentation

### Primary Implementation Documents
1. **[STEP4_WHOLE_CASE_SYNTHESIS_PLAN.md](docs/STEP4_WHOLE_CASE_SYNTHESIS_PLAN.md)** - Master architectural plan
2. **[STEP4_IMPLEMENTATION_PROGRESS.md](docs/STEP4_IMPLEMENTATION_PROGRESS.md)** - Current status and progress
3. **[MENTION_FIRST_IMPLEMENTATION_COMPLETE.md](docs/MENTION_FIRST_IMPLEMENTATION_COMPLETE.md)** - Mention-first extraction achievement
4. **[MULTI_SECTION_EXTRACTION_PLAN.md](docs/MULTI_SECTION_EXTRACTION_PLAN.md)** - Multi-section architecture details

### Testing & Quality
5. **[TESTING_METHODOLOGY.md](docs/TESTING_METHODOLOGY.md)** - Testing strategy and smoke tests
6. **[PASS1_TESTING_SUMMARY.md](docs/PASS1_TESTING_SUMMARY.md)** - Pass 1 testing results
7. **[TECHNICAL_DEBT.md](docs/TECHNICAL_DEBT.md)** - Future work priorities

### Theoretical Foundation
8. **[chapter2.md](docs/chapter2.md)** - 9-concept methodology
9. **[chapter2__section_2.2.5_resources.md](docs/chapter2__section_2.2.5_resources.md)** - Resources definition
10. Chapter 2 sections for all 9 concept types (Roles, Principles, Obligations, States, Actions, Events, Capabilities, Constraints)

### Integration & Operations
11. **[PROV-O_PROVENANCE_IMPLEMENTATION.md](docs/PROV-O_PROVENANCE_IMPLEMENTATION.md)** - Provenance tracking
12. **[MCP_INTEGRATION_GUIDE.md](docs/MCP_INTEGRATION_GUIDE.md)** - OntServe integration
13. **[DEPLOYMENT_INSTRUCTIONS.md](docs/DEPLOYMENT_INSTRUCTIONS.md)** - Production deployment

---

## Quick Start

### Running the System
```bash
cd /home/chris/onto/proethica
python run.py
```

Access at: http://localhost:5000

### Testing
```bash
# Run smoke tests
./tests/smoke_test_phase1.sh

# Test on Case 10 (complete workflow)
# Navigate to: http://localhost:5000/scenario_pipeline/case/10/step1
```

### Database Commands
```bash
export PGPASSWORD=PASS

# Clear case data
psql -h localhost -U postgres -d ai_ethical_dm -c \
  "DELETE FROM temporary_rdf_storage WHERE case_id = 10;
   DELETE FROM extraction_prompts WHERE case_id = 10;"

# Check entity counts by section
psql -h localhost -U postgres -d ai_ethical_dm -c \
  "SELECT section_type, entity_type, COUNT(*)
   FROM extraction_prompts ep
   JOIN temporary_rdf_storage t ON t.extraction_session_id = ep.extraction_session_id
   WHERE case_id = 10
   GROUP BY section_type, entity_type;"
```

---

## Implementation Status

### COMPLETE
- Pass 1 (Roles, States, Resources): TESTED, PRODUCTION READY
- Pass 2 (Principles, Obligations, Constraints, Capabilities): TESTED, PRODUCTION READY
- Pass 3 (Actions, Events): TESTED, PRODUCTION READY
- Step 4 Whole-Case Synthesis: COMPLETE
  - Code provision extraction with mention-first approach
  - Question/Conclusion extraction with entity tagging
  - Q→C linking and provision→entity linking
  - Cross-section synthesis ready

### Multi-Section Extraction Pattern
All passes extract from 2 sections:
1. **Facts Section** - Primary case narrative
2. **Discussion Section** - Analysis and reasoning

**Note**: Questions, Conclusions, References moved to Step 4 for comprehensive synthesis with complete entity context.

---

## Critical Lessons & Best Practices

### Always Do This
- Pass `section_type` parameter from JavaScript to backend
- Use `.lower()` for all string comparisons (case-insensitive)
- Scope deletion filters to `extraction_session_id` (not just case_id)
- Test multi-section workflows
- Verify data isolation between sections

### Never Do This
- Assume parameters are passed without verification
- Use exact string matching for entity types
- Delete entities without scoping to specific session
- Test only one section and assume others work
- Skip integration testing

### Pass-Specific Section Behavior
- **Pass 1**: Extracts `EthicalQuestion`/`EthicalConclusion` entities with `answersQuestion` relationship (DEPRECATED - moved to Step 4)
- **Pass 2**: Extracts normative requirements independently (no special Q→C linking)
- **Pass 3**: Check ontology for temporal relationships before implementing special handling
- **Step 4**: Comprehensive Questions + Conclusions analysis with complete entity context

---

## Integration with Other Systems

### OntServe (Ontology Management)
- Port: 8082 (MCP server)
- Purpose: Provides ontology queries and entity definitions
- Integration: ProEthica queries existing concepts during extraction

### OntExtract (Document Processing)
- Port: 8765
- Purpose: Temporal analysis and semantic drift
- Integration: Shared utilities and LLM services

### PostgreSQL Databases
- **ai_ethical_dm**: ProEthica case data and extractions
- **ai_ethical_dm_test**: Testing database (isolated)
- **ontserve**: Ontology storage and reasoning
- User: postgres / Password: PASS

---

## Historical Documentation

Historical and superseded documentation: see [docs/archive/](docs/archive/)

---

## Configuration

### Environment Variables
```bash
# 9-Concept System (ACTIVE)
EXTRACTION_MODE=multi_pass
ENABLE_ROLE_EXTRACTION=true
ENABLE_PRINCIPLE_EXTRACTION=true
ENABLE_OBLIGATION_EXTRACTION=true
ENABLE_STATE_EXTRACTION=true
ENABLE_RESOURCE_EXTRACTION=true
ENABLE_ACTION_EXTRACTION=true
ENABLE_EVENT_EXTRACTION=true
ENABLE_CAPABILITY_EXTRACTION=true
ENABLE_CONSTRAINT_EXTRACTION=true

# MCP Integration
ENABLE_EXTERNAL_MCP_ACCESS=true
ONTSERVE_MCP_URL=http://localhost:8082

# Enhanced Processing
ENABLE_CONCEPT_SPLITTING=false     # Set to true for LLM-based splitting
ENABLE_CONCEPT_ORCHESTRATION=false # Set to true for advanced pipeline
```

---

## Contact & Support

**Project Location**: /home/chris/onto/proethica
**Database**: ai_ethical_dm (PostgreSQL, localhost:5432)
**Web Interface**: http://localhost:5000
**Document Owner**: ProEthica Development Team

**For Questions**:
1. Check this CLAUDE.md first
2. Review relevant docs/ files
3. Check archived documentation if needed
4. Review code comments in app/services/extraction/

---

**SYSTEM STATUS**: Step 4 COMPLETE + All Passes TESTED + PRODUCTION READY
