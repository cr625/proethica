-- Remove duplicate triples from guideline 46
-- Keeps only the oldest triple for each unique (subject, predicate, object) combination

BEGIN;

-- 1. Show current state
SELECT 'Current state before deduplication:' as info;
SELECT COUNT(*) as total_triples 
FROM entity_triples 
WHERE guideline_id = 46 AND entity_type = 'guideline_concept';

-- 2. Identify duplicates and which ones to keep
CREATE TEMPORARY TABLE triples_to_keep AS
SELECT MIN(id) as keep_id,
       subject,
       predicate,
       COALESCE(object_literal, object_uri) as object_value,
       is_literal,
       COUNT(*) as duplicate_count
FROM entity_triples
WHERE guideline_id = 46 AND entity_type = 'guideline_concept'
GROUP BY subject, predicate, COALESCE(object_literal, object_uri), is_literal;

-- 3. Show deduplication summary
SELECT 'Deduplication summary:' as info;
SELECT 
    SUM(CASE WHEN duplicate_count = 1 THEN 1 ELSE 0 END) as unique_triples,
    SUM(CASE WHEN duplicate_count > 1 THEN 1 ELSE 0 END) as duplicate_groups,
    SUM(CASE WHEN duplicate_count > 1 THEN duplicate_count - 1 ELSE 0 END) as triples_to_remove,
    COUNT(*) as total_unique_concepts
FROM triples_to_keep;

-- 4. Show examples of duplicates being removed
SELECT 'Sample duplicates to be removed:' as info;
SELECT 
    et.id,
    et.subject,
    et.predicate,
    COALESCE(et.object_literal, et.object_uri) as object_value,
    et.created_at
FROM entity_triples et
WHERE et.guideline_id = 46 
  AND et.entity_type = 'guideline_concept'
  AND et.id NOT IN (SELECT keep_id FROM triples_to_keep)
ORDER BY et.subject, et.predicate, COALESCE(et.object_literal, et.object_uri), et.id
LIMIT 20;

-- 5. Delete duplicate triples (keep only the oldest one for each unique triple)
DELETE FROM entity_triples
WHERE guideline_id = 46 
  AND entity_type = 'guideline_concept'
  AND id NOT IN (SELECT keep_id FROM triples_to_keep);

-- 6. Show final state
SELECT 'Final state after deduplication:' as info;
SELECT COUNT(*) as remaining_triples 
FROM entity_triples 
WHERE guideline_id = 46 AND entity_type = 'guideline_concept';

-- 7. Verify no duplicates remain
SELECT 'Verification - duplicate check (should be 0):' as info;
SELECT COUNT(*) as remaining_duplicates
FROM (
    SELECT subject, predicate, COALESCE(object_literal, object_uri), is_literal
    FROM entity_triples
    WHERE guideline_id = 46 AND entity_type = 'guideline_concept'
    GROUP BY subject, predicate, COALESCE(object_literal, object_uri), is_literal
    HAVING COUNT(*) > 1
) duplicate_check;

-- 8. Show sample of remaining triples
SELECT 'Sample of remaining unique triples:' as info;
SELECT 
    id,
    subject,
    predicate,
    COALESCE(object_literal, object_uri) as object_value,
    is_literal
FROM entity_triples
WHERE guideline_id = 46 AND entity_type = 'guideline_concept'
ORDER BY subject, predicate
LIMIT 10;

COMMIT;