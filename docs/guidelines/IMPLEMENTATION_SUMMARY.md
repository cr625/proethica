# Guideline Triple Management - Implementation Summary

## Overview
This document summarizes the investigation and implementation plan for optimal guideline triple storage and management.

## Key Findings

### 1. Current State
- **No duplicate detection** - System creates duplicate triples without checking
- **All triples stored in database** - No distinction by value
- **UI already classifies triples** - High/Medium/Low value categories exist
- **TTL files are canonical** - Database is synced from files

### 2. Triple Value Categories (Already Implemented in UI)
- **High Value**: defines, requires, emphasizes, implements, alignsWith
- **Medium Value**: Other semantic relationships  
- **Low Value**: mentionsTerm, type, label (duplicate searchable info)

## Recommended Implementation

### Phase 1: Duplicate Detection (Priority: HIGH)
**Implementation**: `/app/services/triple_duplicate_detection_service.py`
- Checks against ontology files and database
- Detects equivalent concepts across namespaces
- Can be integrated into guideline processing pipeline

**Usage**:
```python
from app.services.triple_duplicate_detection_service import get_duplicate_detection_service
service = get_duplicate_detection_service()
unique, duplicates = service.filter_duplicate_triples(new_triples)
```

### Phase 2: Triple Analysis Tool (Priority: MEDIUM)
**Implementation**: `/scripts/analyze_guideline_triples.py`
- Analyzes existing triples by value and duplicates
- Generates ontology candidate files
- Helps clean up existing data

**Usage**:
```bash
python scripts/analyze_guideline_triples.py --guideline 190 --export
```

### Phase 3: Tiered Storage Strategy (Priority: HIGH)
**Documentation**: `/docs/guidelines/guideline_triple_storage_strategy.md`
- **Tier 1**: High-value → engineering-ethics.ttl (with review)
- **Tier 2**: Medium-value → Database (or guideline-specific TTL)
- **Tier 3**: Low-value → Database only (or discard)

### Phase 4: UI Enhancements (Priority: LOW)
**Implementation**: `/app/static/js/manage_triples_enhancements.js`
- Visual indicators for triple origin
- Value-based filtering
- Export high-value triples to TTL

**Integration**: Add to manage_guideline_triples.html:
```html
<script src="{{ url_for('static', filename='js/manage_triples_enhancements.js') }}"></script>
```

## Quick Start Implementation

### 1. Enable Duplicate Detection
In `guideline_analysis_service.py`:
```python
def generate_triples(self, concepts, guideline_id=None):
    # Existing triple generation...
    
    # Add duplicate detection
    from app.services.triple_duplicate_detection_service import get_duplicate_detection_service
    service = get_duplicate_detection_service()
    unique_triples, _ = service.filter_duplicate_triples(raw_triples, guideline_id)
    
    return unique_triples
```

### 2. Add Triple Origin Tracking
When saving triples, add metadata:
```python
triple.triple_metadata = {
    'value_classification': service.classify_triple_value(predicate),
    'source': 'guideline_extraction',
    'guideline_id': guideline_id
}
```

### 3. Create Review Process
Add admin route for reviewing high-value candidates:
```python
@admin_bp.route('/ontology/review_candidates')
def review_ontology_candidates():
    high_value_triples = EntityTriple.query.filter(
        EntityTriple.triple_metadata['value_classification'] == 'high',
        EntityTriple.triple_metadata['reviewed'] == None
    ).all()
    return render_template('admin/review_candidates.html', triples=high_value_triples)
```

## Benefits
1. **Prevents duplicate triples** across guidelines and ontologies
2. **Maintains ontology quality** by selective inclusion
3. **Improves performance** with fewer redundant triples
4. **Provides traceability** from extraction to ontology
5. **Enables intelligent search** without clutter

## Next Actions
1. **Immediate**: Integrate duplicate detection service
2. **Short-term**: Run analysis on existing triples
3. **Medium-term**: Implement review workflow
4. **Long-term**: Automate promotion of validated triples

## Testing
```bash
# Test duplicate detection
python -c "from app.services.triple_duplicate_detection_service import get_duplicate_detection_service; s = get_duplicate_detection_service(); print(f'Loaded: {s.loaded_ontologies}')"

# Analyze existing data
python scripts/analyze_guideline_triples.py --world 1

# Check for duplicates in specific guideline
python scripts/analyze_guideline_triples.py --guideline 190
```