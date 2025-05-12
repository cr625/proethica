# Guidelines Feature Implementation Progress

## Overview

This document tracks the implementation of the feature that allows users to associate RDF triples with uploaded guidelines in the Engineering World. The feature enables users to:

1. Upload guidelines (file, paste content, or provide URL)
2. Parse uploaded guidelines with LLM to extract ontology concepts
3. Present the user with suggested associated RDF triples derived from ontology entities
4. Allow the user to select which triples to include by checking/unchecking them
5. Associate selected triples with the guidelines document

## Implementation Phases

### Phase 1: Basic Guidelines Display (Completed)

- [x] Update `world_detail.html` template to properly display guidelines section
- [x] Update Principles and Obligations tab sections in `world_detail.html`
- [x] Add Events and Capabilities tabs in `world_detail.html`
- [x] Update `guideline_concepts_review.html` to include Events and Capabilities tabs
- [x] Update `GuidelineAnalysisService` to recognize Events and Capabilities as valid concept types

### Phase 2: Guidelines Upload and Processing (In Progress)

- [x] Ensure guideline upload interface is working correctly at `/worlds/{id}/guidelines/add`
- [x] Implement integration with LLM for parsing guidelines content
  - [x] Extract concepts based on the engineering ethics ontology
  - [x] Match extracted concepts to existing ontology entities
- [x] Handle file uploads (PDF, DOCX, TXT) with appropriate content extraction

### Phase 3: Guidelines Review UI (In Progress)

- [x] Implement basic guideline concepts review page
  - [x] Display extracted concepts grouped by type
  - [x] Show matched existing ontology entities 
  - [x] Implement concept selection with checkboxes
- [ ] Enhance the guideline concepts review page
  - [ ] Improve visual distinction between new concepts and matched existing concepts
  - [ ] Add filtering options for concepts
  - [ ] Add sorting capabilities
- [ ] Create preview of final selected concepts before saving

### Phase 4: RDF Triple Association (In Progress)

- [x] Create basic functionality to associate concepts with RDF triples
- [x] Store triples in the database with proper subject/predicate/object structure
- [ ] Enhance triple visualization after guidelines are saved
- [ ] Implement a better triple browsing interface

### Phase 5: Testing and Refinement (Pending)

- [ ] Test with various guideline formats (PDF, DOCX, TXT)
- [ ] Test with different sizes of guidelines documents
- [ ] Refine LLM prompt for better concept extraction
- [ ] Optimize performance for larger documents

## Technical Notes

### LLM Integration

- Using `app/utils/llm_utils.py` for LLM client management
- The `GuidelineAnalysisService` handles:
  - Extracting concepts from guidelines using LLM
  - Matching concepts to existing ontology entities
  - Creating RDF triples for selected concepts
- Using a fallback mechanism between Anthropic and OpenAI models

### Entity Type Support

The system now supports the following entity types:
- Principles
- Obligations
- Roles
- Actions
- Resources
- Conditions
- Events (newly added)
- Capabilities (newly added)

### UI Components

- `world_detail.html`: Main world page showing all entities and guidelines
- `guideline_concepts_review.html`: Interface for reviewing extracted concepts from guidelines
- `guideline_content.html`: Display of guideline content

## Next Steps

1. Visual enhancements for concept review page:
   - Add clear visual distinction between new concepts and ones that match existing ontology entities
   - Implement sorting capabilities (by relevance, alphabetically, by confidence score)
   - Add filtering options to show only certain concept types or matching status

2. Triple visualization improvements:
   - Create a dedicated view for browsing triples associated with a guideline
   - Visualize relationships between concepts in a graph format
   - Allow editing of triple associations after initial creation

3. Testing with various guideline formats:
   - Test PDF documents with different layouts and formatting
   - Test with DOCX files containing tables, images, and complex formatting
   - Test with different URL sources including academic papers and ethical guidelines

4. Performance optimizations:
   - Implement caching for LLM responses to avoid repeated processing
   - Optimize database queries for guideline-related triple operations
   - Consider batch processing for larger documents

## Conclusion

The guidelines feature enhancement has successfully implemented support for additional entity types (Events and Capabilities) throughout the system. This work enables a more comprehensive analysis of ethical guidelines by:

1. Expanding the ontology concept extraction capabilities to identify a wider range of entity types
2. Providing a more complete UI for reviewing and selecting these entities
3. Supporting the creation of RDF triples for these new entity types

These changes bring the system closer to providing a complete mapping between ethical guidelines and the engineering-ethics ontology, allowing for better reasoning about ethical considerations in engineering practice.

Most of the core infrastructure was already in place, and our enhancements have extended its capabilities. The system now has a solid foundation for the improved guideline processing workflow, with clear next steps for further refinement and optimization.
