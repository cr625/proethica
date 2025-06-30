# Database Schema Extension Plan for Type Mapping

## Current State Analysis

### Existing Structure (39 tables)
- ✅ **entity_triples**: Robust table with JSONB metadata support
- ✅ **guidelines**: Already tracks concepts in metadata
- ✅ **users**: Exists for tracking reviewers
- ❌ **Problem confirmed**: All concepts forced to "is a State"

### Sample Data Issues
```
Public Safety Paramount --[is a]--> State  ❌ Should be Principle
Professional Competence --[is a]--> State  ❌ Should be Principle
```

## Schema Extension Strategy

### Option 1: Minimal Extensions (RECOMMENDED)
**Extend existing tables + add 3 new tables**

#### 1.1 Extend entity_triples
```sql
ALTER TABLE entity_triples ADD COLUMN original_llm_type VARCHAR(255);
ALTER TABLE entity_triples ADD COLUMN type_mapping_confidence FLOAT;
ALTER TABLE entity_triples ADD COLUMN needs_type_review BOOLEAN DEFAULT false;
ALTER TABLE entity_triples ADD COLUMN mapping_justification TEXT;
```

#### 1.2 New Tables
```sql
-- Store pending concept types for review
CREATE TABLE pending_concept_types (
    id SERIAL PRIMARY KEY,
    suggested_type VARCHAR(255) NOT NULL,
    suggested_description TEXT,
    suggested_parent_type VARCHAR(255),
    source_guideline_id INTEGER REFERENCES guidelines(id),
    example_concepts JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending',  -- pending, approved, rejected
    reviewer_notes TEXT,
    approved_by INTEGER REFERENCES users(id),
    approved_at TIMESTAMP
);

-- Store approved custom types
CREATE TABLE custom_concept_types (
    id SERIAL PRIMARY KEY,
    type_name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    parent_type VARCHAR(255),
    ontology_uri VARCHAR(500),
    created_from_pending_id INTEGER REFERENCES pending_concept_types(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Track type mapping decisions
CREATE TABLE concept_type_mappings (
    id SERIAL PRIMARY KEY,
    original_llm_type VARCHAR(255),
    mapped_to_type VARCHAR(255),
    mapping_confidence FLOAT,
    is_automatic BOOLEAN DEFAULT true,
    reviewed_by INTEGER REFERENCES users(id),
    review_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Option 2: Clean Slate Redesign
**Create entirely new type management system** (More disruptive)

### Recommendation: Option 1

**Why?**
- ✅ Preserves existing data and relationships
- ✅ Leverages robust JSONB metadata system
- ✅ Minimal disruption to existing routes/templates
- ✅ Can migrate existing "State" overassignments gradually

## Implementation Plan

### Phase 2A: Schema Extensions
1. **Add columns to entity_triples** (backward compatible)
2. **Create 3 new tables** (isolated, no impact on existing system)
3. **Add indexes** for performance

### Phase 2B: Data Migration  
1. **Preserve existing data** (all current triples stay intact)
2. **Add mapping metadata** to existing concepts
3. **Flag problematic "State" assignments** for review

### Phase 2C: Model Updates
1. **Extend EntityTriple model** with new fields
2. **Create new model classes** for type management
3. **Update relationships** and validation

## Compatibility Strategy

### Backward Compatibility
- ✅ **All existing queries work unchanged**
- ✅ **Existing templates continue functioning**
- ✅ **New fields are optional/nullable**

### Forward Compatibility
- ✅ **Gradual adoption** of new type mapping
- ✅ **Fallback to old behavior** if mapping fails  
- ✅ **Side-by-side comparison** of old vs new assignments

## Migration Safety

### Data Safety
- ✅ **No data deletion** (only additions)
- ✅ **Rollback capability** (new columns can be dropped)
- ✅ **Backup strategy** before any changes

### Testing Strategy
- ✅ **Test on development database first**
- ✅ **Validate with sample data**
- ✅ **Performance testing** with new indexes

## Expected Benefits

### Immediate
- 🎯 **Eliminate "State" over-assignment**
- 🎯 **Preserve LLM semantic insights**
- 🎯 **Enable human review workflow**

### Long-term
- 🎯 **Ontology expansion capability**
- 🎯 **Type mapping audit trail**
- 🎯 **Improved concept accuracy**

## Risk Assessment

### Low Risk
- ✅ Non-destructive changes
- ✅ Gradual adoption possible
- ✅ Rollback capability

### Mitigation
- ✅ Database backup before migration
- ✅ Feature flags for new functionality
- ✅ Comprehensive testing

---

**Next Step**: Create migration scripts for Option 1 (Minimal Extensions)