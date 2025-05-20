# Document Structure Enhancement Plan

This document outlines the plan for enhancing the case processing pipeline to include ontology-based document structure markup and section-specific embeddings.

## Overview

The goal is to extend the ProEthica ontology to include document structure concepts, and enhance the case processing pipeline to:

1. Mark up case documents with semantic structure based on the ontology
2. Generate section-specific embeddings for more granular case comparison
3. Improve case similarity searching with section-level comparisons

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

- [ ] **1.3. Test ontology extensions**
  - [ ] Create sample triples using new classes and properties
  - [ ] Verify compatibility with existing ontology concepts
  - [ ] Test with SPARQL queries to ensure retrievability

### Phase 2: Pipeline Enhancement Implementation

- [ ] **2.1. Create Document Structure Annotation pipeline step**
  - [ ] Create DocumentStructureAnnotationStep class
  - [ ] Implement section extraction and classification
  - [ ] Implement triple generation for document structure
  - [ ] Add semantic property assignment based on content analysis

- [ ] **2.2. Integrate new pipeline step**
  - [ ] Register step with pipeline manager
  - [ ] Update process_url_pipeline route to include the new step
  - [ ] Add configuration options for ontology-based annotation

- [ ] **2.3. Update document storage for structure triples**
  - [ ] Modify document storage to include structure triples
  - [ ] Update doc_metadata schema to include structure information
  - [ ] Ensure backward compatibility with existing documents

### Phase 3: Section Embedding Implementation

- [ ] **3.1. Enhance EmbeddingService for section-level embeddings**
  - [ ] Add methods to generate embeddings for individual sections
  - [ ] Create storage schema for section embeddings
  - [ ] Implement section-to-section similarity functions

- [ ] **3.2. Update Database Schema**
  - [ ] Create migration for section_embeddings table if needed
  - [ ] Update document_chunks schema if necessary
  - [ ] Add indexing for efficient section similarity search

- [ ] **3.3. Integrate section embeddings with case processing**
  - [ ] Update case processing to include section embedding generation
  - [ ] Ensure section embeddings are stored with section identifiers
  - [ ] Add API endpoints for section-based similarity search

### Phase 4: UI and Visualization Updates

- [ ] **4.1. Enhance case detail view**
  - [ ] Update case_detail.html to display structure annotations
  - [ ] Add visual indicators for semantic properties
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

- [ ] **M1: Verify ontology extension**
  - [ ] Validate consistency with BFO principles
  - [ ] Test triple generation with sample cases
  - [ ] Verify querying capabilities

- [ ] **M2: Test document structure pipeline**
  - [ ] Process test cases through enhanced pipeline
  - [ ] Verify correct structure detection and annotation
  - [ ] Validate triple generation and storage

- [ ] **M3: Validate section embeddings**
  - [ ] Generate embeddings for various section types
  - [ ] Test similarity between related sections
  - [ ] Benchmark performance against full-document embeddings

- [ ] **M4: End-to-end system testing**
  - [ ] Import case and verify all enhancements work together
  - [ ] Test UI features with real case data
  - [ ] Validate search results with section-based queries

## Implementation Notes

- All changes should maintain backward compatibility with existing cases
- Each phase should be implemented incrementally with validation after each step
- Database migrations should be carefully tested before application
- Performance impact of additional triples and embeddings should be monitored

## Progress Log

*This section will be updated as implementation progresses*

### Date: May 20, 2025
- Initial planning document created (Git commit: e4335a01d6925eca96db3ae31c8dc80d44adefde)
- Document structure ontology design completed
- Implementation phases and tracking system established
- Starting point established for Phase 1.1: Define document structure classes in ontology
