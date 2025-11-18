# IAO Resources & References Implementation Plan

**Date**: 2025-10-07
**Status**: READY TO IMPLEMENT
**Approach**: Phased, non-breaking implementation

---

## Executive Summary

Implement IAO document hierarchy for Resources and References across all 3 passes without breaking existing functionality.

**Key Principle**: Add new IAO properties **alongside** existing properties, then gradually migrate.

---

## Phase 1: Foundation - Add IAO to Ontology (Non-Breaking)

**Goal**: Add IAO document classes and new properties without changing existing behavior

**Duration**: 1-2 hours

### Step 1.1: Update proethica-core.ttl

**File**: `/home/chris/onto/OntServe/ontologies/proethica-core.ttl`

**What to add**:
```turtle
# ============================================
# IAO Document Integration for Resources
# ============================================

# Note: IAO classes already exist, we just reference them
# iao:0000300 = document
# iao:0000310 = document part

# New properties linking Resources to IAO documents
proeth-core:refersToDocument a owl:ObjectProperty ;
    rdfs:domain proeth-core:Resource ;
    rdfs:range iao:0000300 ;  # IAO document
    rdfs:label "refers to document"@en ;
    rdfs:comment "Links a resource to the IAO document it represents or references"@en ;
    rdfs:isDefinedBy <http://proethica.org/ontology/core#> .

proeth-core:availableTo a owl:ObjectProperty ;
    rdfs:domain proeth-core:Resource ;
    rdfs:range proeth-core:Role ;  # agents in roles
    rdfs:label "available to"@en ;
    rdfs:comment "Indicates which agent(s) in the case scenario have access to this resource"@en ;
    rdfs:isDefinedBy <http://proethica.org/ontology/core#> .

proeth-core:citedByAgent a owl:ObjectProperty ;
    rdfs:domain proeth-core:Resource ;
    rdfs:range proeth-core:Role ;  # BER, etc.
    rdfs:label "cited by agent"@en ;
    rdfs:comment "Indicates which agent(s) cited this resource as authoritative source"@en ;
    rdfs:isDefinedBy <http://proethica.org/ontology/core#> .

# Property for linking conclusions/principles to cited documents
proeth-core:citesAuthority a owl:ObjectProperty ;
    rdfs:domain proeth-core:Principle ;  # and subclasses
    rdfs:range iao:0000300 ;  # IAO document or document part
    rdfs:label "cites authority"@en ;
    rdfs:comment "Links an ethical concept to the authoritative document that establishes or supports it"@en ;
    rdfs:isDefinedBy <http://proethica.org/ontology/core#> .
```

**Action**:
```bash
# Edit the file
nano /home/chris/onto/OntServe/ontologies/proethica-core.ttl

# Refresh OntServe after editing
cd /home/chris/onto/OntServe
python scripts/refresh_entity_extraction.py proethica-core
```

**Verification**: Query OntServe MCP to confirm new properties exist

**Impact**: ✅ Non-breaking - adds new properties, doesn't change existing ones

---

### Step 1.2: Update TemporaryRDFStorage Model

**File**: `/home/chris/onto/proethica/app/models/temporary_rdf_storage.py`

**What to add**: Optional fields for IAO document references

```python
class TemporaryRDFStorage(db.Model):
    # ... existing fields ...

    # NEW: IAO document references (optional, backwards compatible)
    iao_document_uri = db.Column(db.String(500), nullable=True)  # URI of iao:0000300 or iao:0000310
    iao_document_label = db.Column(db.String(500), nullable=True)  # Human-readable label
    cited_by_role = db.Column(db.String(200), nullable=True)  # Which role cited this (BER, etc.)
    available_to_role = db.Column(db.String(200), nullable=True)  # Which role has access
```

**Action**:
```bash
# Create migration
cd /home/chris/onto/proethica
flask db revision -m "Add IAO document references to TemporaryRDFStorage"

# Edit the migration file to add columns
# Then apply:
flask db upgrade
```

**Impact**: ✅ Non-breaking - nullable columns, existing data unaffected

---

## Phase 2: Pass 1 Resources - Add IAO Support (Backwards Compatible)

**Goal**: Update Pass 1 Resources extractor to ADD IAO document references alongside existing extraction

**Duration**: 2-3 hours

### Step 2.1: Update DualResourcesExtractor

**File**: `/home/chris/onto/proethica/app/services/extraction/dual_resources_extractor.py`

**Changes**:

1. **Add IAO document extraction to the prompt**:
```python
# In _create_dual_resource_extraction_prompt method, add:

For each resource, also identify if it's a document:
- document_type: 'document' if it's a written document, 'document_part' if it's a specific section
- document_title: Full title of the document
- document_section: Specific section reference (e.g., "II.4.a") if applicable
```

2. **Add document_info to ResourceIndividual model**:
```python
@dataclass
class ResourceIndividual:
    # ... existing fields ...
    document_type: Optional[str] = None  # 'document' or 'document_part'
    document_title: Optional[str] = None
    document_section: Optional[str] = None
```

