# ProEthica Refactoring Progress

**Last Updated:** November 19, 2025 (End of Day - Demo Prep Complete)
**Active Branch:** `development`
**Current Focus:** Demo Testing & Verification

---

## DEMO PREP STATUS - November 19, 2025 (Evening)

**Ready for Demo Tonight:** ✅

### Completed Today

#### 1. Phase 1 Provenance - FULLY TESTED ✅
- ✅ Successfully committed 10 classes with full provenance to `proethica-intermediate-extracted.ttl`
- ✅ All provenance properties verified (case ID, section, pass, timestamps, source text)
- ✅ Committed to git (both ProEthica and OntServe repos)
- ✅ OntServe loading provenance ontology correctly

#### 2. Critical Bug Fixes ✅
- ✅ **Pass 2 Facts Section Display** - Fixed orphaned entities issue
  - Problem: 32 Pass 2 entities from Facts section weren't showing in review page
  - Root cause: Entities stored without corresponding extraction_prompts records
  - Fix: Created missing extraction_prompts linking sessions to section_type='facts'
  - Now visible: 6 principles, 8 obligations, 8 constraints, 10 capabilities

- ✅ **Config Import Errors** - Fixed OntServe refresh script path issues
  - Simplified sys.path setup to avoid package name conflicts
  - Refresh functionality now works without errors

- ✅ **Dateutil Dependency** - Removed external dependency
  - Using built-in `datetime.fromisoformat()` instead
  - No more "module not found" errors

- ✅ **Git Tracking of Extraction Data** - Fixed dev/prod data conflict risk
  - Problem: Runtime extraction data was tracked in git, risking overwrites between environments
  - Fixed: Removed from tracking, added to .gitignore
  - Now excluded: `proethica-intermediate-extracted.ttl`, `proethica-case-*.ttl`
  - Still tracked (correct): Schema files only (core, intermediate, cases, provenance)
  - Impact: Dev and production can have different extracted data without conflicts

#### 3. Test Environment Prepared ✅
- ✅ **Case 13 cleaned** - Ready for fresh end-to-end demo
  - All 163 entities deleted
  - All 18 extraction prompts cleared
  - Clean slate for testing complete workflow

- ✅ **Case 7 status** - Partially extracted for reference
  - Pass 1: Complete (10 classes, 15 individuals committed with provenance)
  - Pass 2: Complete (73 entities - 32 facts + 41 discussion)
  - Pass 3: In progress (temporal dynamics extraction running)

### What's Ready for Demo Tonight

**Tested & Working:**
1. ✅ Pass 1 extraction (Facts section) with provenance
2. ✅ Commit to OntServe with full provenance preservation
3. ✅ Pass 2 Facts section extraction and display
4. ✅ Pass 2 Discussion section extraction and display
5. ✅ Entity review pages showing correct counts
6. ✅ Clear and re-run functionality (all passes)

**Available Test Cases:**
- **Case 7:** Partially complete (good for showing existing work)
- **Case 13:** Clean slate (good for fresh demo of full workflow)

### Known Issues (Non-Critical)

1. **Step 3 Temporal Extraction Performance**
   - Issue: LLM API calls can be slow (2-5 minutes for full extraction)
   - Workaround: Stay on page until extraction completes
   - Note: SSE connection closes if user navigates away

2. **Provenance Not Yet on Temporal Entities**
   - Pass 3 entities don't have Phase 1 provenance yet
   - Would need Phase 2 work to add section/pass tracking
   - Not critical for tonight's demo

### Demo Recommendations

**Best Demo Flow:**
1. Use **Case 13** for clean end-to-end walkthrough
2. Show **Pass 1 extraction** → Review → **Commit with provenance**
3. Check `proethica-intermediate-extracted.ttl` to show provenance properties
4. Show **Pass 2 extraction** (Facts or Discussion)
5. Demonstrate **Clear & Re-run** functionality
6. Optionally show **Pass 3 temporal dynamics** (if time allows, be patient)

**Files to Show:**
- `OntServe/ontologies/proethica-intermediate-extracted.ttl` - Classes with provenance
- `OntServe/ontologies/proethica-case-13.ttl` - Case-specific individuals
- `OntServe/ontologies/proethica-provenance.ttl` - Provenance ontology definition

---

## CRITICAL: Branch Information

**⚠️ ACTIVE BRANCH:**
```bash
git checkout development
```

**Branch Status:**
- All work consolidated in `development` branch
- Feature branches merged
- Backup available at `development-backup-before-merge`

---

## Recent Completed Tasks

### November 19, 2025 - Step 3/4 Clear & Re-run Functionality

