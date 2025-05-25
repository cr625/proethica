# PGVector Native Query Implementation

## Overview
The system uses PostgreSQL's pgvector extension for efficient similarity searches on embedding vectors.

## Native Query Implementation
The native pgvector query uses:
- PostgreSQL array format for vectors: `[1.0,2.0,3.0,...]`
- CAST operator for type conversion: `CAST(:param AS vector)`
- Cosine distance operator: `<=>` (returns 0 for identical vectors)
- Proper parameter binding with SQLAlchemy's `text()` function

## Query Pattern
```sql
SELECT 
    ds.embedding <=> CAST(:query_embedding AS vector) AS similarity
FROM 
    document_sections ds
WHERE 
    ds.embedding IS NOT NULL
ORDER BY 
    similarity ASC
```

## Fixes Applied
1. Changed from `::vector` casting to `CAST(:param AS vector)` for better compatibility
2. Removed unnecessary transaction block that was interfering with parameter binding
3. Properly format embeddings as PostgreSQL array strings
4. Use SQLAlchemy's text() for raw SQL execution

## Performance Benefits
- Utilizes PostgreSQL's optimized vector operations
- Leverages pgvector's indexing capabilities
- Scales efficiently with large datasets
- No need to load all embeddings into Python memory

## Fallback Strategy
The Python fallback remains as a safety net but should rarely be needed with the fixed implementation.