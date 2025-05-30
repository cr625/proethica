# Guideline Triple Storage Strategy

## Overview
This document outlines the optimal approach for storing and managing triples extracted from ethical guidelines, balancing ontology integrity with practical queryability.

## Current Issues
1. No duplicate detection - same concepts can be extracted multiple times
2. All triples stored in database regardless of value
3. No synchronization between guideline triples and ontology files
4. Low-value triples (mentionsTerm, type, label) clutter the system

## Proposed Tiered Storage Strategy

### Tier 1: Core Ontology (engineering-ethics.ttl)
**What goes here:** High-value, universally applicable triples
- Fundamental ethical principles (e.g., Public Safety, Professional Integrity)
- Core role definitions (e.g., Engineer, Client, Regulatory Authority)
- Essential capabilities and obligations
- Well-established domain concepts

**Criteria:**
- Triple has high semantic value (defines, requires, emphasizes, implements)
- Concept appears in multiple guidelines or cases
- Represents established domain knowledge
- Has been reviewed and approved by domain experts

**Process:**
1. Extract and review triples from guidelines
2. Identify high-value, recurring concepts
3. Add to engineering-ethics.ttl with proper documentation
4. Sync to database via existing script

### Tier 2: Guideline-Specific Ontology (Optional)
**What goes here:** Guideline-specific interpretations and extensions
- File: `engineering-ethics-{guideline-name}.ttl`
- Imports: engineering-ethics.ttl
- Contains: Medium-value triples specific to that guideline
- Use case: When a guideline introduces specialized concepts

**Criteria:**
- Medium semantic value
- Specific to one guideline's interpretation
- Extends but doesn't contradict core ontology
- May be promoted to Tier 1 if adopted widely

### Tier 3: Database Only (EntityTriple)
**What goes here:** Low-value and experimental triples
- mentionsTerm relationships (for tracking coverage)
- Experimental relationships being evaluated
- Triples pending review for promotion
- Guideline-specific annotations

**Criteria:**
- Low semantic value or high uncertainty
- Useful for search/analysis but not ontology modeling
- Temporary or experimental relationships
- Metadata about guideline coverage

## Implementation Plan

### Phase 1: Duplicate Detection
```python
def check_existing_triple(subject_uri, predicate, object_value):
    """Check if triple exists in ontology or database"""
    # 1. Check loaded ontology graph
    if ontology_graph.contains((subject_uri, predicate, object_value)):
        return "ontology"
    
    # 2. Check database
    existing = EntityTriple.query.filter_by(
        subject=subject_uri,
        predicate=predicate,
        object_literal=object_value if is_literal else None,
        object_uri=object_value if not is_literal else None
    ).first()
    
    return "database" if existing else None
```

### Phase 2: Value-Based Storage
```python
def store_triple_by_value(triple, value_category):
    """Store triple based on its value category"""
    if value_category == "high":
        # Queue for ontology addition (requires review)
        queue_for_ontology_review(triple)
        # Also store in database for immediate use
        store_in_database(triple, metadata={"candidate_for": "core_ontology"})
    
    elif value_category == "medium":
        # Store in database with potential for guideline-specific ontology
        store_in_database(triple, metadata={"value": "medium"})
    
    else:  # low value
        # Only store in database if needed for search/analysis
        if should_store_low_value(triple):
            store_in_database(triple, metadata={"value": "low", "retention": "temporary"})
```

### Phase 3: Synchronization Process
1. **Ontology → Database**: Existing sync script (keep as-is)
2. **Database → Ontology**: New review process
   - Weekly/monthly review of high-value candidates
   - Expert approval required
   - Batch updates to engineering-ethics.ttl
   - Version control with meaningful commits

### Phase 4: UI Enhancements
1. **Show Triple Origin**:
   - Icon indicating if triple exists in core ontology
   - Different icon for guideline-specific triples
   - Tooltip showing source (ontology file, guideline, etc.)

2. **Review Queue**:
   - Dashboard for high-value triple candidates
   - Bulk approval/rejection interface
   - Export approved triples to TTL format

## Benefits
1. **Ontology Integrity**: Core ontology remains clean and authoritative
2. **Flexibility**: Low-value triples available for search without cluttering ontology
3. **Scalability**: Can handle many guidelines without ontology bloat
4. **Traceability**: Clear path from extraction to ontology inclusion
5. **Performance**: Reduced triple count in core ontology

## Migration Strategy
1. Analyze existing guideline triples by value
2. Move high-value approved triples to engineering-ethics.ttl
3. Mark medium-value triples for retention in database
4. Remove or archive low-value triples (with user confirmation)
5. Implement duplicate detection going forward

## Example Value Classifications

### High Value (→ Core Ontology)
```turtle
proethica:PublicSafety proethica:isPrimaryObligationOf proethica:ProfessionalEngineer .
proethica:ConfidentialityObligation proethica:requiresCapability proethica:InformationManagement .
```

### Medium Value (→ Database/Guideline Ontology)
```turtle
guideline:Section2_1 proethica:interpretsPrinciple proethica:PublicSafety .
guideline:CaseStudy3 proethica:illustratesConcept proethica:ConflictOfInterest .
```

### Low Value (→ Database Only or Discard)
```turtle
guideline:Paragraph5 proethica:mentionsTerm "engineer" .
proethica:PublicSafety rdf:type proethica:Principle .  # If already in ontology
```

## Next Steps
1. Create script to analyze current triple values
2. Implement duplicate detection in guideline processing
3. Add triple review interface to admin panel
4. Update sync scripts for bidirectional flow
5. Document the review/approval process