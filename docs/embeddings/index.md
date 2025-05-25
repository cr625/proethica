# Embeddings System Overview

The AI Ethical DM application uses vector embeddings to enable semantic similarity search across case documents and sections. This system allows for nuanced comparisons of ethical scenarios based on meaning rather than just keyword matching.

## System Architecture

### Core Components

**Embedding Services**
- `EmbeddingService` - Base service for generating embeddings from text
- `SectionEmbeddingService` - Specialized service for document section embeddings

**Storage Infrastructure**
- PostgreSQL database with pgvector extension
- `document_sections` table with Vector(384) column
- Efficient similarity search using pgvector operators

**Multiple Provider Support**
- Local: SentenceTransformers (`all-MiniLM-L6-v2`)
- API: OpenAI (`text-embedding-ada-002`) 
- API: Claude (via Anthropic API)

## Current Capabilities

### Embedding Generation
- **Section-Level Embeddings**: Generate embeddings for facts, discussion, conclusions, etc.
- **Content Preprocessing**: Automatic cleaning of URIs, XML tags, and formatting
- **Batch Processing**: Process multiple sections efficiently
- **Metadata Integration**: Store section metadata alongside embeddings

### Similarity Search
- **Cross-Case Comparison**: Find similar sections across different cases
- **Thematic Clustering**: Group related ethical concepts and arguments
- **Guideline Association**: Link case sections to relevant ethical guidelines
- **Distance Metrics**: Cosine similarity via pgvector native operators

### Provider Flexibility
- **Configurable Priority**: Environment variable controls provider selection
- **Fallback Mechanisms**: Graceful degradation if preferred provider fails
- **Dimension Adaptation**: Handles different embedding dimensions (384, 1024, 1536)

## Integration Points

### Document Processing Pipeline
1. Case import and section parsing
2. Document structure annotation with RDF triples
3. **Section embedding generation** ← Current focus
4. Guideline association based on similarity
5. Storage in searchable format

### User Interface Integration
- "Generate Section Embeddings" button on structure view
- Similarity search in case repository
- Related cases suggestions
- Guideline recommendations

### Data Flow
```
Document Sections → Text Extraction → Embedding Model → Vector Storage → Similarity Search
     ↓                    ↓               ↓              ↓              ↓
Case Content → Clean Text → 384-dim Vector → PostgreSQL → Related Content
```

## Current Limitations

### Model Constraints
- **Small Embedding Dimension**: 384 dimensions may miss nuanced relationships
- **General Domain Model**: Not specialized for ethics/engineering terminology
- **Limited Context Window**: May truncate long section content

### Performance Considerations
- **Sequential Processing**: Embeddings generated one section at a time
- **Local Model Latency**: SentenceTransformers model loading overhead
- **Storage Overhead**: Vector storage requires significant disk space

### Feature Gaps
- **No Visualization**: Limited insight into embedding relationships
- **Basic Similarity**: Simple cosine distance without re-ranking
- **No Clustering**: Missing automatic grouping of similar concepts
- **Limited Analytics**: No embedding quality metrics or drift detection

## Strategic Value

### Research Applications
- **Pattern Recognition**: Identify recurring ethical themes across cases
- **Precedent Analysis**: Find cases with similar factual circumstances
- **Principle Application**: Understand how ethical rules apply in practice
- **Comparative Studies**: Analyze decision patterns across time periods

### Practical Benefits
- **Case Discovery**: Lawyers and ethicists find relevant precedents quickly
- **Consistency Checking**: Identify potential conflicts in ethical determinations
- **Knowledge Management**: Organize large case repositories semantically
- **Decision Support**: Surface similar cases during ethical review processes

## Next Steps

The embeddings system provides a solid foundation but has significant room for improvement. Priority areas include:

1. **Model Upgrades**: Larger, more capable embedding models
2. **API Integration**: Leverage high-quality commercial embedding APIs  
3. **Visualization Tools**: Interactive exploration of embedding spaces
4. **Performance Optimization**: Batch processing and caching improvements
5. **Domain Specialization**: Fine-tuning for ethics and engineering terminology

See [improvement_plan.md](improvement_plan.md) for detailed enhancement roadmap.