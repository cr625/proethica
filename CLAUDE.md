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

## 2025-05-12: Implementing Guidelines Feature with Ontology Entity Integration

### Background

The application has a concept of Worlds, with the Engineering World (ID: 1) being the primary world defined so far. Each world has RDF triples associated with it from the engineering-ethics ontology. This implementation enhances the guidelines feature to not just allow uploading guidelines, but to analyze them for concepts that can be represented as entities in the engineering-ethics ontology.

### Implementation Approach

A two-phase approach was implemented for associating RDF triples with guidelines:
1. Upload phase: Users upload guidelines via file, URL, or direct text entry
2. Analysis phase: The system evaluates the content using LLM-based analysis to extract concepts and match them to ontology entities

### Components Created/Modified

1. **Database Schema Updates**:
   - Created a new `guidelines` table to store guideline documents
   - Updated the `entity_triples` table to link triples to guidelines
   - Added extra fields for triple labeling and provenance

2. **Model Updates**:
   - Enhanced `World` model with a relationship to `Guideline` model
   - Created `Guideline` model to store and manage guideline documents

3. **Services**:
   - Created `GuidelineAnalysisService` to handle LLM-based analysis of guidelines
   - Implemented methods for concept extraction and ontology entity matching

4. **MCP Server Integration**:
   - Created guideline analysis module for the MCP server
   - Implemented endpoints for guideline analysis using LLM processing

5. **Templates and UI**:
   - Created `guideline_concepts_review.html` for reviewing extracted concepts
   - Enhanced existing guidelines interface for better user experience

6. **Routes**:
   - Updated `worlds.py` routes to handle guideline upload, analysis, and concept selection

### Key Features

1. **Document Processing**:
   - Support for multiple input methods (file upload, URL, direct text)
   - Handling of various document formats (PDF, DOCX, TXT, HTML)

2. **Concept Extraction**:
   - LLM-based extraction of ontology-relevant concepts from guidelines
   - Classification of concepts by type (principle, obligation, action, etc.)
   - Relevance scoring for extracted concepts

3. **Entity Matching**:
   - Matching extracted concepts to existing ontology entities
   - Calculation of match confidence scores
   - Support for creating new entities when no matches exist

4. **Concept Review Interface**:
   - User-friendly interface for reviewing extracted concepts
   - Selection of concepts to include in the ontology
   - Preview of matched ontology entities

5. **RDF Triple Generation**:
   - Creation of RDF triples for selected concepts
   - Association of triples with both the guideline and the world
   - Storage with proper labeling for better browsing

### Recent Template Fixes (2025-05-12)

Fixed parameter naming inconsistencies in guideline-related templates to ensure they work correctly with route definitions:

1. **Templates Updated**:
   - `guidelines.html`: Changed `world_id` to `id` in all URL routes
   - `guideline_content.html`: Changed `world_id`/`guideline_id` to `id`/`document_id` for all routes
   - `guideline_concepts_review.html`: Changed `world_id` to `id` for the save concepts route

2. **Workflow Improvements**:
   - Ensured consistent URL parameter naming convention across all templates
   - Fixed form actions to correctly submit to the proper endpoints
   - Updated navigation links for proper guideline browsing experience

3. **Additional Fixes (2025-05-12 Evening)**:
   - Fixed the breadcrumb navigation in the `guideline_concepts_review.html` template to handle both direct parameters (world_id, document_id) and object properties (world.id, guideline.id) for backward compatibility
   - Removed references to non-existent routes (`worlds.edit_guideline` and `worlds.export_guideline_triples`)
   - Updated the progress documentation in `guidelines_progress.md` with detailed information about all template fixes
   - Removed all references to `csrf_token()` from guidelines-related templates to fix the `jinja2.exceptions.UndefinedError: 'csrf_token' is undefined` error (since Flask-WTF's CSRFProtect is not initialized in the application)
   - Added default values for undefined variables in guideline_content.html template:
     * Added `|default(0)` filter to `triple_count` and `concept_count` variables
     * Added existence check for `triples` list with `triples is defined and triples` in conditional statements
     * Fixed the `jinja2.exceptions.UndefinedError: 'triple_count' is undefined` error that occurred when viewing guideline details

These fixes ensure the seamless flow of the guideline upload, analysis, and concept extraction pipeline. All guideline-related templates now use consistent parameter naming and URL generation patterns, which resolved previous routing issues.

### Future Enhancements

1. Improve concept extraction quality with refined LLM prompts
2. Enhance matching algorithm for better ontology entity alignment
3. Add support for more complex relationships between concepts
4. Implement versioning for guidelines to track changes over time

### Documentation

All implementation details and progress are tracked in `guidelines_progress.md`, which outlines:
- Implementation phases (current and planned)
- Technical details of database changes and workflow
- Current limitations and known issues
- Next steps for further development
