# AI Ethical DM Enhancement Progress

## Project Overview

ProEthica is an application for ethical analysis of engineering cases, using a semantic knowledge graph approach. The system imports cases, processes their content, and applies ontology-based reasoning to support ethical decision-making.

## Current Work: Document Structure Enhancement

We're enhancing the case processing pipeline to add document structure markup based on the ontology. This involves encoding document sections (Facts, Questions, Discussion, etc.) as semantic entities with appropriate relationships.

### Completed Implementation (Phase 1)

1. **Ontology Extension (Phase 1.1 and 1.2)**:
   - Added `DocumentElement` as base class under BFO generically dependent continuant
   - Created document section classes (`FactsSection`, `QuestionsSection`, etc.)
   - Defined document metadata classes (`CaseNumber`, `CaseYear`, `CaseTitle`)
   - Added structured content classes (`QuestionItem`, `ConclusionItem`, `CodeReferenceItem`)
   - Created document structure properties for hierarchical and semantic relationships
   - Added section-specific semantic relationship properties

2. **Testing (Phase 1.3)**:
   - Created sample triples file to demonstrate document structure ontology usage
   - Developed SPARQL test queries to validate retrievability of document structure concepts
   - Verified compatibility with existing ontology concepts
   - Ran the application to confirm backward compatibility

### Next Implementation Steps (Phase 2)

1. **Create DocumentStructureAnnotationStep** (Phase 2.1):
   - New pipeline step to extract and classify document sections
   - Generate document structure triples
   - Link structure to semantic context

2. **Section-level Embeddings** (Phase 3):
   - Extend EmbeddingService for section-level embedding generation
   - Update database schema to store section embeddings
   - Support section-based similarity search

### Design Decisions

1. **Document Structure in Ontology**: We decided to include document structure in the proethica-intermediate ontology, treating sections as generically dependent continuants following BFO principles.

2. **Dual Embedding Strategy**: We'll implement both document-level embeddings (existing) and section-level embeddings (new) to enable finer-grained similarity comparison while maintaining backward compatibility.

### Git Commits

1. **c4807fe**: Add document structure classes and properties to proethica-intermediate ontology (Phase 1.1 and 1.2)
2. **861f1aa**: Update document structure enhancement plan with completed tasks
3. **fa60ea8**: Complete Phase 1.3: Test ontology extensions
4. **828b526**: Mark M1 testing milestone as completed
5. **a547f66**: Add update to case processing pipeline plan connecting new structure to existing workflow

## Progress Tracking

The project is following the detailed implementation plan in `docs/document_structure_enhancement_plan.md`, which breaks down the work into phases and tracks completion status.

Currently completed:
- Phase 1: Ontology Extension Implementation (100%)
- Testing Milestone M1: Verify ontology extension (100%)

Next steps:
- Phase 2.1: Create DocumentStructureAnnotationStep class

## Related Documents

- `docs/document_structure_enhancement_plan.md`: Main implementation plan
- `docs/update_to_case_processing_pipeline_plan.md`: Connection to existing pipeline
- `docs/document_structure_sample_triples.ttl`: Sample triples for testing
- `docs/document_structure_sparql_tests.md`: SPARQL queries for testing
- `ontologies/proethica-intermediate.ttl`: Extended ontology with document structure
