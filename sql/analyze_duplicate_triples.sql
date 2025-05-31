-- Analyze duplicate triples in guideline 46

BEGIN;

-- 1. Count total triples for guideline 46
SELECT 'Total triples in guideline 46:' as info;
SELECT COUNT(*) as total_count
FROM entity_triples
WHERE guideline_id = 46 AND entity_type = 'guideline_concept';

-- 2. Find duplicate triples (same subject, predicate, object_literal/object_uri)
SELECT 'Duplicate triple groups:' as info;
SELECT 
    subject,
    predicate,
    COALESCE(object_literal, object_uri) as object_value,
    is_literal,
    COUNT(*) as duplicate_count,
    MIN(id) as keep_id,
    STRING_AGG(id::TEXT, ', ' ORDER BY id) as all_ids
FROM entity_triples
WHERE guideline_id = 46 AND entity_type = 'guideline_concept'
GROUP BY subject, predicate, COALESCE(object_literal, object_uri), is_literal
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC
LIMIT 20;

-- 3. Count how many duplicates vs unique triples
WITH duplicate_analysis AS (
    SELECT 
        subject,
        predicate,
        COALESCE(object_literal, object_uri) as object_value,
        is_literal,
        COUNT(*) as count
    FROM entity_triples
    WHERE guideline_id = 46 AND entity_type = 'guideline_concept'
    GROUP BY subject, predicate, COALESCE(object_literal, object_uri), is_literal
)
SELECT 'Duplicate analysis:' as info;
SELECT 
    'Unique triples' as type,
    COUNT(*) as groups,
    SUM(count) as total_triples
FROM duplicate_analysis
WHERE count = 1
UNION ALL
SELECT 
    'Duplicate groups' as type,
    COUNT(*) as groups,
    SUM(count) as total_triples
FROM duplicate_analysis
WHERE count > 1;

-- 4. Count total duplicates to remove
WITH duplicate_triples AS (
    SELECT 
        subject,
        predicate,
        COALESCE(object_literal, object_uri) as object_value,
        is_literal,
        COUNT(*) - 1 as duplicates_to_remove
    FROM entity_triples
    WHERE guideline_id = 46 AND entity_type = 'guideline_concept'
    GROUP BY subject, predicate, COALESCE(object_literal, object_uri), is_literal
    HAVING COUNT(*) > 1
)
SELECT 'Total duplicate triples to remove:' as info;
SELECT SUM(duplicates_to_remove) as total_to_remove
FROM duplicate_triples;

-- 5. Show sample of actual duplicate triples
SELECT 'Sample duplicate triples:' as info;
WITH duplicates AS (
    SELECT 
        subject,
        predicate,
        COALESCE(object_literal, object_uri) as object_value,
        is_literal,
        COUNT(*) as dup_count
    FROM entity_triples
    WHERE guideline_id = 46 AND entity_type = 'guideline_concept'
    GROUP BY subject, predicate, COALESCE(object_literal, object_uri), is_literal
    HAVING COUNT(*) > 1
    LIMIT 1
)
SELECT 
    et.id,
    et.subject,
    et.predicate,
    COALESCE(et.object_literal, et.object_uri) as object_value,
    et.is_literal,
    et.created_at
FROM entity_triples et
JOIN duplicates d ON et.subject = d.subject 
    AND et.predicate = d.predicate 
    AND COALESCE(et.object_literal, et.object_uri) = d.object_value
    AND et.is_literal = d.is_literal
WHERE et.guideline_id = 46
ORDER BY et.subject, et.predicate, COALESCE(et.object_literal, et.object_uri), et.id;

ROLLBACK;