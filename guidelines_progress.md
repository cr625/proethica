# Guidelines Integration Progress Tracker

## Overview
This document tracks the progress of implementing the guidelines integration feature for ProEthica. The feature allows users to upload ethical guidelines associated with a world, analyze the content to extract ethical concepts, and convert these into RDF triples linked to the world's knowledge graph.

## Feature Implementation Plan

### Phase 1: Basic Guidelines Upload and Display
- [x] Fix routing in guideline templates
- [x] Ensure proper parameter naming between routes and templates
- [x] Fix form submissions for guideline analysis
- [x] Test guideline upload functionality
- [x] Test guideline display

### Phase 2: Guideline Analysis Pipeline
- [x] Fix guideline analysis service integration
- [x] Ensure LLM-based concept extraction works properly
- [x] Test matching extracted concepts to ontology entities
- [x] Fix the review page for concept selection (UI)
- [x] Ensure proper saving of selected concepts as triples

### Phase 3: Guideline-Ontology Integration (In Progress)
- [ ] Enhance triple generation to better connect with existing ontology
- [ ] Improve UI for displaying matched ontology concepts vs. new concepts
- [ ] Add visualization of created triples after concept saving
- [ ] Add ability to edit/delete concepts after creation

### Phase 4: Guideline Search and Retrieval
- [ ] Implement search functionality across guidelines
- [ ] Add ability to filter guidelines by concepts
- [ ] Connect guideline concepts to case analysis
- [ ] Integrate guidelines into agent reasoning

## Current Status
The basic functionality for uploading, analyzing, and extracting concepts from guidelines is now fixed and operational. The two-phase approach allows users to:

1. Upload guidelines through the interface
2. Process the guidelines to extract key ethical concepts
3. Review the extracted concepts and their matches to existing ontology entities
4. Select which concepts to save as RDF triples
5. View the saved guidelines with their associated concepts

All guideline-related templates now use consistent parameter naming and URL generation, which should resolve the previous routing issues. We've specifically fixed the breadcrumb navigation in the guideline_concepts_review.html template to accept both direct parameters (world_id, document_id) and object properties (world.id, guideline.id) for backward compatibility.

## Recent Fixes
- Fixed route parameter naming in the guideline_concepts_review.html template
- Ensured consistent parameter naming between template and controller
- Corrected URL generation for navigation links
- Fixed form action URLs to properly submit analysis results
- Fixed parameter naming in guidelines.html template (changed world_id to id)
- Fixed parameter naming in guideline_content.html template (changed world_id/guideline_id to id/document_id)
- Fixed parameter naming in guideline_concepts_review.html template (changed world_id to id)
- Updated all URL generation to match the route parameter naming convention
- Fixed URL routing error by changing 'main.index' to 'index' in guidelines.html and guideline_content.html templates (resolves BuildError for endpoint 'main.index')
- Added missing `get_content_excerpt()` method to the Document model to fix 'jinja2.exceptions.UndefinedError: Document object has no attribute get_content_excerpt'
- Fixed guidelines.html template to handle different ways of storing concept counts between Document and Guideline models
- Updated guideline_content.html template to work with both Document and Guideline models' different field names for source URLs
- Removed reference to non-existent route `worlds.edit_guideline` from guidelines.html template
- Removed reference to non-existent route `worlds.edit_guideline` from guideline_content.html template
- Removed reference to non-existent route `worlds.export_guideline_triples` from guideline_content.html template
- Fixed breadcrumb navigation in guideline_concepts_review.html to handle both direct parameters (world_id, document_id) and object properties (world.id, guideline.id) for backward compatibility
- Removed all references to `csrf_token()` from guidelines-related templates to fix `jinja2.exceptions.UndefinedError: 'csrf_token' is undefined` error (Flask-WTF's CSRFProtect is not initialized in the application)
- Added default values for undefined variables in guideline_content.html: 
  * Added `|default(0)` filter to `triple_count` variable
  * Added `|default(0)` filter to `concept_count` variable
  * Added check for existence of `triples` list with `triples is defined and triples` in conditional

## Next Steps
1. Test the end-to-end workflow with real guidelines using the fixed templates
2. Enhance the display of ontology matching results
3. Improve the visual presentation of guidelines on the world detail page
4. Add functionality to manage existing guideline concepts
5. Add an explanation to the guideline analysis page that shows how the system matches concepts to ontology entities
