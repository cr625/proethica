# Embeddings Troubleshooting Guide

This guide addresses common issues with the embeddings system and provides solutions for typical problems.

## Common Errors

### 1. "'str' object has no attribute 'keys'" Error

**Error**: `AttributeError: 'str' object has no attribute 'keys'`

**Cause**: Document metadata is stored as a string instead of a dictionary object, typically from legacy data or JSON serialization issues.

**Location**: `SectionEmbeddingService.process_document_sections()`

**Solution**: 
The error has been fixed in the latest version of `section_embedding_service.py`. The service now properly handles both string and dictionary metadata formats.

**Manual Fix (if needed)**:
```python
# In process_document_sections method
if isinstance(document.doc_metadata, dict):
    doc_metadata = document.doc_metadata
elif isinstance(document.doc_metadata, str):
    try:
        import json
        doc_metadata = json.loads(document.doc_metadata)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Failed to parse document metadata as JSON: {e}")
        doc_metadata = {}
else:
    doc_metadata = {}
```

**Prevention**: Ensure all document metadata is stored as JSON in the database, not serialized strings.

### 2. "No section data found" Error

**Error**: `No section data found in document metadata`

**Cause**: Document hasn't been processed through the structure annotation pipeline, or section data is in an unexpected format.

**Solution**:
1. First run "Generate Document Structure" on the case
2. Verify the document has `sections_dual` or `sections` in metadata
3. Check that sections contain actual content (not empty strings)

**Debug Steps**:
```python
# Check document metadata structure
document = Document.query.get(document_id)
print(f"Metadata keys: {document.doc_metadata.keys()}")
print(f"Has sections_dual: {'sections_dual' in document.doc_metadata}")
print(f"Has document_structure: {'document_structure' in document.doc_metadata}")
```

### 3. "Model loading timeout" Error

**Error**: `Timeout loading SentenceTransformers model`

**Cause**: Local embedding model download or loading takes too long, especially on first run.

**Solution**:
1. **Increase timeout**: Set environment variable `MODEL_LOADING_TIMEOUT=300`
2. **Pre-download models**: Run model download script before first use
3. **Use API provider**: Switch to OpenAI or Claude APIs for faster startup

**Model Pre-download**:
```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### 4. "pgvector extension not available" Error

**Error**: `pgvector extension is not available`

**Cause**: PostgreSQL database doesn't have the pgvector extension installed or enabled.

**Solution**:
1. **Install pgvector**: `CREATE EXTENSION IF NOT EXISTS vector;`
2. **Check installation**: `SELECT * FROM pg_extension WHERE extname = 'vector';`
3. **Fallback mode**: System will use Python-based similarity if pgvector unavailable

**Installation Commands**:
```sql
-- Connect as superuser
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify installation
\dx vector
```

### 5. "Embedding dimension mismatch" Error

**Error**: `Embedding dimension mismatch: expected 384, got 1536`

**Cause**: Database schema expects 384-dimensional vectors but embedding provider returns different dimensions.

**Solution**:
1. **Check provider configuration**: Verify `EMBEDDING_PROVIDER_PRIORITY` setting
2. **Update schema**: Migrate database to support new dimensions
3. **Force provider**: Set single provider in environment

**Schema Migration**:
```sql
-- For OpenAI embeddings (1536 dimensions)
ALTER TABLE document_sections ALTER COLUMN embedding TYPE vector(1536);

-- Update index
DROP INDEX document_sections_embedding_idx;
CREATE INDEX document_sections_embedding_idx ON document_sections 
    USING ivfflat (embedding vector_cosine_ops);
```

## Performance Issues

### Slow Embedding Generation

**Symptoms**: Taking >10 seconds per section to generate embeddings

**Causes & Solutions**:

1. **CPU-bound local model**
   - Solution: Use GPU acceleration or switch to API provider
   - Check: `nvidia-smi` for GPU availability

2. **Memory pressure**
   - Solution: Reduce batch size or restart application
   - Check: Monitor memory usage during processing

3. **Model reloading**
   - Solution: Implement model caching or persistent model loading
   - Fix: Keep model in memory between requests

### Database Query Performance

**Symptoms**: Slow similarity search queries (>2 seconds)

**Solutions**:
1. **Rebuild pgvector index**: 
   ```sql
   REINDEX INDEX document_sections_embedding_idx;
   ```

2. **Adjust index parameters**:
   ```sql
   DROP INDEX document_sections_embedding_idx;
   CREATE INDEX document_sections_embedding_idx ON document_sections 
       USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
   ```

3. **Update table statistics**:
   ```sql
   ANALYZE document_sections;
   ```

## Data Issues

### Missing Embeddings

**Symptoms**: Sections exist but no embeddings generated

**Debug Steps**:
```python
# Check for sections without embeddings
from app.models import Document, DocumentSection