**Problem:** Users could run extraction multiple times creating duplicate entities. Step 4 review page showed committed entities even after clearing.

**Solution Implemented:**

#### Step 3 (Temporal Dynamics) - COMPLETE
- ✅ Warning banner when extraction has been run before
- ✅ "Clear Pass 3 Data" button on review page
- ✅ Clears all temporal entities: actions, events, causal chains, timeline, Allen relations
- ✅ Clears extraction prompts and artifacts
- ✅ Page reloads to show clean state

#### Step 4 (Whole Case Synthesis) - COMPLETE
- ✅ Warning banner when synthesis has been run
- ✅ "Clear Synthesis Data" button on main page
- ✅ Clears synthesis results: code provisions, questions, conclusions
- ✅ Clears synthesis annotations (138 text span mappings)
- ✅ Clears precedent case references (11 entities)
- ✅ "Refresh from OntServe" button (detects deleted entities)
- ✅ Always-visible review button (like other steps)
- ✅ Removed "About Step 4" collapsible card

#### Critical Bug Fixes
- ✅ **Entity count filtering**: Review pages now only show uncommitted entities
- ✅ **Committed/uncommitted clearing**: Clear buttons now delete BOTH committed and uncommitted entities
- ✅ **CSRF token fix**: Added CSRF tokens to all AJAX POST requests
- ✅ **Orphaned entity cleanup**: Manually removed 34 orphaned entities from legacy data
- ✅ **Precedent entity handling**: Added to Pass 4 clearing list, shows in graph

**Files Modified:**
- `app/services/case_entity_storage_service.py` - Clearing service with Pass 3/4 support
- `app/routes/scenario_pipeline/entity_review.py` - Added Pass 4 redirect
- `app/routes/scenario_pipeline/step4.py` - Fixed entity count queries, updated graph query
- `app/templates/entity_review/enhanced_temporal_review.html` - Warning banner + clear button
- `app/templates/scenarios/step3_dual_extraction.html` - Warning banner + clear button
- `app/templates/scenarios/step4.html` - Clear button, refresh button, always-visible review
- `app/templates/scenario_pipeline/step4_review.html` - Refresh button with CSRF token

**Database Changes:**
- Pass 3 clearing: `extraction_type='temporal_dynamics_enhanced'`
- Pass 4 clearing: `extraction_type IN ['code_provision_reference', 'ethical_question', 'ethical_conclusion', 'precedent_case_reference']`
- Synthesis annotations: `ontology_name='step4_synthesis'`

**Key Insight:** Orphaned entities occurred when prompts were deleted but entities remained committed. New logic clears both committed and uncommitted to prevent this.

---

### November 19, 2025 - Late Evening: Phase 1 Provenance Implementation COMPLETE ✅

**Status:** Phase 1 of Entity Storage Architecture fully implemented and ready for testing

**Files Created:**
- `/home/chris/onto/OntServe/ontologies/proethica-provenance.ttl` - New provenance ontology
  - Defines 7 provenance properties: `firstDiscoveredInCase`, `firstDiscoveredAt`, `discoveredInCase`, `discoveredInSection`, `discoveredInPass`, `sourceText`, `extractedBy`
  - Imports W3C PROV-O and ProEthica Core ontologies
  - Fully documented with rdfs:label and rdfs:comment

**Files Modified:**
- [app/services/rdf_extraction_converter.py](app/services/rdf_extraction_converter.py)
  - Updated `convert_extraction_to_rdf()` to accept `section_type` and `pass_number` parameters
  - Updated `convert_states_extraction_to_rdf()` with provenance parameters
  - Updated `convert_resources_extraction_to_rdf()` with provenance parameters
  - Updated `_convert_role_classes()` to add comprehensive provenance to all role classes
  - Updated `_add_state_class_to_graph()` to add comprehensive provenance to all state classes
  - Updated `_add_resource_class_to_graph()` to add comprehensive provenance to all resource classes

- [app/routes/scenario_pipeline/step1.py](app/routes/scenario_pipeline/step1.py)
  - Updated roles extraction to pass `section_type='facts'/'discussion'` and `pass_number=1`
  - Updated states extraction to pass `section_type='facts'/'discussion'` and `pass_number=1`
  - Updated resources extraction to pass `section_type='facts'/'discussion'` and `pass_number=1`

