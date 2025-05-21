# Document Structure Enhancement Plan

This document outlines the plan for enhancing the case processing pipeline to include ontology-based document structure markup and section-specific embeddings.

## Overview

The goal is to extend the ProEthica ontology to include document structure concepts, and enhance the case processing pipeline to:

1. Mark up case documents with semantic structure based on the ontology
2. Generate section-specific embeddings for more granular case comparison
3. Improve case similarity searching with section-level comparisons
4. Connect document sections with ethical principles and guidelines for advanced semantic reasoning

## Implementation Tracking

### Phase 1: Ontology Extension Implementation

- [x] **1.1. Define document structure classes in proethica-intermediate.ttl**
  - [x] Create DocumentElement as base class (subclass of BFO generically dependent continuant)
  - [x] Define DocumentSection and its subclasses (Facts, Questions, References, Discussion, Conclusion)
  - [x] Define DocumentMetadata classes (CaseNumber, Year, Title)
  - [x] Define StructuredContent classes (QuestionItem, ConclusionItem)
  - [x] Verify ontology consistency after additions

- [x] **1.2. Define document structure properties in proethica-intermediate.ttl**
  - [x] Add basic properties (hasTextContent, isPartOf, mentions)
  - [x] Add section-specific semantic properties (describesEvent, concernsPrinciple, etc.)
  - [x] Add document-case relationship properties
  - [x] Verify property domains and ranges are properly set

- [x] **1.3. Test ontology extensions**
  - [x] Create sample triples using new classes and properties
  - [x] Verify compatibility with existing ontology concepts
  - [x] Test with SPARQL queries to ensure retrievability

### Phase 2: Pipeline Enhancement Implementation

- [x] **2.1. Create Document Structure Annotation pipeline step**
  - [x] Create DocumentStructureAnnotationStep class
  - [x] Implement section extraction and classification
  - [x] Implement triple generation for document structure
  - [x] Add semantic property assignment based on content analysis

- [x] **2.2. Prepare integration files**
  - [x] Create integration test for pipeline manager
  - [x] Prepare route update implementation guide
  - [x] Define configuration approach for pipeline with document structure

- [x] **2.3. Complete integration**
  - [x] Register step in production pipeline manager
  - [x] Update actual process_url route with document structure annotation
  - [x] Test integration with live system

- [x] **2.4. Update document storage for structure triples**
  - [x] Modify document storage to include structure triples
  - [x] Update doc_metadata schema to include structure information
  - [x] Ensure backward compatibility with existing documents

- [ ] **2.5. Guideline-Section Association** (To be implemented after Phase 3)
  - [ ] Create mapping between document sections and guideline triples
  - [ ] Identify ethical principles relevant to each document section
  - [ ] Generate new triples linking sections to guideline concepts
  - [ ] Update metadata schema to store section-guideline associations 
  - [ ] Enhance structure visualization to display guideline associations

### Phase 3: Section Embedding Implementation

- [x] **3.1. Enhance EmbeddingService for section-level embeddings**
  - [x] Add methods to generate embeddings for individual sections
  - [x] Create storage schema for section embeddings
  - [x] Implement section-to-section similarity functions

- [x] **3.2. Update Database Schema**
  - [x] Leverage existing document_metadata JSON structure for section embeddings
  - [x] Store embeddings alongside section content in document structure
  - [x] Ensure backward compatibility with existing documents

- [x] **3.3. Integrate section embeddings with case processing**
  - [x] Create utility script for processing existing documents
  - [x] Add routes for section-based similarity search
  - [x] Implement visual interface for section comparison

### Phase 4: UI and Visualization Updates

- [x] **4.1. Enhance case detail view** (Partially Complete)
  - [x] Update case_detail.html with "View Structure" button replacing non-functional "Edit Triples" button
  - [x] Create document_structure.html template to display structure annotations
  - [x] Create document_structure.py routes for structure visualization
  - [ ] Add visual indicators for semantic properties directly in case view
  - [ ] Implement toggles for showing/hiding annotations

- [ ] **4.2. Add section-based similarity search**
  - [ ] Create UI controls for section-specific searches
  - [ ] Implement result visualization for section matches
  - [ ] Add highlighting for matching section content

- [ ] **4.3. Documentation and user guidance**
  - [ ] Update user documentation for structure features
  - [ ] Add tooltips or help text for new UI elements
  - [ ] Create examples of structure-based searching

## Testing Milestones

- [x] **M1: Verify ontology extension**
  - [x] Validate consistency with BFO principles
  - [x] Test triple generation with sample cases
  - [x] Verify querying capabilities

- [ ] **M2: Test document structure pipeline**
  - [ ] Process test cases through enhanced pipeline
  - [ ] Verify correct structure detection and annotation
  - [ ] Validate triple generation and storage

- [ ] **M3: Validate section embeddings**
  - [ ] Generate embeddings for various section types
  - [ ] Test similarity between related sections
  - [ ] Benchmark performance against full-document embeddings

- [ ] **M2.5: Validate guideline-section associations**
  - [ ] Verify accurate mapping between sections and ethical principles
  - [ ] Test retrieval of cases based on section-guideline combinations
  - [ ] Validate visualization of guideline associations

