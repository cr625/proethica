# Entity Storage Architecture - Implementation Plan

**Created:** November 19, 2025
**Status:** Planning Phase
**Purpose:** Redesign entity storage, synchronization, and querying for clarity and correctness

---

## Current Problems

1. **No case tracking for committed classes** - Cannot identify which case contributed which class
2. **Confusing clear messages** - Shows "62 entities from other passes/sections remain" (actually from other cases)
3. **Sync complexity** - 3 data sources (ProEthica DB, TTL files, OntServe DB) with unclear authority
4. **Duplicate class handling** - No mechanism to detect/merge similar classes across cases
5. **Prompt queries unclear** - Mixing committed/uncommitted from different cases incorrectly

---

## Revised Architecture

### 1. Data Storage Layers

#### Layer 1: Uncommitted Entities (Work-in-Progress)
**Location:** ProEthica DB (`temporary_rdf_storage` table)
- **Scope:** Case-specific only
- **Visibility:** Only visible within the same case
- **Persistence:** Database only (NO TTL files for uncommitted)
- **Lifecycle:** Deleted when cleared OR promoted to committed

#### Layer 2: Committed Entities (Permanent)
**Location:** OntServe TTL files

**Classes:**
- **File:** `proethica-intermediate-extracted.ttl`
- **Scope:** Shared across ALL cases
- **Provenance Required:** (see Provenance Schema below)
- **Deduplication:** Merge similar classes with multi-case provenance

**Individuals:**
- **File:** `proethica-case-{id}.ttl` (e.g., `proethica-case-7.ttl`)
- **Scope:** Case-specific (never shared between cases)
- **Provenance Required:** Case ID, discovery date

**Authority:** OntServe becomes primary source once committed

---

### 2. Provenance Schema

All committed classes MUST include:

```turtle
:EnvironmentalEngineerRole
    rdf:type owl:Class ;
    rdfs:label "Environmental Engineer Role" ;
    rdfs:subClassOf proeth-core:Role ;
    rdfs:comment "A specialized engineering role focused on..." ;

    # Case provenance (REQUIRED)
    proeth-prov:firstDiscoveredInCase "7"^^xsd:integer ;
    proeth-prov:firstDiscoveredAt "2025-11-19T12:00:00Z"^^xsd:dateTime ;
    proeth-prov:discoveredInCase "7"^^xsd:integer, "8"^^xsd:integer, "12"^^xsd:integer ;

    # Extraction context (REQUIRED)
    proeth-prov:discoveredInSection "facts" ;  # or "discussion", "questions", "conclusions"
    proeth-prov:discoveredInPass "1"^^xsd:integer ;  # Pass 1, 2, or 3

    # Source text (OPTIONAL but recommended)
    proeth-prov:sourceText "Engineer A, an environmental engineer..." .
```

---

### 3. Prompt Building Logic

**For Case X extraction (Pass N):**

```
Query Priority Order:
1. OntServe committed classes (ALL cases)
   - From: proethica-core.ttl
   - From: proethica-intermediate.ttl
   - From: proethica-intermediate-extracted.ttl

2. OntServe committed individuals (SAME case only)
   - From: proethica-case-X.ttl

3. ProEthica DB uncommitted entities (SAME case ONLY, ANY pass)
   - WHERE case_id = X AND is_committed = false
   - Includes classes and individuals from earlier passes

Result: Case X sees:
✓ All committed classes (from ANY case)
✓ All committed individuals (from SAME case only)
✓ All uncommitted classes (from SAME case only, all passes)
✓ All uncommitted individuals (from SAME case only, all passes)
✗ ALL uncommitted entities from other cases (classes AND individuals)
✗ ALL committed individuals from other cases
```

**CRITICAL:** Uncommitted classes are case-scoped - they do NOT leak to other cases until committed.

**Implementation:**
- Update `DualRoleExtractor`, `DualStatesExtractor`, etc.
- Query OntServe via MCP for committed entities
- Query ProEthica DB for uncommitted entities
- Merge results before building prompts

---

### 4. Class Deduplication Strategy