3. **Pass document info to storage**:
```python
# In save_resources_to_storage method:
if individual.document_type:
    rdf_entity.iao_document_label = individual.document_title
    if individual.document_section:
        rdf_entity.iao_document_label += f" - Section {individual.document_section}"
```

**Impact**: ✅ Non-breaking - adds optional fields, existing extraction still works

---

### Step 2.2: Test Pass 1 Resources with IAO

**Test Case**: Case 10, Facts section

**Expected Results**:
- Existing Resources still extracted (backwards compatible)
- NEW: Resources that are documents have `iao_document_label` populated
- Example: "NSPE Code of Ethics - Section II.4.a"

**Verification**:
```sql
SELECT entity_label, iao_document_label, extraction_type
FROM temporary_rdf_storage
WHERE case_id = 10 AND extraction_type = 'resources' AND section_type = 'facts';
```

---

## Phase 3: Pass 1 References Section - New Implementation

**Goal**: Implement step1e (References section) to extract cited authorities

**Duration**: 3-4 hours

### Step 3.1: Create References Extractor

**New File**: `/home/chris/onto/proethica/app/services/extraction/references_extractor.py`

**What it does**:
- Extracts NSPE Code sections from References section
- Marks them with `cited_by_role = 'Board of Ethical Review'`
- Creates IAO document part entities

**Key differences from Resources**:
- Focus on **specific code sections** (document parts)
- Emphasizes **citation** context (who cited it, why)
- Links to conclusions if possible

**Implementation**:
```python
class ReferencesExtractor:
    """Extract cited authorities from References section"""

    def extract_references(self, section_text: str, case_id: int) -> List[ResourceIndividual]:
        """
        Extract cited documents and document parts.

        Returns Resources with:
        - document_type = 'document_part'
        - cited_by_role = 'Board of Ethical Review'
        - Specific section references (II.4.a, III.4, etc.)
        """
        pass  # Implementation following DualResourcesExtractor pattern
```

---

### Step 3.2: Update step1e Route

**File**: `/home/chris/onto/proethica/app/routes/scenario_pipeline/step1.py`

**Current state**: Basic route exists, no extraction logic

**What to add**:
```python
def step1e(case_id):
    """
    Step 1e: Contextual Pass for References Section
    Extracts cited authorities (Resources marked as citations)
    """
    # Get References section
    # Run ReferencesExtractor
    # Store as Resources with cited_by_role='BER'
    # Display in step1e.html template
```

**Template**: Copy from `step1b.html` pattern, customize for References

---

### Step 3.3: Test Pass 1 References

**Test Case**: Case 10, References section

**Expected extraction**:
- NSPE Code Section II.4.a (document_part)
- NSPE Code Section III.4 (document_part)
- NSPE Code Section II.5.b (document_part)
- All marked with `cited_by_role = 'Board of Ethical Review'`

**Verification**:
```sql
SELECT entity_label, iao_document_label, cited_by_role
FROM temporary_rdf_storage
WHERE case_id = 10 AND section_type = 'references' AND extraction_type = 'resources';
```

---

## Phase 4: Pass 2 Resources & References

**Goal**: Apply same IAO pattern to Pass 2 (Normative Requirements)

**Duration**: 2-3 hours

### Step 4.1: Pass 2 Resources (Facts/Discussion/Questions/Conclusions)

**Current state**: No Resources extractor in Pass 2 (only extracts Principles, Obligations, Constraints, Capabilities)

**Decision needed**: Should Pass 2 also extract Resources?

**Options**:
1. **Skip**: Pass 2 doesn't extract Resources (only normative requirements)
2. **Add**: Create Pass 2 Resources extractor for consistency

**Recommendation**: **Skip for now** - Pass 2 focuses on normative concepts, not resources. Resources are Pass 1's job.

---

### Step 4.2: Pass 2 References Section (step2e)

**Goal**: Extract which NSPE Code provisions support the normative requirements

**What to extract**: Same as Pass 1 References
- Cited NSPE Code sections
- Mark with `cited_by_role = 'BER'`
- But context is different: linking to Principles/Obligations instead of roles/states

**Implementation**:
- Reuse `ReferencesExtractor` from Pass 1
- Same extraction logic
- Different context (normative vs contextual)

**File**: `/home/chris/onto/proethica/app/routes/scenario_pipeline/step2.py`

**Add**:
```python
def step2e_extract_references(case_id):
    """Extract References for Pass 2 (same as Pass 1 but different context)"""
    # Use same ReferencesExtractor
    # Store with step_number=2
```

---

## Phase 5: Pass 3 Resources & References

**Goal**: Plan for Pass 3 when we implement it

**Duration**: TBD (Pass 3 not yet implemented)

### Preliminary Design

**Pass 3 Resources** (Actions, Events):
- May need timeline/sequence documents
- Event logs, incident reports
- Same IAO document pattern

**Pass 3 References**:
- Same ReferencesExtractor
- Context: temporal dynamics

**Action**: Document in Pass 3 implementation plan when we get there

---