- [ ] **M4: End-to-end system testing**
  - [ ] Import case and verify all enhancements work together
  - [ ] Test UI features with real case data
  - [ ] Validate search results with section-based queries

## Implementation Notes

- All changes should maintain backward compatibility with existing cases
- Each phase should be implemented incrementally with validation after each step
- Database migrations should be carefully tested before application
- Performance impact of additional triples and embeddings should be monitored
- Record Git commit hashes after each major change to enable precise version tracking and potential rollbacks
- Phase 2.5 (Guideline-Section Association) will be implemented chronologically after Phase 3, despite its logical placement in the document structure phases

## Progress Log

*This section will be updated as implementation progresses*

### Date: May 20, 2025
- Initial planning document created (Git commit: e4335a01d6925eca96db3ae31c8dc80d44adefde)
- Document structure ontology design completed
- Implementation phases and tracking system established
- Starting point established for Phase 1.1: Define document structure classes in ontology

### Date: May 20, 2025 (Continued)
- Completed Phase 1: Ontology Extension Implementation
  - Added document structure classes to proethica-intermediate.ttl (Git commit: c4807fe)
  - Added document structure properties to proethica-intermediate.ttl (Git commit: c4807fe)
  - Created sample triples for testing in document_structure_sample_triples.ttl (Git commit: fa60ea8)
  - Created SPARQL test queries in document_structure_sparql_tests.md (Git commit: fa60ea8)
  - Verified compatibility with existing ontology concepts
  - Successfully ran the application to confirm backward compatibility
- The ontology extension follows BFO principles by modeling document parts as generically dependent continuants, which is appropriate since document sections depend on the document but are not tied to a specific physical implementation

### Date: May 20, 2025 (Evening)
- Completed Phase 2.1: Document Structure Annotation pipeline step
  - Created DocumentStructureAnnotationStep class that implements BaseStep
  - Implemented document structure triple generation
  - Added section-level embedding metadata preparation
  - Successfully tested the pipeline step with mock case data
  - Verified correct RDF generation (82 triples generated for test case)
  - Added support for individual question and conclusion items
  - Implemented document section sequence relationships

### Date: May 20, 2025 (Night)
- Completed Phase 2.2: Prepare integration files
  - Created test_integrate_document_structure_step.py for testing integration with PipelineManager
  - Developed app/routes/update_pipeline_route.py as an example implementation guide
  - Defined approach for integrating with existing routes and pipeline
  - Documented the implementation path in the enhancement plan
  - Ready for production integration in Phase 2.3

### Date: May 20, 2025 (Late Night)
- Completed Phase 2.3: Production integration
  - Created app/routes/cases_structure_update.py with production-ready route implementation
  - Updated app/templates/create_case_from_url.html with enhanced pipeline option
  - Registered cases_structure_bp blueprint in app/__init__.py
  - Added test_document_structure_integration.py for full integration testing
  - Both standard and enhanced pipelines now accessible through the UI

### Date: May 20, 2025 (End of Day)
- Completed Phase 2.4: Update document storage for structure triples
  - Created update_document_structure_storage.py script to annotate existing cases
  - Implemented formatted document structure storage in doc_metadata
  - Successfully tested and verified with Case 222 (generated 127 triples)
  - Ensured backward compatibility with existing document retrieval code
  - Enhanced schema documentation for doc_metadata structure
  - Ready to implement Phase 3: Section Embedding Implementation

### Date: May 20, 2025 (Late Night)
- Partially Completed Phase 4.1: UI Case Detail View Enhancements
  - Created document_structure.py routes for structure visualization
  - Created document_structure.html template to display document structure details
  - Added "View Structure" button to case detail page, replacing non-functional "Edit Triples" button
  - Implemented display of structure triples and section metadata
  - Created documentation for structure viewing functionality
  - Registered doc_structure_bp blueprint in app/__init__.py
  - Ready for Phase 3 implementation while continuing UI enhancements

### Date: May 20, 2025 (Before Midnight)
- Plan Enhancement: Added Phase 2.5 for Guideline-Section Association
  - Extended implementation plan to include mapping between document sections and guideline triples
  - Revised implementation sequence to place Phase 2.5 after Phase 3
  - Added new Testing Milestone M2.5 for guideline-section associations
  - Enhanced implementation notes with Git commit tracking guidance
  - Emphasized logical relationship of document markup to ethical principles
  - Set up technical pathway for advanced semantic reasoning capabilities

### Date: May 21, 2025 (Just After Midnight)
- Completed Phase 3: Section Embedding Implementation
  - Created SectionEmbeddingService as an extension of the existing EmbeddingService
  - Implemented section-to-section similarity calculation with cosine similarity
  - Added functionality to store section embeddings within document_metadata
  - Created utility script (update_section_embeddings.py) for batch processing existing cases
  - Enhanced document_structure.py routes with section embedding generation and searching
  - Added UI templates for section similarity searches (section_search.html)
  - Added UI for comparing similar sections across cases (section_comparison.html)
  - Wrote unit tests for section embedding functionality (test_section_embeddings.py)