**Phase 1 (Current Implementation):**
- Allow duplicate classes with different case provenance
- Store separately in `proethica-intermediate-extracted.ttl`
- Example:
  ```turtle
  :EnvironmentalEngineerRole_Case7
      rdfs:label "Environmental Engineer Role" ;
      proeth-prov:discoveredInCase "7"^^xsd:integer .

  :EnvironmentalEngineerRole_Case8
      rdfs:label "Environmental Engineer Role" ;
      proeth-prov:discoveredInCase "8"^^xsd:integer .
  ```

**Phase 2 (Future - OntServe Review Interface):**
- Build duplicate detection UI in OntServe
- Group similar classes (by label similarity, definition matching)
- Allow curator to merge duplicates
- Merged class retains all provenance from source classes

**Current Action:** Implement Phase 1, defer Phase 2

---

### 5. Clear Operations

#### Clear Uncommitted Entities (Pass/Section Specific)

**Scope:** Delete uncommitted entities from specific pass + section

**Query:**
```sql
DELETE FROM temporary_rdf_storage
WHERE case_id = ?
  AND is_committed = false
  AND extraction_type IN (...)  -- concept types for this pass
  AND provenance_metadata->>'section_type' = ?  -- 'facts' or 'discussion'
```

**Message:**
```
Cleared 8 uncommitted entities from Discussion section (Pass 1)
12 committed entities from Case 7 remain in OntServe
```

#### Clear All Case Data

**Scope:** Delete ALL data for a case (uncommitted + committed)

**Actions:**
1. Delete from ProEthica DB: `DELETE FROM temporary_rdf_storage WHERE case_id = ?`
2. Delete TTL file: `rm proethica-case-{id}.ttl`
3. Update class provenance in `proethica-intermediate-extracted.ttl`:
   - Remove case ID from `proeth-prov:discoveredInCase` list
   - If no cases remain, delete the class entirely

**Message:**
```
Cleared all data for Case 7:
- 45 uncommitted entities deleted
- proethica-case-7.ttl removed
- Case 7 provenance removed from 12 classes
```

---

### 6. OntServe Synchronization

#### Sync on Commit

**When:** User clicks "Commit Selected to OntServe"

**Process:**
1. Export selected entities to TTL files
   - Classes → append to `proethica-intermediate-extracted.ttl`
   - Individuals → append to `proethica-case-{id}.ttl`
2. Call OntServe API to refresh ontology
3. Mark entities as committed in ProEthica DB
4. Update `is_committed = true`, `committed_at = NOW()`

#### Auto-Refresh on Review Pages

**When:** User views entity review pages

**Process:**
1. Query OntServe via MCP for committed entities
2. Query ProEthica DB for uncommitted entities
3. Merge and display
4. **NO caching** (always fresh data)

**Rationale:** Research demo - correctness over performance

---

### 7. OntServe Interface Changes

#### Remove "Clear Extracted Classes" Button

**Current:** Global button deletes all of `proethica-intermediate-extracted.ttl`

**New:** Remove button from ProEthica interface

**Future:** In OntServe web UI:
- View classes grouped by case (using `proeth-prov:discoveredInCase`)
- Delete classes per case
- Merge duplicate classes

---

## Implementation Phases

### Phase 1: Database & Provenance (Priority 1)

**Files to modify:**
- `app/services/rdf_extraction_converter.py`
  - Add provenance properties to all class exports
  - Include: case_id, section_type, pass_number, discovery_date

- `app/services/ontserve_commit_service.py`
  - Update `_commit_classes_to_intermediate()` to add provenance
  - Update `_commit_individuals_to_case_ontology()` to use case-specific files

**Tasks:**
1. Define provenance properties in `proethica-provenance.ttl`
2. Update RDF converter to include provenance in all exports
3. Test with Case 7 extraction

---

### Phase 2: Prompt Building (Priority 2)

**Files to modify:**
- `app/services/extraction/dual_role_extractor.py`
- `app/services/extraction/dual_states_extractor.py`
- `app/services/extraction/dual_resources_extractor.py`
- (Similar for principles, obligations, etc.)

**Tasks:**
1. Create unified entity query service:
   ```python
   class EntityQueryService:
       def get_entities_for_prompt(self, case_id, concept_type):
           # Query OntServe for committed (all cases for classes, same case for individuals)
           # Query ProEthica DB for uncommitted (same case only)
           # Merge and deduplicate
           return entities
   ```

