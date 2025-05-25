# Section Embedding Enhancement Plan

## Overview
This plan outlines improvements to the section embedding workflow to enable granular similarity analysis at the section level (fact_1, question_1, discussion_segment_1, etc.) with future support for ontology-based semantic enrichment.

## Current State Analysis

### What Works
- Basic section embedding generation using all-MiniLM-L6-v2 (384 dimensions)
- Storage in PostgreSQL with pgvector
- Document-level metadata extraction
- Structure triple generation with granular section items

### Current Limitations
1. **Granularity Gap**: Embeddings are generated for entire sections (Facts, Discussion) rather than individual items (fact_1, fact_2, discussion_segment_1)
2. **No Section Type Awareness**: System doesn't differentiate between section types during similarity search
3. **Missing Ontology Integration**: No connection between embeddings and ontology concepts
4. **Limited Comparison Options**: No UI for section-to-section similarity analysis

## Phase 1: Granular Section Embeddings (Immediate)

### 1.1 Update Data Model
```python
# Extend DocumentSection model to include:
- section_type: String (fact, question, discussion_segment, conclusion, reference)
- section_number: Integer (1, 2, 3...)
- parent_section: String (Facts, Questions, Discussion, etc.)
- ontology_concepts: JSON (future use)
```

### 1.2 Enhance Section Parsing
Update `section_embedding_service.py` to:
- Parse structure triples to extract individual items
- Create separate embeddings for each fact_1, question_1, etc.
- Maintain section type and sequence information

### 1.3 Embedding Generation Strategy
```python
def generate_granular_embeddings(document):
    """Generate embeddings for individual section items"""
    # Parse structure triples
    structure = document.doc_metadata.get('document_structure', {})
    triples = structure.get('structure_triples', '')
    
    # Extract individual items:
    # - FactStatements (fact_1, fact_2...)
    # - Questions (question_1, question_2...)
    # - DiscussionSegments (discussion_segment_1...)
    # - Conclusions (conclusion_1, conclusion_2...)
    
    # Generate embedding for each item
    # Store with metadata: type, number, parent_section
```

## Phase 2: Like-to-Like Comparison (Week 1-2)

### 2.1 Similarity Search Enhancement
- Add section_type filtering to similarity queries
- Create dedicated endpoints for type-specific searches:
  - `/api/similarity/facts` - Compare facts across cases
  - `/api/similarity/questions` - Compare questions
  - `/api/similarity/discussions` - Compare discussion segments

### 2.2 UI Components
- Add "Find Similar" button next to each section item
- Create similarity results panel showing:
  - Similar items from other cases
  - Similarity score
  - Case context (number, year, title)

### 2.3 Indexing Strategy
```sql
-- Create composite indexes for efficient type-based queries
CREATE INDEX idx_section_embeddings_type_vector 
ON document_sections(section_type, embedding_vector);
```

## Phase 3: Cross-Section Analysis (Week 3-4)

### 3.1 Relationship Mapping
Define meaningful cross-section relationships:
- Facts → Questions (what questions arise from these facts?)
- Questions → Discussion (how are questions addressed?)
- Discussion → Conclusions (what conclusions follow?)
- Facts → Conclusions (direct fact-to-conclusion paths)

### 3.2 Weighted Similarity
Implement similarity scoring that accounts for:
- Section type compatibility
- Semantic distance
- Ontology concept overlap (Phase 4)

## Phase 4: Ontology Integration (Week 5-6)

### 4.1 Concept Extraction Pipeline
```python
def extract_ontology_concepts(section_text, section_type):
    """Extract ontology concepts relevant to section"""
    # Use LLM to identify:
    # - Ethical principles mentioned
    # - Professional obligations
    # - Stakeholders involved
    # - Actions/decisions described
    
    # Map to ontology entities
    # Store as metadata with embedding
```

### 4.2 Hybrid Similarity
Combine embedding similarity with ontology-based similarity:
```python
similarity_score = (
    0.7 * embedding_similarity +
    0.3 * ontology_concept_overlap
)
```

### 4.3 Concept-Based Filtering
Enable searches like:
- "Find facts involving conflict of interest"
- "Find discussions about public safety"
- "Find conclusions related to professional integrity"

## Implementation Checklist

### Immediate Actions
- [ ] Fix the current error handling in section embedding generation
- [ ] Update DocumentSection model for granular storage
- [ ] Modify section parser to extract individual items
- [ ] Create embedding generation for individual items

### Week 1-2
- [ ] Implement type-specific similarity endpoints
- [ ] Add UI components for similarity search
- [ ] Create database indexes for performance

### Week 3-4
- [ ] Design cross-section relationship rules
- [ ] Implement weighted similarity scoring
- [ ] Add cross-section search UI

### Week 5-6
- [ ] Integrate ontology concept extraction
- [ ] Implement hybrid similarity scoring
- [ ] Add concept-based search filters

## Success Metrics
1. **Granularity**: Ability to search at fact_1, question_1 level
2. **Accuracy**: Improved relevance in similarity results
3. **Performance**: <500ms response time for similarity queries
4. **Ontology Coverage**: 80%+ of sections have extracted concepts

## Technical Considerations

### Embedding Model Selection
Consider upgrading from MiniLM-L6-v2 (384d) to:
- `all-mpnet-base-v2` (768d) - Better quality, moderate size
- `instructor-large` (768d) - Instruction-following embeddings
- Domain-specific fine-tuned model for ethics/engineering

### Storage Optimization
- Use pgvector's HNSW indexing for fast similarity search
- Consider partitioning by section_type for large datasets
- Implement embedding caching for frequently accessed sections

### API Design
```python
# Granular similarity search
POST /api/embeddings/similarity
{
    "text": "The engineer disclosed confidential information",
    "section_type": "fact",  # Optional filter
    "cross_section_types": ["discussion", "conclusion"],  # Optional
    "min_similarity": 0.7,
    "limit": 10,
    "ontology_concepts": ["confidentiality", "disclosure"]  # Optional
}
```

## Next Steps
1. Review and approve this plan
2. Set up development branch for embedding enhancements
3. Begin Phase 1 implementation
4. Create test cases for section-level similarity
5. Document API changes for frontend integration