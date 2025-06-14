# Implementing Duplicate Detection in Guideline Processing

## Integration Points

### 1. Update GuidelineAnalysisService

In `app/services/guideline_analysis_service.py`, modify the `generate_triples` method:

```python
from app.services.triple_duplicate_detection_service import get_duplicate_detection_service

def generate_triples(self, concepts, guideline_id=None):
    """Generate RDF triples with duplicate detection."""
    
    # Get duplicate detection service
    duplicate_service = get_duplicate_detection_service()
    
    # Generate triples as before
    raw_triples = self._generate_raw_triples(concepts)
    
    # Filter duplicates
    unique_triples, duplicate_triples = duplicate_service.filter_duplicate_triples(
        raw_triples, 
        exclude_guideline_id=guideline_id
    )
    
    # Log duplicates found
    if duplicate_triples:
        logger.info(f"Found {len(duplicate_triples)} duplicate triples")
        for dup in duplicate_triples[:5]:  # Log first 5
            logger.debug(f"Duplicate: {dup['duplicate_info']['details']}")
    
    # Return unique triples with duplicate info
    return {
        'triples': unique_triples,
        'duplicates_found': len(duplicate_triples),
        'duplicate_details': duplicate_triples
    }
```

### 2. Update UI to Show Duplicate Status

In `manage_guideline_triples.html`, add duplicate indicators:

```html
<!-- Add to triple row -->
{% if triple.duplicate_check_result %}
<span class="badge bg-info" title="{{ triple.duplicate_check_result.details }}">
    {% if triple.duplicate_check_result.in_ontology %}
        <i class="fas fa-book"></i> In Ontology
    {% elif triple.duplicate_check_result.in_database %}
        <i class="fas fa-database"></i> In Database
    {% endif %}
</span>
{% endif %}
```

### 3. Add Batch Duplicate Check Command

Create `scripts/check_guideline_duplicates.py`:

```python
#!/usr/bin/env python3
"""Check all guideline triples for duplicates."""

from app.services.triple_duplicate_detection_service import get_duplicate_detection_service
from app.models.entity_triple import EntityTriple

def check_all_duplicates():
    service = get_duplicate_detection_service()
    
    # Get all guideline triples
    triples = EntityTriple.query.filter_by(entity_type='guideline_concept').all()
    
    duplicates = []
    for triple in triples:
        result = service.check_duplicate_with_details(
            triple.subject,
            triple.predicate,
            triple.object_literal if triple.is_literal else triple.object_uri,
            triple.is_literal
        )
        
        if result['is_duplicate']:
            duplicates.append((triple, result))
    
    print(f"Found {len(duplicates)} duplicate triples out of {len(triples)}")
    return duplicates
```

### 4. Update Triple Storage to Check First

In routes that save triples:

```python
@worlds_bp.route('/save_triples', methods=['POST'])
def save_guideline_triples():
    duplicate_service = get_duplicate_detection_service()
    
    for triple_data in triples_to_save:
        # Check for duplicate first
        check_result = duplicate_service.check_duplicate_with_details(
            triple_data['subject'],
            triple_data['predicate'],
            triple_data['object'],
            triple_data.get('is_literal', False)
        )
        
        if not check_result['is_duplicate']:
            # Create new triple
            triple = EntityTriple(...)
            db.session.add(triple)
        else:
            # Log or handle duplicate
            logger.info(f"Skipping duplicate: {check_result['details']}")
```

## Testing the Implementation

1. **Test with Known Duplicates**:
   ```bash
   python scripts/analyze_guideline_triples.py --guideline 190
   ```

2. **Check Ontology Loading**:
   ```python
   from app.services.triple_duplicate_detection_service import get_duplicate_detection_service
   service = get_duplicate_detection_service()
   print(f"Loaded ontologies: {service.loaded_ontologies}")
   print(f"Total triples in memory: {len(service.ontology_graph)}")
   ```

3. **Test Equivalent Concept Detection**:
   ```python
   equivalents = service.find_equivalent_concepts('http://proethica.org/ontology/PublicSafety')
   print(f"Equivalent URIs: {equivalents}")
   ```

## Performance Considerations

1. **Ontology Loading**: Done once at service initialization
2. **Memory Usage**: ~10-50MB for typical ontologies
3. **Query Performance**: Add indexes if needed:
   ```sql
   CREATE INDEX idx_entity_triple_lookup 
   ON entity_triples(subject, predicate, object_uri, object_literal, is_literal);
   ```

## Next Steps

1. Run duplicate analysis on existing data
2. Clean up identified duplicates
3. Update guideline processing pipeline
4. Add UI indicators for duplicate status
5. Create admin interface for managing duplicates