2. Update all extractors to use new service
3. Add tests for query logic

---

### Phase 3: Clear Operations (Priority 3)

**Files to modify:**
- `app/services/case_entity_storage_service.py`
  - Update `clear_pass_data()` to use section_type filter
  - Add `clear_all_case_data()` method

- `app/routes/scenario_pipeline/entity_review.py`
  - Update clear endpoints
  - Improve messaging

**Tasks:**
1. Implement section-specific clear queries
2. Update clear messages to show uncommitted vs committed counts
3. Test clear operations for each pass/section

---

### Phase 4: UI Improvements (Priority 4)

**Files to modify:**
- `app/templates/entity_review/*.html`
  - Update clear button labels
  - Improve messaging
  - Add "Refresh from OntServe" button

**Tasks:**
1. Remove "Clear Extracted Classes" button (from ProEthica - will be in OntServe UI)
2. Update clear success messages
3. Add entity counts breakdown (uncommitted/committed)
4. **Add "Refresh from OntServe" button** to review pages:
   - Button location: Top of entity review page
   - Action: Re-query OntServe for committed entities
   - Use case: User edits committed entity in OntServe, clicks refresh to see updates
   - Implementation:
     ```python
     @bp.route('/case/<int:case_id>/entities/refresh_from_ontserve', methods=['POST'])
     def refresh_from_ontserve(case_id):
         # Clear cached OntServe data
         # Re-query OntServe via MCP
         # Update display
         return jsonify({'success': True, 'message': 'Refreshed from OntServe'})
     ```

---

### Phase 5: Rollback & Error Handling (Priority 5)

**Files to modify:**
- `app/services/ontserve_commit_service.py`
  - Add transaction management
  - Add rollback on failure

**Implementation:**
```python
def commit_selected_entities(self, case_id: int, entity_ids: List[int]):
    backup_files = {}

    try:
        # Start database transaction
        db.session.begin()

        # Backup existing TTL files before modification
        backup_files['intermediate'] = self._backup_file('proethica-intermediate-extracted.ttl')
        backup_files['case'] = self._backup_file(f'proethica-case-{case_id}.ttl')

        # Step 1: Write to TTL files
        self._commit_classes_to_intermediate(classes_to_commit)
        self._commit_individuals_to_case_ontology(case_id, individuals_to_commit)

        # Step 2: Sync with OntServe
        sync_result = self._synchronize_with_ontserve()
        if not sync_result['success']:
            raise Exception(f"OntServe sync failed: {sync_result['error']}")

        # Step 3: Mark as committed in DB
        for entity in entities:
            entity.is_committed = True
            entity.committed_at = datetime.utcnow()

        # Commit database transaction
        db.session.commit()

        # Success - delete backups
        self._delete_backups(backup_files)

        return {'success': True, ...}

    except Exception as e:
        # Rollback database
        db.session.rollback()

        # Restore TTL files from backup
        self._restore_backups(backup_files)

        # Log error
        logger.error(f"Commit failed, rolled back: {e}")

        return {'success': False, 'error': str(e)}
```

**Tasks:**
1. Implement file backup/restore utilities
2. Wrap all commit operations in try/except
3. Test rollback scenarios (disk full, OntServe down, etc.)

---

## Testing Plan

### Test Case 1: Fresh Extraction
1. Clear all data for Case 7
2. Run Pass 1 Facts extraction
3. Verify uncommitted entities in DB
4. Check prompt for Pass 1 Discussion includes Pass 1 Facts uncommitted entities
5. Verify NO TTL files created yet

### Test Case 2: Commit Flow
1. Commit Pass 1 Facts entities
2. Verify TTL files created:
   - `proethica-intermediate-extracted.ttl` has classes with provenance
   - `proethica-case-7.ttl` has individuals
3. Verify entities marked committed in DB
4. Query OntServe, confirm entities present

### Test Case 3: Cross-Case Visibility
1. Create Case 8
2. Run Pass 1 extraction
3. Verify Case 8 sees:
   - ✓ Committed classes from Case 7
   - ✗ Uncommitted classes from Case 7
   - ✗ Committed individuals from Case 7
   - ✓ Own uncommitted entities