**Provenance Properties Added to ALL Classes:**
```turtle
# Standard W3C PROV-O
prov:generatedAtTime "2025-11-19T..."^^xsd:dateTime
prov:wasAttributedTo "Case 7 Extraction"

# ProEthica-specific (NEW)
proeth-prov:firstDiscoveredInCase "7"^^xsd:integer
proeth-prov:firstDiscoveredAt "2025-11-19T..."^^xsd:dateTime
proeth-prov:discoveredInCase "7"^^xsd:integer
proeth-prov:discoveredInSection "facts"  # or "discussion"
proeth-prov:discoveredInPass "1"^^xsd:integer
proeth-prov:sourceText "exact quote from case..."
```

**Next Steps:**
1. ✅ Test with Case 7 extraction - COMPLETE
2. ✅ Commit entities and verify TTL files contain provenance - COMPLETE
3. ✅ Manually inspect `proethica-intermediate-extracted.ttl` - COMPLETE
4. Verify provenance queries work via OntServe MCP - Future work

---

### November 19, 2025 - Phase 1 Provenance TESTED AND VERIFIED ✅

**Status:** Phase 1 implementation successfully tested with Case 7 Facts section extraction

**Test Results:**
- ✅ **10 classes committed** to `proethica-intermediate-extracted.ttl` with full provenance
  - 2 Role classes: EnvironmentalEngineerRole, EngineeringMentorRole
  - 4 State classes: MentorAbsenceState, AIToolInexperienceState, TechnicalWritingInsecurityState, DesignDeficiencyDiscoveryState
  - 4 Resource classes: AISoftwareTool, ProfessionalJournalArticle, GroundwaterMonitoringData, LocalSafetyRegulations

- ✅ **15 individuals committed** to `proethica-case-7.ttl`
  - 3 role individuals (Engineer A, Engineer B, Client W)
  - 6 state individuals (various engineer states)
  - 6 resource individuals (AI tools, monitoring data, regulations, journal articles)

**Verified Provenance Properties on ALL Classes:**
```turtle
# Example: EnvironmentalEngineerRole
proeth-prov:firstDiscoveredInCase 7 ;
proeth-prov:firstDiscoveredAt "2025-11-19T16:24:27.319739"^^xsd:dateTime ;
proeth-prov:discoveredInCase 7 ;
proeth-prov:discoveredInSection "facts" ;
proeth-prov:discoveredInPass 1 ;
proeth-prov:sourceText "Engineer A, an environmental engineer..." ;
prov:generatedAtTime "2025-11-19T16:24:27.319739"^^xsd:dateTime ;
prov:wasAttributedTo "Case 7 Extraction" ;
```

**Additional Fixes Applied:**
- [app/services/ontserve_commit_service.py](app/services/ontserve_commit_service.py)
  - Added provenance extraction from `rdf_json_ld` field
  - Removed `python-dateutil` dependency (using built-in `datetime.fromisoformat`)
  - Added `PROETHICA_PROV` namespace binding
  - Temporarily disabled OntServe refresh calls (minor import issue, non-critical)

- [OntServe/services/sparql_service.py](OntServe/services/sparql_service.py)
  - Added `proethica-provenance.ttl` to ontology loading list

**Files Updated:**
- `proethica-intermediate-extracted.ttl`: 151 lines (10 classes with full provenance)
- `proethica-case-7.ttl`: 262 lines (15 individuals)

**Phase 1 Architecture Status: COMPLETE AND OPERATIONAL** ✅

---

### November 19, 2025 - Evening Session: Demo Walkthrough + Architecture Redesign

**Context:** Demo walkthrough of Case 7 extraction workflow revealed critical issues with entity storage and synchronization.

#### Bug Fixes (CRITICAL)

