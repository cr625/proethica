# Guideline Triples Deduplication and Storage Strategy

## Overview

This document outlines the implementation of duplicate detection and storage strategy for guideline triples. The goal is to prevent duplicate triples while handling versioning and conflicts intelligently.

## Storage Strategy

### 1. Triple Versioning Approach

We implement versioning at the triple level rather than guideline level to allow for fine-grained tracking:

```sql
-- Enhanced EntityTriple table with versioning support
ALTER TABLE entity_triples ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE entity_triples ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE entity_triples ADD COLUMN superseded_by INTEGER REFERENCES entity_triples(id);
ALTER TABLE entity_triples ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
```

### 2. Duplicate Detection Levels

Our implementation provides three levels of duplicate detection:

1. **Exact Match**: Same subject, predicate, and object
2. **Equivalent Match**: Same semantic content but different URIs (namespace variations)
3. **Similar Match**: Related concepts with high semantic similarity

### 3. Conflict Resolution Strategy

When the same term exists but with different attributes:

#### Case 1: Same URI, Different Labels
```
Existing: <URI> rdfs:label "Engineer" 
New:      <URI> rdfs:label "Professional Engineer"
```
**Resolution**: Create new version, mark old as superseded

#### Case 2: Same Label, Different Categories
```
Existing: <URI> rdf:type "Role"
New:      <URI> rdf:type "Capability" 
```
**Resolution**: User prompt for conflict resolution

#### Case 3: Different Confidence Scores
```
Existing: <URI> proethica:hasConfidence "0.8"
New:      <URI> proethica:hasConfidence "0.9"
```
**Resolution**: Keep higher confidence, update metadata

## Implementation Components

### 1. Enhanced Triple Storage

```python
class VersionedTripleStore:
    def store_triple(self, triple_data, guideline_id, conflict_resolution='prompt'):
        """
        Store a triple with duplicate detection and conflict resolution.
        
        Args:
            triple_data: Dictionary with triple information
            guideline_id: Source guideline ID
            conflict_resolution: 'prompt', 'merge', 'skip', 'version'
        
        Returns:
            StorageResult with status and actions taken
        """
        # Check for duplicates
        duplicate_result = self.duplicate_service.check_duplicate_with_details(
            triple_data['subject'],
            triple_data['predicate'],
            triple_data.get('object_uri', triple_data.get('object_literal')),
            triple_data.get('is_literal', False),
            exclude_guideline_id=guideline_id
        )
        
        if duplicate_result['is_duplicate']:
            return self._handle_duplicate(triple_data, duplicate_result, conflict_resolution)
        else:
            return self._store_new_triple(triple_data, guideline_id)
```

### 2. Conflict Resolution UI

Create an interactive conflict resolution interface:

```html
<!-- Conflict Resolution Modal -->
<div class="modal" id="conflictModal">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5>Resolve Triple Conflict</h5>
            </div>
            <div class="modal-body">
                <div class="row">
                    <div class="col-6">
                        <h6>Existing Triple</h6>
                        <div class="card">
                            <div class="card-body">
                                <strong>Subject:</strong> {{ existing.subject_label }}<br>
                                <strong>Predicate:</strong> {{ existing.predicate_label }}<br>
                                <strong>Object:</strong> {{ existing.object_label }}<br>
                                <small class="text-muted">From: {{ existing.source_guideline }}</small>
                            </div>
                        </div>
                    </div>
                    <div class="col-6">
                        <h6>New Triple</h6>
                        <div class="card">
                            <div class="card-body">
                                <strong>Subject:</strong> {{ new.subject_label }}<br>
                                <strong>Predicate:</strong> {{ new.predicate_label }}<br>
                                <strong>Object:</strong> {{ new.object_label }}<br>
                                <small class="text-muted">From: Current guideline</small>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="mt-3">
                    <h6>Resolution Options:</h6>
                    <div class="form-check">
                        <input type="radio" name="resolution" value="keep_existing" class="form-check-input">
                        <label>Keep existing, skip new</label>
                    </div>
                    <div class="form-check">
                        <input type="radio" name="resolution" value="replace" class="form-check-input">
                        <label>Replace existing with new</label>
                    </div>
                    <div class="form-check">
                        <input type="radio" name="resolution" value="version" class="form-check-input">
                        <label>Create new version</label>
                    </div>
                    <div class="form-check">
                        <input type="radio" name="resolution" value="merge" class="form-check-input">
                        <label>Merge (combine metadata)</label>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-primary" onclick="resolveConflict()">Apply Resolution</button>
            </div>
        </div>
    </div>
</div>
```

### 3. Enhanced UI Indicators

The triples review template now shows:

- **Green "New" badge**: Triple is completely new
- **Yellow "In Ontology" badge**: Exact match found in core ontology
- **Blue "In Database" badge**: Exact match found in database
- **Star icon**: High-value semantic relationship
- **Circle icon**: Low-value relationship (mentions, basic properties)

### 4. Batch Processing Strategy

For guidelines with many triples:

1. **Pre-process**: Run duplicate detection on all triples
2. **Categorize**: Group by duplicate status and conflict type
3. **Auto-resolve**: Apply rules for simple cases (exact duplicates → skip)
4. **User review**: Present conflicts requiring manual resolution
5. **Batch save**: Store all resolved triples in single transaction

## Configuration Options

### Default Behaviors

```python
DEDUPLICATION_CONFIG = {
    'exact_duplicates': 'skip',           # Skip exact matches
    'ontology_duplicates': 'skip',        # Skip if in core ontology
    'equivalent_duplicates': 'prompt',    # Ask user for equivalent URIs
    'similar_duplicates': 'store',        # Store similar concepts as new
    'confidence_threshold': 0.7,          # Minimum confidence for similarity
    'auto_merge_metadata': True,          # Merge compatible metadata
    'preserve_provenance': True           # Keep source information
}
```

### Per-Guideline Settings

Allow customization per guideline type:
- NSPE codes: More conservative (skip more duplicates)
- Internal guidelines: More permissive (allow variations)
- Experimental guidelines: Store everything for analysis

## Testing Strategy

### 1. Test Cases

Create comprehensive test cases:

```python
def test_exact_duplicate_detection():
    """Test exact triple duplicate detection."""
    assert detect_duplicate(triple1, triple1) == True

def test_namespace_variation_detection():
    """Test detection of equivalent URIs with different namespaces."""
    triple1 = create_triple("proethica:Engineer", "rdf:type", "proethica:Role")
    triple2 = create_triple("ethics:Engineer", "rdf:type", "ethics:Role")
    assert detect_equivalent(triple1, triple2) == True

def test_conflict_resolution():
    """Test conflict resolution strategies."""
    # ... test different conflict scenarios
```

### 2. Performance Testing

- Load testing with 10,000+ triples
- Memory usage monitoring during duplicate detection
- Database query optimization for triple lookups

## Migration Strategy

### Phase 1: Implement Detection
- Deploy duplicate detection service
- Add UI indicators
- No automatic actions (review-only mode)

### Phase 2: Add Storage Logic
- Implement versioning
- Add conflict resolution UI
- Enable automatic handling of simple cases

### Phase 3: Optimize Performance
- Add database indexes
- Implement caching
- Optimize for large-scale processing

## Monitoring and Analytics

Track metrics:
- Duplicate detection accuracy
- User resolution choices
- Performance metrics
- Storage efficiency improvements

This strategy ensures data quality while maintaining usability and providing clear visibility into the deduplication process.