-- Cleanup orphaned triples for guideline 8
-- This script identifies and removes triples that are associated with guideline 8 
-- but don't belong to world 1.

-- Step 1: Analyze the current situation
SELECT 
    'Analysis: Document 8 info' as action,
    id,
    title,
    world_id,
    doc_metadata->'guideline_id' as associated_guideline_id
FROM documents 
WHERE id = 8;

-- Step 2: Find all triples associated with the guideline
-- First get the associated guideline_id for document 8
WITH document_info AS (
    SELECT 
        id as doc_id,
        world_id as doc_world_id,
        (doc_metadata->'guideline_id')::int as guideline_id
    FROM documents 
    WHERE id = 8
),
triple_analysis AS (
    SELECT 
        et.id as triple_id,
        et.guideline_id,
        et.world_id,
        et.subject_label,
        di.doc_world_id,
        CASE 
            WHEN et.world_id = di.doc_world_id THEN 'CORRECT'
            ELSE 'ORPHANED'
        END as status
    FROM entity_triple et
    JOIN document_info di ON et.guideline_id = di.guideline_id
    WHERE et.guideline_id = (SELECT guideline_id FROM document_info)
)
SELECT 
    'Analysis: Triple breakdown by world' as action,
    world_id,
    status,
    COUNT(*) as triple_count
FROM triple_analysis
GROUP BY world_id, status
ORDER BY world_id;

-- Step 3: Show details of orphaned triples
WITH document_info AS (
    SELECT 
        id as doc_id,
        world_id as doc_world_id,
        (doc_metadata->'guideline_id')::int as guideline_id
    FROM documents 
    WHERE id = 8
)
SELECT 
    'Orphaned triples details' as action,
    et.id as triple_id,
    et.world_id,
    et.subject_label,
    w.name as world_name
FROM entity_triple et
JOIN document_info di ON et.guideline_id = di.guideline_id
JOIN worlds w ON et.world_id = w.id
WHERE et.guideline_id = (SELECT guideline_id FROM document_info)
  AND et.world_id != di.doc_world_id
LIMIT 10;

-- Step 4: Count orphaned triples to be deleted
WITH document_info AS (
    SELECT 
        id as doc_id,
        world_id as doc_world_id,
        (doc_metadata->'guideline_id')::int as guideline_id
    FROM documents 
    WHERE id = 8
)
SELECT 
    'Total orphaned triples to delete' as action,
    COUNT(*) as orphaned_count
FROM entity_triple et
JOIN document_info di ON et.guideline_id = di.guideline_id
WHERE et.guideline_id = (SELECT guideline_id FROM document_info)
  AND et.world_id != di.doc_world_id;

-- Step 5: DELETE ORPHANED TRIPLES (uncomment to execute)
-- WARNING: This will permanently delete orphaned triples!
/*
WITH document_info AS (
    SELECT 
        id as doc_id,
        world_id as doc_world_id,
        (doc_metadata->'guideline_id')::int as guideline_id
    FROM documents 
    WHERE id = 8
)
DELETE FROM entity_triple 
WHERE id IN (
    SELECT et.id
    FROM entity_triple et
    JOIN document_info di ON et.guideline_id = di.guideline_id
    WHERE et.guideline_id = (SELECT guideline_id FROM document_info)
      AND et.world_id != di.doc_world_id
);
*/

-- Step 6: Verify cleanup (run after deletion)
/*
WITH document_info AS (
    SELECT 
        id as doc_id,
        world_id as doc_world_id,
        (doc_metadata->'guideline_id')::int as guideline_id
    FROM documents 
    WHERE id = 8
)
SELECT 
    'After cleanup: Remaining triples' as action,
    et.world_id,
    COUNT(*) as triple_count
FROM entity_triple et
JOIN document_info di ON et.guideline_id = di.guideline_id
WHERE et.guideline_id = (SELECT guideline_id FROM document_info)
GROUP BY et.world_id
ORDER BY et.world_id;
*/