### Test Case 4: Clear Operations
1. Clear Pass 1 Discussion uncommitted entities
2. Verify Facts entities remain
3. Verify committed entities remain
4. Check message accuracy

### Test Case 5: Duplicate Classes
1. Case 7 commits "Environmental Engineer Role"
2. Case 8 extracts similar "Environmental Engineer Role"
3. Verify both stored with different provenance
4. Verify both appear in prompts for Case 9

---

## Success Criteria

✅ Uncommitted entities only visible within same case
✅ Committed classes visible across all cases
✅ Committed individuals only visible within same case
✅ All committed entities have complete provenance
✅ Clear operations scoped correctly (pass + section)
✅ Clear messages accurate and non-confusing
✅ OntServe auto-refreshes on review pages
✅ No TTL files for uncommitted entities
✅ Duplicate classes allowed with provenance tracking

---

## Migration Path

### For Existing Data

**Classes in `proethica-intermediate-extracted.ttl` without provenance:**
1. Backup current file
2. Add default provenance:
   ```turtle
   proeth-prov:firstDiscoveredInCase "unknown"^^xsd:string ;
   proeth-prov:firstDiscoveredAt "2025-01-01"^^xsd:dateTime ;
   ```
3. Mark as needing review in OntServe

**Uncommitted entities in DB:**
- Already have `provenance_metadata` JSON
- Extract case_id, section_type, extraction_pass from JSON
- Use when committing

---

## Questions for Review - ANSWERED

1. **Should we version class definitions when the same class is refined across cases?**
   - **ANSWER: YES** - Version class definitions when refined
   - Implementation: Store all versions with provenance, allow curator to select canonical version

2. **How should we handle class merging in Phase 2 (automatic vs manual)?**
   - **ANSWER: Manual curator approval** - No automatic merging
   - Implementation: OntServe UI shows potential duplicates, curator decides whether to merge

3. **Should committed individuals ever be editable after commit?**
   - **ANSWER: Only editable in OntServe, NOT in ProEthica**
   - Implementation: Add "Refresh from OntServe" button to ProEthica review pages
   - If user needs to edit committed entity:
     1. Edit in OntServe web UI
     2. Click "Refresh from OntServe" in ProEthica
     3. Updated entity appears in ProEthica
   - **Future:** ProEthica could interact directly with OntServe for editing

4. **What's the rollback strategy if a commit fails midway?**
   - **ANSWER: Use database transactions**
   - Implementation:
     ```python
     try:
         db.session.begin()
         # Write TTL files
         # Update OntServe
         # Mark entities as committed in DB
         db.session.commit()
     except Exception:
         db.session.rollback()
         # Delete partial TTL writes
         # Restore previous state
     ```

---

## Next Steps

### Phase 1: COMPLETED ✅ (November 19, 2025)
1. ✅ **Review this plan** - APPROVED with clarifications
2. ✅ **Create proethica-provenance.ttl** - COMPLETE
   - Created comprehensive provenance ontology with 7 properties
   - Imports W3C PROV-O and ProEthica Core
   - File: `/home/chris/onto/OntServe/ontologies/proethica-provenance.ttl`

3. ✅ **Update RDF converter** - COMPLETE
   - Modified `convert_extraction_to_rdf()` to accept section_type and pass_number
   - Updated roles, states, and resources converters
   - All class exports now include comprehensive provenance

4. ✅ **Update extraction routes** - COMPLETE
   - Step 1 routes now pass section_type and pass_number to RDF converter
   - All three concept types (roles, states, resources) updated

### Phase 1: Remaining Tasks
5. **Test with Case 7** - Extract entities and verify provenance in temporary storage
6. **Commit and verify** - Commit entities and check TTL files have provenance
7. **Manual verification** - Inspect `proethica-intermediate-extracted.ttl` for correct annotations

### Phase 2 Implementation (Next Week)
7. **Create EntityQueryService** - Unified query for committed + uncommitted
8. **Update all extractors** - Use new query service for prompt building
9. **Test cross-case visibility** - Verify uncommitted classes don't leak between cases

### Incremental Testing
- Test each phase independently
- Don't move to next phase until previous is verified
- Use Case 7 as primary test case

---

**END OF PLANNING DOCUMENT**
