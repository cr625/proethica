-- Diagnostic script to understand guideline triple issues
-- This will show why "Other Guidelines" appear when there's only one guideline

BEGIN;

-- 1. Show all guidelines in the database
SELECT 'All Guidelines in Database:' as info;
SELECT id, title, world_id, 
       guideline_metadata->>'document_id' as document_id,
       created_at
FROM guidelines
ORDER BY id;

-- 2. Show all documents that might be guidelines
SELECT 'Documents with guideline_id in metadata:' as info;
SELECT id, title, document_type, 
       doc_metadata->>'guideline_id' as guideline_id_in_metadata,
       created_at
FROM documents
WHERE doc_metadata->>'guideline_id' IS NOT NULL
ORDER BY id;

-- 3. Count guideline concept triples by their guideline_id
SELECT 'Guideline concept triples grouped by guideline_id:' as info;
SELECT 
    guideline_id,
    COUNT(*) as triple_count,
    COUNT(DISTINCT subject) as unique_subjects
FROM entity_triples
WHERE entity_type = 'guideline_concept'
GROUP BY guideline_id
ORDER BY guideline_id;

-- 4. Check for triples with guideline_id in metadata
SELECT 'Triples with guideline_id in doc_metadata:' as info;
SELECT 
    (doc_metadata->>'guideline_id')::INTEGER as metadata_guideline_id,
    COUNT(*) as triple_count
FROM entity_triples
WHERE entity_type = 'guideline_concept'
  AND doc_metadata->>'guideline_id' IS NOT NULL
GROUP BY (doc_metadata->>'guideline_id')::INTEGER
ORDER BY metadata_guideline_id;

-- 5. Find mismatches between guideline_id and metadata guideline_id
SELECT 'Triples with mismatched guideline IDs:' as info;
SELECT 
    id,
    guideline_id as direct_guideline_id,
    (doc_metadata->>'guideline_id')::INTEGER as metadata_guideline_id,
    subject,
    predicate,
    object
FROM entity_triples
WHERE entity_type = 'guideline_concept'
  AND guideline_id IS NOT NULL
  AND doc_metadata->>'guideline_id' IS NOT NULL
  AND guideline_id != (doc_metadata->>'guideline_id')::INTEGER
LIMIT 10;

-- 6. Show all unique guideline IDs referenced in triples
SELECT 'All unique guideline IDs referenced in triples:' as info;
SELECT DISTINCT
    COALESCE(guideline_id, (doc_metadata->>'guideline_id')::INTEGER) as referenced_guideline_id,
    CASE 
        WHEN guideline_id IS NOT NULL AND doc_metadata->>'guideline_id' IS NULL THEN 'direct only'
        WHEN guideline_id IS NULL AND doc_metadata->>'guideline_id' IS NOT NULL THEN 'metadata only'
        WHEN guideline_id = (doc_metadata->>'guideline_id')::INTEGER THEN 'both (matching)'
        ELSE 'both (mismatched)'
    END as reference_type,
    COUNT(*) as triple_count
FROM entity_triples
WHERE entity_type = 'guideline_concept'
GROUP BY COALESCE(guideline_id, (doc_metadata->>'guideline_id')::INTEGER), reference_type
ORDER BY referenced_guideline_id;

-- 7. For document 190, check what guideline_id it references
SELECT 'Document 190 details:' as info;
SELECT id, title, document_type, 
       doc_metadata->>'guideline_id' as guideline_id_in_metadata,
       doc_metadata
FROM documents
WHERE id = 190;

-- 8. Show sample triples for each guideline_id
SELECT 'Sample triples for each guideline_id:' as info;
WITH guideline_samples AS (
    SELECT DISTINCT ON (COALESCE(guideline_id, (doc_metadata->>'guideline_id')::INTEGER))
        COALESCE(guideline_id, (doc_metadata->>'guideline_id')::INTEGER) as gid,
        id, subject, predicate, object, guideline_id,
        doc_metadata->>'guideline_id' as metadata_guideline_id
    FROM entity_triples
    WHERE entity_type = 'guideline_concept'
    ORDER BY COALESCE(guideline_id, (doc_metadata->>'guideline_id')::INTEGER), id
)
SELECT * FROM guideline_samples ORDER BY gid;

ROLLBACK;