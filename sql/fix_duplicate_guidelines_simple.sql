-- Simple SQL script to fix duplicate guidelines pointing to the same document
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

-- 2. Show triples count for each guideline
SELECT 'Triples per guideline:' as info;
SELECT 
    g.id as guideline_id,
    g.title,
    COUNT(et.id) as triple_count
FROM guidelines g
LEFT JOIN entity_triples et ON et.guideline_id = g.id
GROUP BY g.id, g.title
ORDER BY g.id;

-- 3. Update all triples from guidelines 43, 44, 45 to point to guideline 46
UPDATE entity_triples
SET guideline_id = 46
WHERE guideline_id IN (43, 44, 45);

SELECT 'Triples updated: ' || COUNT(*) as result
FROM entity_triples
WHERE guideline_id = 46;

-- 4. Delete the old duplicate guidelines (43, 44, 45)
DELETE FROM guidelines
WHERE id IN (43, 44, 45);

-- 5. Show final state
SELECT 'Final state - Guidelines after cleanup:' as info;
SELECT 
    g.id as guideline_id,
    g.title as guideline_title,
    g.guideline_metadata->>'document_id' as document_id,
    (SELECT COUNT(*) FROM entity_triples WHERE guideline_id = g.id) as triple_count
FROM guidelines g
ORDER BY g.id;

-- 6. Verify document 190 still references guideline 46
SELECT 'Document 190 guideline reference:' as info;
SELECT 
    id,
    title,
    doc_metadata->>'guideline_id' as guideline_id_reference
FROM documents
WHERE id = 190;

COMMIT;