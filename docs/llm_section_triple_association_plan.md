# LLM-Based Section-Triple Association Implementation Plan

## Overview

This document outlines the plan for implementing an LLM-based approach to associate document sections with ontology concepts. The current embedding-based approach has limitations in matching section content with relevant concepts, resulting in too few associations. The LLM-based approach will leverage semantic understanding to identify more meaningful associations.

## Current State

The existing system implements a two-phase matching algorithm:
1. **Coarse matching** using vector similarity between section embeddings and concept embeddings
2. **Fine-grained matching** with semantic properties and section context

Limitations identified:
- Too few associations are being found (only 1 concept for many sections)
- Embedding space mismatch between narrative sections and concept definitions
- Granularity issues when embedding entire sections

## Approach

We'll leverage existing LLM integration in the application to implement a new association approach:

1. Create an `LLMSectionTripleAssociator` class based on patterns from `GuidelineSectionService`
2. Use multi-metric approach combining:
   - Vector similarity (if available)
   - Term overlap
   - Structural relevance
   - LLM assessment
3. Maintain database compatibility by using the same storage format
4. Enhance UI to display LLM reasoning for associations

## Implementation Steps

- [x] 1. Create `LLMSectionTripleAssociator` class
  - [x] a. Adapt `analyze_triple_relevance_with_llm` from GuidelineSectionService
  - [x] b. Adapt term overlap and structural relevance calculations
  - [x] c. Implement final relevance calculation

- [x] 2. Update `SectionTripleAssociationService`
  - [x] a. Add option to use LLM-based association
  - [x] b. Integrate LLM associator as an alternative
  - [x] c. Format results consistently

- [x] 3. Update route handler in document_structure.py
  - [x] a. Add method selection parameter
  - [x] b. Pass configuration to service

- [x] 4. Update UI templates
  - [x] a. Add method selection in form
  - [x] b. Display LLM reasoning for associations

## Testing Checkpoints

- [x] After implementing LLMSectionTripleAssociator: Test in isolation
- [x] After updating SectionTripleAssociationService: Verify service works
- [x] After updating route handler: Test method selection
- [x] End-to-end test with UI updates

## Additional Utilities Created

- Created `run_llm_section_triple_association.sh` script for command-line use
- Created `test_llm_section_triple_association.py` for testing with individual sections

## Success Criteria

- More concepts associated with sections (at least 3-5 per section)
- Meaningful explanations for why concepts are relevant
- Consistent database format with existing implementation
- UI displays both association methods and reasoning

## Future Enhancements

- Fine-tune the LLM prompt for better results
- Add caching to improve performance
- Implement hybrid approach combining embedding and LLM
- Develop specialized UI for concept filtering and visualization
