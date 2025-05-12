# ProEthica Project Work Log

[TOC]

## 2025-05-11: Fixing NSPE Case Import Pipeline for Ontology Triples

### Issue
When importing a new NSPE case (case 187) from URL https://www.nspe.org/career-growth/ethics/board-ethical-review-cases/acknowledging-errors-design, the case data was imported properly but the query to fetch ontology triples was not finding the triples despite them being correctly added to the database.

### Investigation

1. Created debugging tools to examine entity triples in the database:
   - `check_database_triples.py` - Low-level inspection of database structure and triple storage patterns
   - `fix_entity_triples_query.py` - Updated query tool using correct subject URI pattern

2. Discovered that triples were being stored with:
   - `subject = "http://proethica.org/cases/{case_id}"`
   - `entity_type = 'document'`
   - `temporal_region_type = NULL` (not set to the case ID as expected)

3. The query code in `correct_query_triples.py` was looking for triples using the pattern:
   ```python
   cursor.execute("""
       SELECT id, subject, predicate, object_uri, object_literal, is_literal, 
              graph, triple_metadata, temporal_region_type
       FROM entity_triples
       WHERE entity_type = 'document' AND temporal_region_type = %s
       ORDER BY graph, predicate
   """, (str(case_id),))
   ```

4. Updated the query to use the correct pattern:
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

5. Verified that case 188 had 14 triples (13 from engineering-ethics ontology and 1 from mclaren-extensional-definitions).

### Findings

The pipeline itself is correctly adding both engineering world entity triples and McLaren extensional definition triples to imported cases. The issue was in how these triples were being queried.

The ontology integration happens in step 8 of the NSPE case processing pipeline through the `integrate_ontologies_with_case()` function:
   - Adds engineering world entities to the case via `add_engineering_world_entities()`
   - Adds McLaren extensional definitions to the case via `add_mclaren_extensional_definitions()`

### Documentation and Fixes

1. Created a comprehensive document `nspe-pipeline-update.md` describing:
   - The pipeline flow
   - The triple storage pattern
   - The issue with the entity triple queries
   - Recommendations for fixing and improving the system

2. Fixed the query script `correct_query_triples.py` to properly query triples.

### Next Steps

1. Update all triple query code (such as in `app/routes/cases.py`) to use the subject URI pattern for finding case-related triples.

2. Consider adding a database migration to populate the `temporal_region_type` field with the case ID for consistency.

3. Update the `EntityTripleService` code to ensure triples stored by that service consistently use the same pattern as the ontology integration code.

### Conclusion

The NSPE case import pipeline is working correctly for importing ontology triples. The issue was in the query method. By updating the query to use the correct pattern, we can now correctly retrieve the engineering ethics and McLaren ontology triples for cases.

## 2025-05-12: Enhancing Guidelines Feature to Support RDF Triple Association

### Background

The application has a concept of Worlds, with the Engineering World (ID: 1) being the primary world. Each world has RDF triples associated with it from various ontologies. The goal was to enhance the existing guidelines upload feature to better link guidelines to ethical concepts in the engineering-ethics ontology.

### Implementation

1. Enhanced the `GuidelineAnalysisService` to support additional entity types:
   - Added support for "event" and "capability" entity types alongside the existing types (principle, obligation, role, action, resource, condition)
   - Updated the LLM prompt to extract these new entity types from guideline content
   - Modified triple creation methods to handle these new types
   
2. Verified that the existing workflow for guidelines is functional:
   - Uploading guidelines via file, URL, or pasted text
   - Processing content with LLM to extract concepts
   - Matching concepts to existing ontology entities
   - Creating and storing RDF triples for selected concepts

3. Created comprehensive documentation in `guidelines_progress.md` that:
   - Outlined the implementation phases
   - Tracked completed features and pending enhancements
   - Documented technical details of the implementation
   - Provided clear next steps for future development

### Testing

Testing confirmed that:
- The guideline upload interface works correctly
- The LLM integration successfully extracts concepts from guidelines
- The concept review page displays extracted concepts with their matched entities
- The system can create and store RDF triples for selected concepts

### Next Steps

Future enhancements will focus on:
1. Improving the visual distinction between new concepts and matches to existing ontology entities
2. Enhancing the triple visualization and browsing experience
3. Comprehensive testing with various document formats
4. Performance optimizations for larger documents

### Documentation

All changes and progress are documented in `guidelines_progress.md` with details on implementation phases, technical notes, and next steps.
