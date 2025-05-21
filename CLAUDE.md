# AI Ethical DM Development Progress

## Case Document Structure Enhancement Project

### Current Status (May 21, 2025)
- **Phase 1 Complete**: Extended ontology with document structure classes and properties
- **Phase 2.1-2.3 Complete**: 
  - Implemented DocumentStructureAnnotationStep pipeline component
  - Created integration files and example implementation
  - Completed production integration with UI access
  - Successfully tested with both mock and real case data
- **Phase 2.4 Complete**:
  - Implemented document storage schema updates for structure triples
  - Created update script for existing cases (`update_document_structure_storage.py`)
  - Successfully tested and verified with Case 222
  - Each case now has formal document structure RDF triples in doc_metadata
- **Phase 3 Complete**:
  - Created SectionEmbeddingService extending EmbeddingService
  - Implemented section-to-section similarity calculation with cosine similarity
  - Added storage for section embeddings in document_metadata
  - Created UI for section similarity searches and comparisons
  - Developed utility script (update_section_embeddings.py) for batch processing
  - Enhanced section embedding generation with robust content finding strategies
  - Added support for multiple document structure formats
  - Fixed compatibility issue with legacy metadata structures
  - Implemented automatic metadata reorganization during embedding generation
- **Phase 4.1 (Partial) Complete**:
  - Added "View Structure" button to case detail page (replacing non-functional "Edit Triples" button)
  - Created document structure visualization template and routes
  - Implemented display of structure triples and section metadata
  - Added "Generate Document Structure" button for direct UI access to structure generation
  - Enhanced error handling and format compatibility for structure generation
  - Added support for legacy document structure formats with automatic reorganization
- **Plan Enhancement**:
  - Added Phase 2.5: Guideline-Section Association (to be implemented after Phase 3)
  - Created pathway for connecting document sections with ethical principles
  - Added testing milestone for guideline-section associations
- **Next Steps**:
  - Phase 2.5: Implement guideline-section associations
  - Complete Phase 4: Further enhance UI with visual indicators and section-based search

### Implementation Details

We've successfully implemented the document structure annotation step for the case processing pipeline. This enhancement:

1. **Creates semantic markup** of case documents using our ontology
2. **Structures case content** into well-defined sections (Facts, Questions, Discussion, References, Conclusion)
3. **Prepares for section-level embeddings** to enable more granular similarity search
4. **Establishes relationships** between document parts following BFO principles

The implementation includes:

- New pipeline step class: `DocumentStructureAnnotationStep`
- Integration test: `test_document_structure_step.py` (standalone test)
- Pipeline integration test: `test_integrate_document_structure_step.py`
- Integration guide: `app/routes/update_pipeline_route.py`

### Testing Results

Our mock test case (with 82 generated triples) successfully:
- Creates a document entity with proper URI
- Identifies and classifies all document sections
- Extracts and associates individual questions and conclusions
- Establishes document sequence relationships
- Prepares metadata for section-level embeddings

### Ontological Approach

We've modeled document sections as generically dependent continuants in the BFO framework. This means:
- Sections are entities that depend on the document but aren't tied to a specific physical manifestation
- They maintain identity across different representations (HTML, text, etc.)
- They can have complex relationships to other entities in our ontology

### Embedding Strategy

We're implementing a dual embedding approach:
1. **Document-level embeddings** (existing): For overall case similarity
2. **Section-level embeddings** (new): For more granular comparison

This will allow us to answer queries like:
- "Find cases with similar facts but different conclusions"
- "Find cases with similar ethical questions addressed"
- "Compare discussions between related cases"

### Next Phase

Ready to implement:
- Phase 2.5: Guideline-Section Association
  - Map document sections to ethical principles and guidelines
  - Create visualization for guideline associations
  - Generate new triples linking sections to guideline concepts 
  - Update metadata schema to store section-guideline associations
- Remaining Phase 4 Tasks: UI and visualization updates
  - Add visual indicators for semantic properties directly in case view
  - Enhance existing section-based similarity search with additional filters
  - Complete user documentation and tooltips for structure features
