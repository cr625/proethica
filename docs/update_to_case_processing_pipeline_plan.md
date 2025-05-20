# Update to Case Processing Pipeline Plan

This document serves as an update to the original [Case Processing Pipeline Plan](case_processing_pipeline_plan.md), focusing specifically on the document structure enhancement implementation.

## Document Structure Enhancement Summary

We have extended the proethica-intermediate ontology to include document structure concepts that allow for fine-grained semantic markup of case documents. This enhancement:

1. Maintains compatibility with the Basic Formal Ontology (BFO) by modeling document elements as generically dependent continuants
2. Creates a structured hierarchy of document elements that correspond to case sections (Facts, Questions, References, Discussion, Conclusion)
3. Establishes semantic relationships between document elements and case content
4. Enables section-specific processing, including embedding generation

## Relationship to Existing Pipeline

The current case processing pipeline already handles the following steps:
- Extracting case content from URLs
- Parsing the document into HTML sections
- Storing the case in the database
- Generating document-level embeddings

Our document structure enhancement builds upon these existing steps by adding:

1. **Document Structure Annotation**: Map document sections to ontological classes
2. **Section-level Embedding Generation**: Create embeddings for individual sections
3. **Triple Generation**: Generate RDF triples that semantically describe the document structure
4. **Enhanced Search Capabilities**: Enable section-based comparison and similarity search

## Implementation Progress

Phase 1 of the implementation has been completed:
- Document structure classes have been defined in the ontology
- Document structure properties have been defined
- Sample triples have been created and tested
- SPARQL queries have been verified to work with the new structure

## Next Steps

The next implementation step is Phase 2.1: Create the DocumentStructureAnnotationStep class that will be integrated into the pipeline. This step will:

1. Extract sections from case documents
2. Classify sections according to the ontology
3. Generate structure triples
4. Link these triples to the case's semantic context

## Design Decision: Document Structure in Ontology

We have decided to include document structure in the ontology because:

1. **Semantic Integration**: Document structure provides important context for understanding case content
2. **BFO Compatibility**: Document elements are properly modeled as generically dependent continuants
3. **Enhanced Analysis**: Structure-aware processing enables more targeted language model analysis
4. **Improved Retrieval**: Section-based comparison allows for more precise similarity search

## Embedding Strategy

For embeddings, we have decided to implement both:
1. **Document-level embeddings** (existing implementation)
2. **Section-level embeddings** (new implementation)

This dual approach allows us to:
- Maintain backward compatibility with existing functionality
- Provide finer-grained similarity comparison between case sections
- Enable section-type-aware searching (e.g., comparing only Facts sections across cases)

## Technical Implementation Path

The step-by-step implementation will proceed as follows:

1. Create the DocumentStructureAnnotationStep class
2. Extend the EmbeddingService to handle section-level embeddings
3. Update the database schema to store section-level information
4. Enhance the UI to expose the new capabilities

Each step will be implemented with careful testing to ensure that existing functionality is not disrupted.

## Impact on Use Cases

This enhancement will improve the following use cases:
- Case similarity search (more precise section-based matching)
- Context-aware ethical analysis (section-specific contexts)
- Case comparison (direct comparison of corresponding sections)
- Knowledge graph exploration (structure-aware navigation)

The implementation maintains consistency with the BFO approach, treating document sections as generically dependent continuants that require some material bearer (the document itself) but are not tied to a specific physical implementation.
