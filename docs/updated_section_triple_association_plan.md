# Updated Section-Triple Association Plan

This document outlines the implementation plan for the updated section-triple association system that directly uses ontology TTL files instead of database-stored triples.

## 1. Project Overview

The goal is to create a system that associates document sections with relevant ontology concepts from the enhanced engineering-ethics.ttl and proethica-intermediate.ttl files, with a focus on role-related concepts.

Key improvements over the previous approach:
- Direct use of ontology TTL files instead of database triples
- Leveraging semantic matching properties added to the ontology
- Context-aware matching based on section types
- Focus on role-related concepts and principles

## 2. Implementation Phases

### Phase 1: Core Component Development
1. [x] Create OntologyTripleLoader class
   - [x] Load TTL files directly with rdflib
   - [x] Extract concepts with semantic properties
   - [x] Prioritize role-related concepts
   - [x] Clean text for embedding generation

2. [x] Develop embedding service
   - [x] Generate embeddings for sections and concepts
   - [x] Compute similarity metrics
   - [x] Handle text cleaning to avoid formatting tokens

3. [x] Implement two-phase matching algorithm
   - [x] Coarse matching with vector similarity
   - [x] Fine-grained matching with semantic properties
   - [x] Section type context awareness

4. [x] Create storage mechanism
   - [x] Define table structure for associations
   - [x] Implement storage and retrieval functions

### Phase 2: Integration and Testing
1. [x] Build main service class
   - [x] Bring components together
   - [x] Connect to database for section access
   - [x] Implement batch processing

2. [x] Develop command-line interface
   - [x] Process flags for different modes
   - [x] Support section selection options
   - [x] Provide progress reporting

3. [✓] Create comprehensive testing scripts
   - [x] Test ontology loading
   - [ ] Test with sample document
   - [ ] Benchmark performance

### Phase 3: UI Integration and Refinement
1. [ ] Update web interface
   - [ ] Display associated concepts
   - [ ] Filter by concept type
   - [ ] Show match confidence

2. [ ] Develop evaluation tools
   - [ ] Compare with previous approach
   - [ ] Manual review interface
   - [ ] Gather metrics on match quality

## 3. Progress Tracking

| Phase | Task | Status | Notes | Completion Date |
|-------|------|--------|-------|----------------|
| 1.1 | Create OntologyTripleLoader class | Completed | Implemented with role/principle detection | 2025-05-22 |
| 1.2 | Develop embedding service | Completed | Added text cleaning and similarity calculation | 2025-05-22 |
| 1.3 | Implement two-phase matching algorithm | Completed | Built coarse and fine-grained matching | 2025-05-22 |
| 1.4 | Create storage mechanism | Completed | Added database storage for associations | 2025-05-22 |
| 2.1 | Build main service class | Completed | Created comprehensive service layer | 2025-05-22 |
| 2.2 | Develop command-line interface | Completed | Added CLI with batch processing options | 2025-05-22 |
| 2.3 | Create comprehensive testing scripts | Partially Complete | Created ontology loader test | 2025-05-22 |
| 3.1 | Update web interface | Not Started | | |
| 3.2 | Develop evaluation tools | Not Started | | |

## 4. Key Component Details

### OntologyTripleLoader
```python
class OntologyTripleLoader:
    def __init__(self, ontology_files=None):
        """
        Initialize with optional ontology file paths, otherwise use defaults.
        
        Args:
            ontology_files: List of paths to .ttl files to load
        """
        if ontology_files is None:
            # Default to the standard ontology files
            self.ontology_files = [
                "ontologies/proethica-intermediate.ttl",
                "ontologies/engineering-ethics.ttl"
            ]
        else:
            self.ontology_files = ontology_files
            
        self.graph = None
        self.concepts = {}
        self.role_concepts = {}
        self.role_related_concepts = {}
        
    def load(self):
        """Load ontologies from .ttl files into an RDFLib graph."""
        # Load ontology files
        # Extract concepts and properties
        
    def get_concept_text_for_embedding(self, concept_uri):
        """Get clean text representation of concept for embedding."""
        # Create text combining label, description, and matching terms
        # Remove formatting tokens and technical syntax
```

### SectionTripleAssociator
```python
class SectionTripleAssociator:
    def __init__(self, ontology_loader, embedding_service, 
                 similarity_threshold=0.6, max_matches=10):
        """Initialize the associator with components and parameters."""
        # Initialize components and parameters
        # Generate concept embeddings
        
    def associate_section(self, section_embedding, section_metadata):
        """
        Associate a section with relevant ontology concepts.
        
        Args:
            section_embedding: Vector embedding of the section
            section_metadata: Metadata about the section
            
        Returns:
            List of match dictionaries with scores and metadata
        """
        # Two-phase matching process
        # Return ranked list of matching concepts
        
    def _get_section_context(self, section_metadata):
        """Extract contextual information about the section from structure triples."""
        # Determine section type and assign appropriate boosts
        # Return context object for fine-grained matching
```

### Main Service Integration
```python
class SectionTripleAssociationService:
    def __init__(self, similarity_threshold=0.6, max_matches=10):
        """Initialize the service with components and parameters."""
        # Initialize loader, embedding service, and associator
        # Set up database connection
        
    def associate_section_with_concepts(self, section_id):
        """Associate a document section with relevant ontology concepts."""
        # Get section embedding and metadata
        # Perform association
        # Store results
        
    def batch_associate_sections(self, section_ids, batch_size=50):
        """Process multiple sections in batch."""
        # Process sections in batches
        # Track progress and results
```

## 5. Testing Strategy

1. Unit tests for each component
   - Test ontology loading
   - Test embedding generation
   - Test matching algorithms

2. Integration tests
   - End-to-end processing of sample document
   - Verify database storage and retrieval

3. Regression tests
   - Ensure existing functionality is preserved
   - Compare with previous implementation

## 6. Success Criteria

1. All case sections successfully associated with relevant ontology concepts
2. Role-related concepts correctly prioritized in matching
3. Match quality verified through manual review
4. Processing completes within reasonable time and resource limits
5. Web interface properly displays concept associations

## 7. Implementation Log

| Date | Component | Action | Status | Notes |
|------|-----------|--------|--------|-------|
| 2025-05-22 | Plan | Created updated implementation plan | Complete | Updated plan to use TTL files directly |
| 2025-05-22 | OntologyTripleLoader | Implemented initial version | Complete | Added support for role and principle concept identification |
| 2025-05-22 | EmbeddingService | Implemented initial version | Complete | Added text cleaning and similarity calculation |
| 2025-05-22 | SectionTripleAssociator | Implemented initial version | Complete | Added two-phase matching with context-awareness |
| 2025-05-22 | Storage | Implemented database storage | Complete | Created table and added CRUD operations |
| 2025-05-22 | Service | Implemented main service | Complete | Added batch processing and retrieval functions |
| 2025-05-22 | CLI | Implemented command-line interface | Complete | Added support for various processing modes |
| 2025-05-22 | Testing | Created ontology loader test | Complete | Added test script for verifying loader functionality |
| 2025-05-22 | Testing | Created document test script | Complete | Added end-to-end test with statistics reporting |

## 8. Next Steps

1. Test the implementation with a sample document
2. Verify that associations are stored correctly
3. Evaluate the quality of concept matches
4. Update the web interface to show concept associations
5. Develop additional testing and evaluation tools