**1. RDF Converter Crash on Null Values**
- **Issue:** `TypeError: 'NoneType' object is not iterable` when extracting roles
- **Location:** [app/services/rdf_extraction_converter.py:254](app/services/rdf_extraction_converter.py#L254)
- **Root Cause:** LLM returned `"ethical_tensions": null` instead of list
- **Fix:** Added null checks for `ethical_tensions` and `active_obligations`
  ```python
  if "ethical_tensions" in individual and individual["ethical_tensions"] is not None:
      # Process tensions
  ```
- **Impact:** Roles extraction now working correctly for Case 7

**2. Confusing UI Messages**
- **Issue:** "No new roles classes found" message on Facts section review page
- **Location:** [app/templates/scenarios/entity_review.html:799](app/templates/scenarios/entity_review.html#L799)
- **Fix:** Added section-aware messaging:
  - Facts: "All role classes in the facts section were already present in the ontology"
  - Discussion: "All role classes were already captured in the Facts section"
- **Impact:** Clearer user guidance during review

#### Architecture Planning (MAJOR)

**Problem Identified:**
- No case tracking for committed classes in `proethica-intermediate-extracted.ttl`
- Unclear data flow between ProEthica DB, TTL files, and OntServe
- Confusing clear operation messages
- Uncommitted classes potentially leaking between cases

**Solution Designed:**
Created comprehensive architecture plan: [docs/ENTITY_STORAGE_ARCHITECTURE_PLAN.md](docs/ENTITY_STORAGE_ARCHITECTURE_PLAN.md)

**Key Architectural Decisions:**

1. **Three Storage Layers:**
   - Uncommitted entities: ProEthica DB only (no TTL files)
   - Committed classes: `proethica-intermediate-extracted.ttl` (shared, with provenance)
   - Committed individuals: `proethica-case-{id}.ttl` (case-specific)

2. **Prompt Building Query Logic:**
   ```
   For Case X:
     ✓ Committed classes from ALL cases (via OntServe)
     ✓ Committed individuals from SAME case only (via OntServe)
     ✓ Uncommitted classes from SAME case only (via ProEthica DB)
     ✓ Uncommitted individuals from SAME case only (via ProEthica DB)
     ✗ Uncommitted entities from other cases (NO LEAKAGE)
   ```

3. **Provenance Requirements:**
   All committed classes must include:
   - `proeth-prov:firstDiscoveredInCase` - Original case ID
   - `proeth-prov:firstDiscoveredAt` - Discovery timestamp
   - `proeth-prov:discoveredInCase` - All case IDs using this class
   - `proeth-prov:discoveredInSection` - Facts/Discussion/etc
   - `proeth-prov:discoveredInPass` - Pass 1/2/3
   - `proeth-prov:sourceText` - Original text snippet

4. **Class Deduplication Strategy:**
   - Phase 1: Allow duplicates with different case provenance
   - Phase 2: Manual curator review in OntServe UI for merging

5. **Clear Operations:**
   - Section-specific: Clear only uncommitted from specific pass+section
   - Case-wide: Clear all data (uncommitted + committed) for entire case
   - Message improvement: Show uncommitted vs committed counts separately

**Implementation Phases:**
- Phase 1 (This Week): Add provenance to all class exports
- Phase 2 (Next Week): Fix prompt building queries
- Phase 3: Update clear operations and messaging
- Phase 4: Add "Refresh from OntServe" button + UI improvements
- Phase 5: Add transaction-based rollback on commit failures

**Files to Modify:**
- `app/services/rdf_extraction_converter.py` - Add provenance properties
- `app/services/ontserve_commit_service.py` - Update commit logic
- `app/services/extraction/dual_*_extractor.py` - Fix query logic
- `app/services/case_entity_storage_service.py` - Section-specific clearing
- `app/templates/entity_review/*.html` - Add refresh button, improve messages

#### Demo Walkthrough Status

**Completed:**
- ✅ Step 1 Facts extraction - 2 role classes, 3 individuals, 4 state classes, 6 individuals, 4 resource classes, 6 individuals
- ✅ Step 1 Discussion extraction - 3 state classes, 5 individuals, 3 resource classes, 5 individuals
- ✅ Review page verification - All entities displaying correctly
- ✅ Fixed critical RDF converter bug
- ✅ Fixed confusing UI messages

**Pending:**
- Step 1 Clear & Re-run functionality testing
- Step 2 (Normative Requirements) extraction
- Step 3 (Temporal Dynamics) extraction
- Step 4 (Synthesis) extraction

**Feedback Tracked:**
- [DEMO_FEEDBACK.md](DEMO_FEEDBACK.md) - Contains UX issues identified during walkthrough

---

### November 17, 2025 - Source Text Provenance

- ✅ **Added source text context to ALL 9 concept types** (Pass 1-3)
- ✅ All extractors now include `source_text: Optional[str]` field
- ✅ LLM prompts request "EXACT text snippet from case (max 200 chars)"
- ✅ RDF converter stores using `PROETHICA_PROV.sourceText` property
- ✅ UI displays source text with blue italic text and quote icon
- ✅ Archived deprecated Pass 3 templates and routes

**Templates Updated:**
- entity_review.html (Pass 1)
- entity_review_pass2.html (Pass 2)
- enhanced_temporal_review.html (Pass 3 - active)

---

### November 16-17, 2025 - Foundation Work

#### Repository Cleanup
- ✅ Removed `/backups/` directory (26 MB)
- ✅ Removed `/ontology_editor/` module (redirect to OntServe)
- ✅ Removed `cases_structure_update.py` (309 lines, deprecated)
- ✅ Cleaned up root directory (moved 15 test files to `/experiments/`)
- ✅ Repository size reduced by ~26 MB

#### LangChain Migration
- ✅ Updated to LangChain 1.0
- ✅ Added `langchain-classic>=1.0.0` for legacy chains
- ✅ Updated imports: `langchain.chains` → `langchain_classic.chains`
- ✅ Phase 1 complete: Removed deprecation warnings
- ⏳ Phase 2 in progress: 4/24 files migrated to LLMManager

#### Bug Fixes
- ✅ Fixed empty section handling (dissenting_opinion)
- ✅ Fixed ontology_editor import error (EntityService stub)

#### Documentation
- ✅ Created comprehensive OntServe integration guide
- ✅ Created LLM service migration plan
- ✅ Updated INSTALL.md with simplified instructions

---

## Application Status

**Current State:**
- ✅ Application starts successfully
- ✅ All imports working
- ✅ OntServe MCP server detected on port 8082
- ✅ Database connection successful
- ✅ Clear & Re-run functionality working for all passes

**Demo Ready:**
- ✅ Step 1-3 extraction with clear functionality
- ✅ Step 4 synthesis with clear + refresh
- ✅ No duplicate entities on re-run
- ✅ Clean entity count displays

---

## What's Next?

### Immediate Priority: Entity Storage Architecture (This Week)

**Phase 1: Provenance Implementation**
1. **Create provenance ontology** - `proethica-provenance.ttl`
   - Define all provenance properties (case, date, section, pass)
   - Add to OntServe ontology imports

2. **Update RDF Converter** - `app/services/rdf_extraction_converter.py`
   - Add provenance annotations to all class exports
   - Include case_id, section_type, pass_number, discovery_date

3. **Update Commit Service** - `app/services/ontserve_commit_service.py`
   - Modify `_commit_classes_to_intermediate()` to write provenance
   - Test with Case 7 extraction

4. **Verification**
   - Manually inspect `proethica-intermediate-extracted.ttl`
   - Confirm all classes have complete provenance
   - Test query from OntServe via MCP

**See detailed plan:** [docs/ENTITY_STORAGE_ARCHITECTURE_PLAN.md](docs/ENTITY_STORAGE_ARCHITECTURE_PLAN.md)

---

### Secondary Priority: Complete Demo Walkthrough

**Remaining Steps:**
1. **Test Clear & Re-run** - Step 1 functionality
2. **Step 2 Extraction** - Normative Requirements (Principles, Obligations, Constraints, Capabilities)
3. **Step 3 Extraction** - Temporal Dynamics (Actions, Events, timeline)
4. **Step 4 Synthesis** - Code provisions, questions, conclusions
5. **Feedback Compilation** - Update [DEMO_FEEDBACK.md](DEMO_FEEDBACK.md)

---

### Lower Priority Tasks

1. **Continue LLM Migration** (Phase 2: 20/24 files remaining)
   - Migrate remaining services to LLMManager
   - Standardized timeout/retry handling
   - Better token tracking

2. **Repository Cleanup Round 2**
   - Evaluate `/ttl_triple_association/` (107K)
   - Clean up experimental files
   - Review annotation service duplicates

3. **Integration Testing**
   - End-to-end extraction tests
   - Clear functionality tests across all passes
   - Commit/rollback scenarios

---

## Key Commands

```bash
# Ensure correct branch
git checkout development

# Pull latest
git pull origin development

# Start application
source venv-proethica/bin/activate
python run.py

# Check database
export PGPASSWORD=PASS
psql -h localhost -U postgres -d ai_ethical_dm -c "SELECT COUNT(*) FROM temporary_rdf_storage WHERE case_id = 8;"
```

---

## Known Issues

1. **Orphaned Entities (RESOLVED)**
   - Issue: Entities remained when prompts deleted
   - Fix: Clear now deletes both committed and uncommitted
   - Legacy data: Manually cleaned up 34 orphaned entities

2. **LangChain 1.0 Migration (COMPLETE)**
   - All imports updated
   - `langchain-classic` installed for legacy code
   - No breaking changes

3. **MCP Integration (WORKING)**
   - OntServe running on port 8082
   - All API calls functioning
   - Refresh functionality working

---

## Reference Files

**Planning:**
- [docs/LLM_SERVICE_MIGRATION_PLAN.md](docs/LLM_SERVICE_MIGRATION_PLAN.md) - Migration roadmap
- [docs/PROETHICA_ONTSERVE_INTEGRATION.md](docs/PROETHICA_ONTSERVE_INTEGRATION.md) - OntServe integration

**Implementation:**
- [INSTALL.md](INSTALL.md) - Installation guide
- [requirements.txt](requirements.txt) - Dependencies

---

**END OF PROGRESS FILE**
