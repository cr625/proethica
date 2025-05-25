# Current Embeddings Implementation

This document provides detailed technical information about the current embeddings implementation in the AI Ethical DM application.

## Technical Architecture

### Embedding Models

**Primary Model: all-MiniLM-L6-v2**
- **Dimensions**: 384
- **Provider**: SentenceTransformers (local)
- **Model Size**: ~90MB
- **Performance**: ~1000 tokens/second on CPU
- **Strengths**: Fast, lightweight, general-purpose
- **Limitations**: Small dimension space, not domain-specialized

**Alternative Providers**
```python
# Configuration priority
EMBEDDING_PROVIDER_PRIORITY = "local,openai,claude"

# Provider specifications
"local": all-MiniLM-L6-v2 (384 dims)
"openai": text-embedding-ada-002 (1536 dims) 
"claude": anthropic embeddings (1024 dims)
```

### Database Schema

**document_sections Table**
```sql
CREATE TABLE document_sections (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    section_id VARCHAR(255),
    section_type VARCHAR(100),
    content TEXT,
    embedding vector(384),  -- pgvector type
    section_metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(document_id, section_id)
);

-- Indexes for efficient similarity search
CREATE INDEX document_sections_embedding_idx ON document_sections 
    USING ivfflat (embedding vector_cosine_ops);
```

**Metadata Structure**
```json
{
    "section_type": "facts|discussion|conclusion|references",
    "word_count": 250,
    "processed_at": "2025-01-15T10:30:00Z",
    "embedding_model": "all-MiniLM-L6-v2",
    "embedding_provider": "local",
    "content_hash": "sha256:abc123...",
    "source_document_uri": "http://proethica.org/cases/123"
}
```

## Service Implementation

### EmbeddingService (`app/services/embedding_service.py`)

**Core Methods**
```python
class EmbeddingService:
    def generate_embedding(self, text: str) -> List[float]
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]
    def search_similar_chunks(self, query: str, k: int = 10) -> List[Dict]
    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float
```

**Text Preprocessing Pipeline**
1. **URI Removal**: Strip `<http://...>` patterns
2. **XML Cleaning**: Remove XML tags and attributes  
3. **Token Filtering**: Remove formatting tokens like `@en`, `^^xsd:string`
4. **Whitespace Normalization**: Collapse multiple spaces
5. **Length Validation**: Ensure content meets minimum length requirements

**Provider Management**
```python
def _get_embedding_provider(self):
    """Select embedding provider based on environment configuration."""
    providers = os.environ.get('EMBEDDING_PROVIDER_PRIORITY', 'local').split(',')
    
    for provider in providers:
        if provider == 'local' and self._check_local_model():
            return LocalEmbeddingProvider()
        elif provider == 'openai' and self._check_openai_api():
            return OpenAIEmbeddingProvider()
        elif provider == 'claude' and self._check_claude_api():
            return ClaudeEmbeddingProvider()
    
    raise Exception("No embedding provider available")
```

### SectionEmbeddingService (`app/services/section_embedding_service.py`)

**Section Processing Workflow**
```python
def process_document_sections(self, document_id: int) -> Dict[str, Any]:
    """
    1. Retrieve document and validate metadata structure
    2. Extract sections from document_structure or sections_dual
    3. Generate embeddings for each section
    4. Store in document_sections table with metadata
    5. Update document metadata with embedding counts
    """
```

**Section Extraction Logic**
```python
# Priority order for section data sources
if 'document_structure' in metadata and 'sections' in metadata['document_structure']:
    sections = metadata['document_structure']['sections']
elif 'sections_dual' in metadata:
    # Use text version for embeddings, HTML for display
    sections = {k: v.get('text', v.get('html', '')) for k, v in metadata['sections_dual'].items()}
elif 'sections' in metadata:
    sections = metadata['sections']
else:
    return {"error": "No section data found"}
```

## Integration Points

### Document Structure View
**Template**: `app/templates/document_structure.html`
**Route**: `/structure/view/<int:id>`

**"Generate Section Embeddings" Button**
```html
<button onclick="generateSectionEmbeddings({{ case.id }})" class="btn btn-primary">
    <i class="bi bi-cpu"></i> Generate Section Embeddings
</button>
```