## Phase 6: Entity Review Display Updates

**Goal**: Show IAO document information in entity review pages

**Duration**: 1-2 hours

### Step 6.1: Update Pass 1 Entity Review Template

**File**: `/home/chris/onto/proethica/app/templates/scenarios/entity_review_pass1.html`

**What to add**: Display `iao_document_label` for Resources

```html
{% if entity.iao_document_label %}
    <div class="badge bg-info">
        <i class="bi bi-file-text"></i> {{ entity.iao_document_label }}
    </div>
{% endif %}

{% if entity.cited_by_role %}
    <div class="badge bg-success">
        <i class="bi bi-quote"></i> Cited by {{ entity.cited_by_role }}
    </div>
{% endif %}
```

### Step 6.2: Update Pass 2 Entity Review Template

**File**: `/home/chris/onto/proethica/app/templates/scenarios/entity_review_pass2.html`

**Same pattern**: Display document references for cited authorities

---

## Phase 7: Integration with Larger Plan

### How This Fits Into Multi-Section Extraction Plan

**Current Plan Status** (from MULTI_SECTION_EXTRACTION_PLAN.md):
- ✅ Pass 1 Facts, Discussion, Questions, Conclusions - COMPLETE
- ⏳ Pass 1 References (step1e) - **THIS PLAN ADDRESSES**
- ✅ Pass 2 Facts, Discussion, Questions, Conclusions - COMPLETE
- ⏳ Pass 2 References (step2e) - **THIS PLAN ADDRESSES**
- ⏳ Pass 3 - Not yet started

**Integration Points**:
1. **References sections complete multi-section extraction** for Passes 1 & 2
2. **IAO foundation** ready for Pass 3 when we implement it
3. **Documentation updated** in MULTI_SECTION_EXTRACTION_PLAN.md

---

## Testing Strategy

### Test Cases

**Case 10** (Revolving Door):
- ✅ Already has all sections
- ✅ References section has clear NSPE Code citations
- ✅ Good for testing IAO document extraction

**Test Sequence**:
1. Phase 1: Verify ontology update (query OntServe MCP)
2. Phase 2: Test Pass 1 Resources on Facts section
3. Phase 3: Test Pass 1 References section extraction
4. Phase 4: Test Pass 2 References section extraction
5. Phase 6: Verify entity review display

### Rollback Plan

**If something breaks**:
1. IAO properties are optional → can be removed without data loss
2. Database columns are nullable → can be dropped without affecting existing data
3. Extractors add data alongside existing → can disable new code paths

---

## Documentation Updates

### Files to Update

1. ✅ **RESOURCE_VS_REFERENCE_DESIGN.md** - Design rationale (done)
2. ✅ **UPPER_ONTOLOGY_GUIDANCE_RESOURCES.md** - IAO/PROV-O analysis (done)
3. ⏳ **MULTI_SECTION_EXTRACTION_PLAN.md** - Add IAO implementation details
4. ⏳ **CLAUDE.md** - Update current status with IAO completion
5. ⏳ **Implementation guide** - How to query IAO documents

---

## Timeline Estimate

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Foundation | 1-2 hours | None |
| Phase 2: Pass 1 Resources | 2-3 hours | Phase 1 |
| Phase 3: Pass 1 References | 3-4 hours | Phase 2 |
| Phase 4: Pass 2 References | 2-3 hours | Phase 3 |
| Phase 5: Pass 3 Planning | 1 hour | None (documentation only) |
| Phase 6: UI Updates | 1-2 hours | Phases 2-4 |
| Phase 7: Documentation | 1 hour | All phases |
| **TOTAL** | **11-16 hours** | ~2 days |

---

## Success Criteria

### Phase Completion Checklist

**Phase 1 Complete When**:
- ✅ proethica-core.ttl has IAO properties
- ✅ Database schema updated with IAO columns
- ✅ OntServe MCP serves new properties

**Phase 2 Complete When**:
- ✅ Pass 1 Resources extractor populates `iao_document_label`
- ✅ Test extraction on Case 10 Facts shows documents
- ✅ No regression in existing Resource extraction

**Phase 3 Complete When**:
- ✅ step1e extracts cited NSPE Code sections
- ✅ Citations marked with `cited_by_role = 'BER'`
- ✅ Entity review shows References section data

**Phase 4 Complete When**:
- ✅ step2e extracts References for Pass 2
- ✅ Same extraction logic as Pass 1
- ✅ Proper section isolation (Pass 2 References separate from Pass 1)

**Phase 6 Complete When**:
- ✅ Entity review displays IAO document badges
- ✅ "Cited by BER" badges show for References
- ✅ Visual distinction between case resources and cited authorities

---

## Next Steps

**Immediate**:
1. Review this plan
2. Approve approach
3. Start Phase 1 (Foundation)

**Questions to Resolve**:
1. Should Pass 2 extract Resources, or only References?
2. Do we want to link Conclusions→Citations automatically, or manually in a later phase?
3. Any specific IAO properties we want beyond what's planned?

---

**Ready to implement when approved!**
