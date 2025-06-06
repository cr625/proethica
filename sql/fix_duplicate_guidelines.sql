-- SQL script to fix duplicate guidelines pointing to the same document
-- This consolidates multiple guideline records into one per document

BEGIN;

-- 1. Show the current situation
SELECT 'Current Guidelines and their Documents:' as info;
SELECT 
    g.id as guideline_id,
    g.title as guideline_title,
    g.guideline_metadata->>'document_id' as document_id,
    d.title as document_title,
    g.created_at
FROM guidelines g
LEFT JOIN documents d ON d.id = (g.guideline_metadata->>'document_id')::INTEGER
ORDER BY (g.guideline_metadata->>'document_id')::INTEGER, g.created_at;

-- 2. Find documents with multiple guidelines
SELECT 'Documents with multiple guidelines:' as info;
WITH duplicate_guidelines AS (
    SELECT 
        (guideline_metadata->>'document_id')::INTEGER as document_id,
        COUNT(*) as guideline_count,
        MIN(id) as oldest_guideline_id,
        MAX(id) as newest_guideline_id,
        STRING_AGG(id::TEXT, ', ' ORDER BY id) as all_guideline_ids
    FROM guidelines
    WHERE guideline_metadata->>'document_id' IS NOT NULL
    GROUP BY (guideline_metadata->>'document_id')::INTEGER
    HAVING COUNT(*) > 1
)
SELECT * FROM duplicate_guidelines;

-- 3. For each document with multiple guidelines, keep the newest and update triples
WITH guideline_consolidation AS (
    SELECT 
        (guideline_metadata->>'document_id')::INTEGER as document_id,
        MAX(id) as keep_guideline_id,
        STRING_AGG(id::TEXT, ', ' ORDER BY id) FILTER (WHERE id < MAX(id)) as remove_guideline_ids
    FROM guidelines
    WHERE guideline_metadata->>'document_id' IS NOT NULL
    GROUP BY (guideline_metadata->>'document_id')::INTEGER
    HAVING COUNT(*) > 1
)
SELECT 
    'For document ' || document_id || ': keeping guideline ' || keep_guideline_id || 
    ', removing guidelines ' || remove_guideline_ids as action
FROM guideline_consolidation;

-- 4. Count triples that will be updated
SELECT 'Triples to be updated:' as info;
WITH guideline_consolidation AS (
    SELECT 
        (guideline_metadata->>'document_id')::INTEGER as document_id,
        MAX(id) as keep_guideline_id
    FROM guidelines
    WHERE guideline_metadata->>'document_id' IS NOT NULL
    GROUP BY (guideline_metadata->>'document_id')::INTEGER
    HAVING COUNT(*) > 1
),
old_guidelines AS (
    SELECT 
        g.id as old_guideline_id,
        (g.guideline_metadata->>'document_id')::INTEGER as document_id
    FROM guidelines g
    JOIN guideline_consolidation gc ON (g.guideline_metadata->>'document_id')::INTEGER = gc.document_id
    WHERE g.id != gc.keep_guideline_id
)
SELECT 
    og.document_id,
    gc.keep_guideline_id,
    COUNT(et.id) as triples_to_update
FROM old_guidelines og
JOIN guideline_consolidation gc ON og.document_id = gc.document_id
JOIN entity_triples et ON et.guideline_id = og.old_guideline_id
GROUP BY og.document_id, gc.keep_guideline_id;

-- 5. Update all triples to point to the newest guideline for each document
WITH guideline_mapping AS (
    SELECT 
        old_guidelines.id as old_guideline_id,
        newest_guidelines.id as new_guideline_id
    FROM guidelines old_guidelines
    JOIN (
        SELECT 
            (guideline_metadata->>'document_id')::INTEGER as document_id,
            MAX(id) as newest_id
        FROM guidelines
        WHERE guideline_metadata->>'document_id' IS NOT NULL
        GROUP BY (guideline_metadata->>'document_id')::INTEGER
    ) newest_guidelines ON (old_guidelines.guideline_metadata->>'document_id')::INTEGER = newest_guidelines.document_id
    WHERE old_guidelines.id != newest_guidelines.newest_id
)
UPDATE entity_triples et
SET guideline_id = gm.new_guideline_id
FROM guideline_mapping gm
WHERE et.guideline_id = gm.old_guideline_id;

-- 6. Update documents to point to the newest guideline
WITH newest_guidelines AS (
    SELECT 
        (guideline_metadata->>'document_id')::INTEGER as document_id,
        MAX(id) as newest_guideline_id
    FROM guidelines
    WHERE guideline_metadata->>'document_id' IS NOT NULL
    GROUP BY (guideline_metadata->>'document_id')::INTEGER
)
UPDATE documents d
SET doc_metadata = jsonb_set(
    COALESCE(d.doc_metadata, '{}'::jsonb),
    '{guideline_id}',
    to_jsonb(ng.newest_guideline_id::TEXT)
)
FROM newest_guidelines ng
WHERE d.id = ng.document_id;

-- 7. Delete the old duplicate guidelines
WITH guidelines_to_keep AS (
    SELECT MAX(id) as keep_id
    FROM guidelines
    WHERE guideline_metadata->>'document_id' IS NOT NULL
    GROUP BY (guideline_metadata->>'document_id')::INTEGER
)
DELETE FROM guidelines
WHERE id NOT IN (SELECT keep_id FROM guidelines_to_keep)
  AND guideline_metadata->>'document_id' IS NOT NULL;

-- 8. Show final state
SELECT 'Final state - Guidelines after cleanup:' as info;
SELECT 
    g.id as guideline_id,
    g.title as guideline_title,
    g.guideline_metadata->>'document_id' as document_id,
    d.title as document_title,
    (SELECT COUNT(*) FROM entity_triples WHERE guideline_id = g.id) as triple_count
FROM guidelines g
LEFT JOIN documents d ON d.id = (g.guideline_metadata->>'document_id')::INTEGER
ORDER BY g.id;

-- 9. Verify no more duplicates
SELECT 'Verification - Documents with multiple guidelines (should be 0):' as info;
SELECT 
    (guideline_metadata->>'document_id')::INTEGER as document_id,
    COUNT(*) as guideline_count
FROM guidelines
WHERE guideline_metadata->>'document_id' IS NOT NULL
GROUP BY (guideline_metadata->>'document_id')::INTEGER
HAVING COUNT(*) > 1;

COMMIT;