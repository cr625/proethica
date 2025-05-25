# Section-Triple Association Implementation

## Overview

The Section-Triple Association system connects document sections with relevant ontology concepts to enhance semantic understanding and enable ontology-based reasoning. This system was implemented to bridge the gap between unstructured document content and structured ontological knowledge.

## Architecture

### Core Components

1. **OntologyTripleLoader** - Loads ontology concepts directly from TTL files
2. **SectionTripleAssociator** - Implements embedding-based two-phase matching algorithm
3. **LLMSectionTripleAssociator** - Implements LLM-based semantic matching
4. **SectionTripleAssociationStorage** - Handles database operations
5. **SectionTripleAssociationService** - Coordinates the entire process
6. **CLI Interface** - Provides batch processing capabilities

### Database Schema

```sql
section_triple_association (
  id SERIAL PRIMARY KEY,
  section_id INTEGER REFERENCES document_sections(id),
  triple_subject TEXT NOT NULL,
  triple_predicate TEXT NOT NULL,
  triple_object TEXT NOT NULL,
  similarity_score FLOAT NOT NULL,
  match_confidence FLOAT NOT NULL,
  match_type VARCHAR(50) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

## Implementation Details

### Two Matching Approaches

#### 1. Embedding-Based Association
- **Coarse Matching**: Uses vector similarity between section embeddings and concept embeddings
- **Fine-Grained Matching**: Refines results using semantic properties and section context
- **Similarity Threshold**: Configurable (default 0.6, often lowered to 0.5 for better coverage)

#### 2. LLM-Based Association
- **Multi-Metric Approach**: Combines vector similarity, term overlap, structural relevance, and LLM assessment
- **Semantic Understanding**: Leverages LLM's ability to understand context and meaning
- **Reasoning Output**: Provides explanations for why concepts are relevant

### Section Embedding Storage

Embeddings are stored using PostgreSQL's pgvector extension:
```python
# Store embedding with direct string formatting
query = text(f"""
    UPDATE document_sections 
    SET embedding = '{embedding_str}'::vector
    WHERE id = :section_id
""")
```

### Integration Points

1. **Document Structure Pipeline**: Associations generated after section embeddings
2. **UI Integration**: Routes in `document_structure.py` handle association requests
3. **Batch Processing**: CLI tools for processing multiple documents

## Usage

### Via Web UI
1. Navigate to document structure view
2. Click "Associate Ontology Concepts" 
3. Select method (embedding-based or LLM-based)
4. View results with match scores and reasoning

### Via CLI
```bash
# Using embedding-based approach
./run_section_triple_association.sh

# Using LLM-based approach
./run_llm_section_triple_association.sh
```

### Programmatic Usage
```python
from ttl_triple_association import SectionTripleAssociationService

service = SectionTripleAssociationService(db_session)
associations = service.associate_sections_with_triples(
    document_id=123,
    method='llm',  # or 'embedding'
    similarity_threshold=0.5
)
```

## Configuration

### Similarity Thresholds
- **Default**: 0.6 (conservative, fewer but more confident matches)
- **Recommended**: 0.5 (balanced coverage and relevance)
- **Exploratory**: 0.4 (more matches, may include less relevant concepts)

### LLM Configuration
- Uses the application's configured LLM service
- Prompts are customizable in `llm_section_triple_associator.py`

## Known Issues and Solutions

1. **Transaction Handling**: Fixed by creating new connections for batch operations
2. **Type Casting**: Resolved string formatting issues with vector storage
3. **Coverage**: LLM-based approach provides better coverage than pure embedding approach

## Performance Considerations

- Embedding generation: ~100ms per section
- Association calculation: ~50ms per section (embedding), ~500ms per section (LLM)
- Batch processing recommended for large document sets

## Future Enhancements

1. **Hybrid Approach**: Combine embedding and LLM methods for optimal results
2. **Caching**: Cache LLM responses for repeated analyses
3. **Concept Filtering**: UI improvements for filtering by concept type
4. **Visualization**: Network graphs showing section-concept relationships