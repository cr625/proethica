# Section-Triple Association Implementation Guide

This document consolidates the implemented section-triple association functionality in the ProEthica system, which links document sections to ontology concepts using both embedding-based and LLM-based approaches.

## Overview

The section-triple association system enables linking case document sections (facts, questions, discussion, etc.) to relevant ontology concepts from ProEthica's knowledge base. This association enhances the system's ability to perform ontology-based reasoning in experiments.

## Architecture

### Core Components

1. **SectionTripleAssociationService** (`ttl_triple_association/section_triple_association_service.py`)
   - Main service orchestrating both embedding and LLM-based associations
   - Manages retrieval and storage of associations

2. **SectionEmbeddingService** (`app/services/section_embedding_service.py`)
   - Generates and stores 384-dimensional embeddings using MiniLM-L6-v2
   - Stores embeddings in DocumentSection table with pgvector

3. **LLM Section-Triple Associator** (`ttl_triple_association/llm_section_triple_associator.py`)
   - Uses Claude API for intelligent concept matching
   - Provides semantic understanding beyond simple similarity

4. **Ontology Triple Loader** (`ttl_triple_association/ontology_triple_loader.py`)
   - Loads triples directly from TTL files
   - Parses engineering-ethics.ttl, proethica-intermediate.ttl, and bfo.ttl

### Storage

Associations are stored in the `section_triple_associations` table:
```sql
CREATE TABLE section_triple_associations (
    id SERIAL PRIMARY KEY,
    section_id INTEGER REFERENCES document_sections(id),
    triple_subject TEXT NOT NULL,
    triple_predicate TEXT NOT NULL,
    triple_object TEXT NOT NULL,
    association_score FLOAT,
    association_method VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Implementation Details

### Embedding-Based Approach
- Generates embeddings for both sections and triple components
- Calculates cosine similarity between vectors
- Fast but limited to surface-level similarity
- Typical threshold: 0.7 for meaningful associations

### LLM-Based Approach
- Analyzes section content and triple meaning
- Understands context and implicit relationships
- Provides explanations for associations
- Better coverage (~3x more associations than embedding-only)

### Hybrid Strategy
The system uses both approaches:
1. Quick embedding-based matching for obvious connections
2. LLM analysis for deeper semantic understanding
3. Deduplication and scoring normalization
4. Final associations stored with method attribution

## Usage

### Via Web Interface
1. Navigate to case detail page
2. Click "Update Document Structure"
3. System automatically generates section embeddings
4. Associations created using hybrid approach

### Via CLI
```bash
# Generate associations for a specific document
python ttl_triple_association/cli.py associate --document-id 252

# Use LLM-only approach
python ttl_triple_association/cli.py associate --document-id 252 --method llm

# List associations
python ttl_triple_association/cli.py list --document-id 252
```

### Programmatic Usage
```python
from ttl_triple_association.section_triple_association_service import SectionTripleAssociationService

service = SectionTripleAssociationService()

# Get associations for a section
associations = service.get_section_associations(section_id=123)

# Generate new associations
service.generate_associations_for_document(document_id=252)
```

## Configuration

### Environment Variables
- `ANTHROPIC_API_KEY`: Required for LLM-based association
- `DATABASE_URL`: PostgreSQL connection with pgvector extension

### Ontology Files
Located in `/ontologies/`:
- `engineering-ethics.ttl`: Domain-specific engineering concepts
- `proethica-intermediate.ttl`: Core ethical reasoning concepts
- `bfo.ttl`: Upper-level ontology (Basic Formal Ontology)

## Performance Characteristics

### Embedding-Based
- Speed: ~1-2 seconds per document
- Coverage: ~15-20% of relevant concepts
- Accuracy: High precision, lower recall

### LLM-Based
- Speed: ~30-60 seconds per document
- Coverage: ~45-60% of relevant concepts
- Accuracy: Good precision and recall

### Storage
- Embeddings: 384 dimensions × 4 bytes = 1.5KB per section
- Associations: ~50-200 per document depending on content

## Integration with Experiments

The prediction service uses associations to enhance prompts:
```python
# In prediction_service.py
associations = self.triple_association_service.get_section_associations(section_id)
if associations:
    # Include top associations in prompt
    for assoc in associations[:10]:
        prompt += f"\n- {assoc['subject']} {assoc['predicate']} {assoc['object']}"
```

## Known Issues and Solutions

1. **Duplicate Associations**
   - Issue: Same triple associated multiple times
   - Solution: Deduplication in service layer

2. **Performance with Large Documents**
   - Issue: LLM timeouts on very long sections
   - Solution: Section chunking, max 2000 tokens per request

3. **Ontology Updates**
   - Issue: Associations become stale when ontology changes
   - Solution: Regeneration triggered on ontology file modification

## Future Enhancements

1. **Confidence Scoring**: Implement multi-model voting for association confidence
2. **Active Learning**: Use experiment feedback to improve associations
3. **Caching**: Redis-based caching for frequently accessed associations
4. **Batch Processing**: Parallel processing for multiple documents