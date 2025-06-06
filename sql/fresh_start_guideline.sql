-- Fresh start: Delete all guideline data and prepare for re-extraction
-- This removes all guidelines and their triples so you can start clean

BEGIN;

-- 1. Show current state
SELECT 'Current state before cleanup:' as info;
SELECT 
    'Guidelines' as entity_type,
    COUNT(*) as count
FROM guidelines
UNION ALL
SELECT 
    'Guideline concept triples' as entity_type,
    COUNT(*) as count
FROM entity_triples
WHERE entity_type = 'guideline_concept';

-- 2. Show guideline details before deletion
SELECT 'Guidelines to be deleted:' as info;
SELECT 
    id,
    title,
    guideline_metadata->>'document_id' as document_id,
    created_at
FROM guidelines
ORDER BY id;

-- 3. Count triples by guideline
SELECT 'Triples per guideline before deletion:' as info;
SELECT 
    COALESCE(guideline_id, 0) as guideline_id,
    COUNT(*) as triple_count
FROM entity_triples
WHERE entity_type = 'guideline_concept'
GROUP BY guideline_id
ORDER BY guideline_id;

-- 4. Delete all guideline concept triples
DELETE FROM entity_triples
WHERE entity_type = 'guideline_concept';

-- 5. Delete all guidelines
DELETE FROM guidelines;

-- 6. Clean up document metadata references
UPDATE documents
SET doc_metadata = doc_metadata - 'guideline_id'
WHERE doc_metadata ? 'guideline_id';

-- 7. Show final clean state
SELECT 'Final state after cleanup:' as info;
SELECT 
    'Guidelines' as entity_type,
    COUNT(*) as count
FROM guidelines
UNION ALL
SELECT 
    'Guideline concept triples' as entity_type,
    COUNT(*) as count
FROM entity_triples
WHERE entity_type = 'guideline_concept'
UNION ALL
SELECT 
    'Documents with guideline_id' as entity_type,
    COUNT(*) as count
FROM documents
WHERE doc_metadata ? 'guideline_id';

-- 8. Show remaining documents that can be used for re-extraction
SELECT 'Documents available for re-extraction:' as info;
SELECT 
    id,
    title,
    document_type,
    source,
    created_at
FROM documents
WHERE document_type = 'guideline'
ORDER BY id;

SELECT 'FRESH START COMPLETE!' as status;
SELECT 'You can now re-run concept extraction on document(s) to create clean guidelines without duplicates.' as next_steps;

COMMIT;