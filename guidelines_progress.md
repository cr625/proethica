# Guidelines Integration Progress

This document tracks the implementation progress of the guideline analysis and concept extraction feature for the AI Ethical DM application.

## Overview

The goal of this feature is to allow users to upload ethical guidelines for engineering (or other domains) and automatically extract key ontological concepts from these guidelines. The system then associates these concepts with the appropriate world as RDF triples, linking them to the existing ontology when possible.

## Implementation Phases

### Phase 1: Initial Setup and Display (COMPLETED)

- [x] Create the `GuidelineAnalysisService` class to handle guideline analysis
- [x] Add the LLM utilities to support concept extraction
- [x] Create the guideline concepts review template
- [x] Implement the World routes to handle guideline analysis and concept selection
- [x] Update the guidelines template to include an "Analyze & Extract Concepts" option

### Phase 2: Concept Extraction and Review (CURRENT)

- [ ] Test the concept extraction with example guideline documents
- [ ] Improve the concept extraction prompting if needed
- [ ] Implement entity matching between extracted concepts and existing ontology entities
- [ ] Enhance the UI to show confidence scores and matched entities
- [ ] Add filtering and sorting options for extracted concepts

### Phase 3: RDF Triple Generation and Integration

- [ ] Create RDF triples from selected concepts 
- [ ] Link concepts to existing ontology entities using relation predicates
- [ ] Implement proper IRI generation for extracted concepts
- [ ] Add a preview of created triples before final confirmation
- [ ] Create a visual graph representation of the extracted concepts

### Phase 4: Advanced Features

- [ ] Implement batch processing for multiple guidelines at once
- [ ] Add user feedback mechanism for improving concept extraction
- [ ] Implement automatic guideline versioning and change tracking
- [ ] Integrate with the reasoning engine to detect conflicts between guidelines
- [ ] Add support for different ethical frameworks and domains

## Technical Implementation Details

### LLM Integration

We're using Anthropic's Claude API as the primary LLM for concept extraction, with a fallback to OpenAI's GPT models. The `get_llm_client()` utility function in `app/utils/llm_utils.py` handles this logic.

The concept extraction process:
1. Takes the guideline document content
2. Provides context about the ontology structure and existing entities
3. Prompts the LLM to extract key concepts and categorize them
4. Processes the response to create structured concept objects

### Ontology Integration

For each extracted concept:
1. We attempt to match it to existing entities in the ontology
2. Create a new entity if no good match is found
3. Generate appropriate RDF triples to represent the concept
4. Create relationship triples to link to existing entities where appropriate

### User Interface Flow

1. User uploads or enters guideline text (existing functionality)
2. After processing, user clicks "Analyze & Extract Concepts" 
3. System extracts concepts and displays them in categorized tabs
4. User reviews and selects which concepts to include
5. System generates RDF triples for selected concepts
6. User is returned to the guidelines list with a success message

## Next Steps

1. Complete the concept matching implementation in the `GuidelineAnalysisService`
2. Test the flow with real guidelines to verify concept extraction quality
3. Implement the RDF triple generation functions
4. Add proper error handling and user feedback
5. Add additional UI enhancements for better concept review experience

## Known Issues

- Need to handle very large guidelines appropriately (currently truncating at 15,000 chars)
- Need to implement proper caching for LLM responses to avoid duplicate processing
- Need to handle edge cases where concept extraction fails or produces unexpected results