document = Document.query.get(document_id)
sections = DocumentSection.query.filter_by(document_id=document_id).all()

print(f"Total sections: {len(sections)}")
sections_with_embeddings = [s for s in sections if s.embedding is not None]
print(f"Sections with embeddings: {len(sections_with_embeddings)}")
```

**Solution**: Re-run embedding generation for affected documents.

### Inconsistent Section Types

**Symptoms**: Embeddings exist but similarity search returns unexpected results

**Cause**: Mixed section types (facts vs discussion) being compared inappropriately

**Solution**: Filter similarity search by section type:
```python
similar_sections = section_service.search_similar_sections(
    query_embedding, 
    section_type='facts',  # Specify type
    threshold=0.7
)
```

## API Provider Issues

### OpenAI API Errors

**Error**: `OpenAI API rate limit exceeded`

**Solution**:
1. **Reduce batch size**: Set `EMBEDDING_BATCH_SIZE=10`
2. **Add retry logic**: Implement exponential backoff
3. **Switch provider**: Use local model as fallback

**Rate Limit Handling**:
```python
import time
import random

def generate_with_retry(texts, max_retries=3):
    for attempt in range(max_retries):
        try:
            return openai_client.embeddings.create(input=texts)
        except openai.RateLimitError:
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait_time)
    raise Exception("Max retries exceeded")
```

### Claude API Errors

**Error**: `Claude API authentication failed`

**Solution**:
1. **Verify API key**: Check `ANTHROPIC_API_KEY` environment variable
2. **Check quotas**: Ensure account has sufficient usage quota
3. **Test connection**: Verify API key with simple request

## Configuration Issues

### Environment Variables Not Loaded

**Symptoms**: Default local model used despite API configuration

**Solution**:
1. **Check variable names**: Verify exact spelling of environment variables
2. **Restart application**: Ensure variables loaded at startup
3. **Test in shell**: Verify variables accessible in runtime environment

**Debug Commands**:
```bash
# Check environment variables
echo $EMBEDDING_PROVIDER_PRIORITY
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY

# Test in Python
import os
print(os.environ.get('EMBEDDING_PROVIDER_PRIORITY', 'NOT SET'))
```

### Model Cache Issues

**Symptoms**: Model re-downloads on every restart

**Solution**:
1. **Set cache directory**: `TRANSFORMERS_CACHE=/app/models/cache`
2. **Persistent storage**: Ensure cache directory persists across restarts
3. **Pre-populate cache**: Download models during container build

## Monitoring and Diagnostics

### Enable Debug Logging

```python
import logging
logging.getLogger('app.services.embedding_service').setLevel(logging.DEBUG)
logging.getLogger('app.services.section_embedding_service').setLevel(logging.DEBUG)
```

### Health Check Queries

```sql
-- Check embedding coverage
SELECT 
    d.id,
    d.title,
    COUNT(ds.id) as sections_count,
    COUNT(ds.embedding) as embeddings_count
FROM documents d
LEFT JOIN document_sections ds ON d.id = ds.document_id
WHERE d.document_type IN ('case', 'case_study')
GROUP BY d.id, d.title
HAVING COUNT(ds.embedding) = 0;

-- Check embedding quality
SELECT 
    section_type,
    AVG(array_length(embedding::float[], 1)) as avg_dimensions,
    COUNT(*) as count
FROM document_sections 
WHERE embedding IS NOT NULL
GROUP BY section_type;
```

### Performance Monitoring

```python
import time
import psutil

def monitor_embedding_performance():
    start_time = time.time()
    memory_before = psutil.Process().memory_info().rss / 1024 / 1024  # MB
    
    # Generate embeddings
    embedding_service = EmbeddingService()
    embeddings = embedding_service.generate_embeddings_batch(texts)
    
    end_time = time.time()
    memory_after = psutil.Process().memory_info().rss / 1024 / 1024  # MB
    
    print(f"Time: {end_time - start_time:.2f}s")
    print(f"Memory delta: {memory_after - memory_before:.2f}MB")
    print(f"Throughput: {len(texts) / (end_time - start_time):.2f} texts/sec")
```

## Getting Help

If you encounter issues not covered in this guide:

1. **Check logs**: Look for detailed error messages in application logs
2. **Verify configuration**: Ensure all required environment variables are set
3. **Test components**: Isolate issues by testing individual components
4. **Update documentation**: Consider adding new issues to this guide

For additional assistance, consult the other documentation files:
- [current_implementation.md](current_implementation.md) for technical details
- [improvement_plan.md](improvement_plan.md) for known limitations and planned fixes