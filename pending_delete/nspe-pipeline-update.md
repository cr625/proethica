# NSPE Pipeline Improvements Documentation

## Pipeline Execution Flow Analysis

After analyzing the case import process for NSPE cases, I've identified how ontology integration is working:

1. The `process_nspe_case.py` script handles the complete pipeline, which includes:
   - Scraping case content from NSPE URLs
   - Cleaning and structuring case content
   - Storing the case in the database
   - Applying semantic tagging
   - Integrating with the world ontology (optional)
   - **Adding ontology triples (engineering ethics and McLaren)**

2. The ontology integration in step 8 happens through the `integrate_ontologies_with_case()` function, which:
   - Adds engineering world entities to the case
   - Adds McLaren extensional definitions to the case

3. Triple storage pattern:
   - Triples are stored with `subject = "http://proethica.org/cases/{case_id}"`
   - Triples use `entity_type = 'document'`
   - `temporal_region_type` field is typically NULL (not set to the case ID)

## Issue with Entity Triple Queries

The main issue discovered is that the query code was expecting triples to be stored with `temporal_region_type = case_id`, but they're actually stored with the case ID in the subject URI pattern.

Original incorrect triple query pattern:
```python
cursor.execute("""
    SELECT id, subject, predicate, object_uri, object_literal, is_literal, 
           graph, triple_metadata, temporal_region_type
    FROM entity_triples
    WHERE entity_type = 'document' AND temporal_region_type = %s
    ORDER BY graph, predicate
""", (str(case_id),))
```

Corrected triple query pattern:
```python
case_uri = f"http://proethica.org/cases/{case_id}"
cursor.execute("""
    SELECT id, subject, predicate, object_uri, object_literal, is_literal, 
           graph, triple_metadata, temporal_region_type
    FROM entity_triples
    WHERE subject = %s AND entity_type = 'document'
    ORDER BY graph, predicate
""", (case_uri,))
```

## Testing Validation

The correct query approach successfully retrieves the 14 triples for case 188:
- 13 triples from the engineering-ethics ontology
- 1 triple from the mclaren-extensional-definitions ontology

## Recommendations

1. Update all triple query code (such as in `app/routes/cases.py`) to use the subject URI pattern for finding case-related triples.

2. Document this pattern in the codebase for future developers.

3. Consider adding a database migration to populate the `temporal_region_type` field with the case ID for consistency, though this isn't strictly necessary if all query code is updated.

4. Update the `EntityTripleService` code to ensure triples stored by that service consistently use the same pattern as the ontology integration code.