**JavaScript Handler**
```javascript
async function generateSectionEmbeddings(documentId) {
    try {
        const response = await fetch(`/api/embeddings/sections/${documentId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        
        if (response.ok) {
            const result = await response.json();
            showSuccess(`Generated embeddings for ${result.sections_processed} sections`);
            location.reload(); // Refresh to show embedding counts
        } else {
            const error = await response.json();
            showError(`Error: ${error.message}`);
        }
    } catch (error) {
        showError(`Network error: ${error.message}`);
    }
}
```

### Similarity Search Integration

**Case Repository Search** (`app/routes/cases.py`)
```python
@cases_bp.route('/search', methods=['GET'])
def search_cases():
    # Use embedding service for semantic search
    embedding_service = EmbeddingService()
    similar_chunks = embedding_service.search_similar_chunks(
        query=query,
        k=10,
        world_id=world_id,
        document_type=['case_study', 'case']
    )
```

**Related Cases Discovery**
```python
def find_related_cases_by_embeddings(case_id: int, similarity_threshold: float = 0.7):
    """Find cases with similar section content using embeddings."""
    section_service = SectionEmbeddingService()
    
    # Get embeddings for source case sections
    source_sections = section_service.get_document_sections(case_id)
    
    # Find similar sections across all cases
    related_cases = []
    for section in source_sections:
        similar_sections = section_service.search_similar_sections(
            section.embedding, threshold=similarity_threshold
        )
        related_cases.extend(similar_sections)
    
    return group_by_case_and_rank(related_cases)
```

## Performance Characteristics

### Embedding Generation
- **Local Model Loading**: ~2-3 seconds initial load
- **Per-Section Generation**: ~50-100ms for typical section (200-500 words)
- **Batch Processing**: ~30% faster than individual processing
- **Memory Usage**: ~500MB for loaded SentenceTransformers model

### Storage Requirements
- **Vector Storage**: 384 floats × 4 bytes = ~1.5KB per embedding
- **Typical Case**: 5-8 sections × 1.5KB = ~7.5-12KB per case
- **Large Repository**: 1000 cases = ~7.5-12MB vector storage

### Query Performance
- **pgvector Index**: IVFFlat with cosine distance
- **Similarity Search**: <50ms for k=10 nearest neighbors
- **Full-Text Fallback**: ~200-500ms when pgvector unavailable
- **Index Build**: ~1-2 minutes for 10,000 embeddings

## Configuration Options

### Environment Variables
```bash
# Embedding provider priority (comma-separated)
EMBEDDING_PROVIDER_PRIORITY=local,openai,claude

# Local model settings
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2
EMBEDDING_CACHE_DIR=/app/models/cache

# API provider settings
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
EMBEDDING_BATCH_SIZE=32

# Database settings
PGVECTOR_ENABLED=true
SIMILARITY_SEARCH_LIMIT=50
DEFAULT_SIMILARITY_THRESHOLD=0.7
```

### Model Configuration
```python
# app/services/embedding_service.py
MODEL_CONFIGS = {
    'all-MiniLM-L6-v2': {
        'dimensions': 384,
        'max_sequence_length': 256,
        'model_size': '90MB',
        'speed': 'fast'
    },
    'all-mpnet-base-v2': {
        'dimensions': 768, 
        'max_sequence_length': 384,
        'model_size': '420MB',
        'speed': 'medium'
    }
}
```

## Known Issues and Limitations

### Current Bugs
1. **Metadata String Error**: `'str' object has no attribute 'keys'` when document metadata is stored as string instead of JSON
2. **Model Loading Timeout**: Occasional timeouts when loading SentenceTransformers model
3. **Memory Leaks**: Model not properly released in some error conditions
4. **Batch Size Limits**: Large batches can cause out-of-memory errors

### Design Limitations
1. **Fixed Dimensions**: Database schema locked to 384 dimensions
2. **Single Model**: No A/B testing or model comparison capabilities
3. **No Versioning**: Embeddings not versioned when models change
4. **Limited Metadata**: Insufficient tracking of embedding generation context

### Performance Bottlenecks
1. **Sequential Processing**: Each section processed individually
2. **Model Reloading**: Model loaded fresh for each embedding request
3. **Synchronous API**: No async processing for large documents
4. **Index Rebuilding**: pgvector index rebuilt completely when adding vectors

See [troubleshooting.md](troubleshooting.md) for specific error resolution and [improvement_plan.md](improvement_plan.md) for planned enhancements.