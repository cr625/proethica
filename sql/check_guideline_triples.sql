-- Check entity_triples with NULL guideline_id

-- Count total guidelines
SELECT COUNT(*) as total_guidelines FROM guidelines;

-- List all guidelines with triple counts
SELECT 
    g.id,
    g.title,
    COUNT(et.id) as triple_count
FROM guidelines g
LEFT JOIN entity_triples et ON g.id = et.guideline_id AND et.entity_type = 'guideline_concept'
GROUP BY g.id, g.title
ORDER BY g.id;

-- Count triples by guideline_id (including NULL)
SELECT 
    guideline_id,
    COUNT(*) as count
FROM entity_triples
WHERE entity_type = 'guideline_concept'
GROUP BY guideline_id
ORDER BY guideline_id;

-- Check specifically for guideline_concept type with NULL guideline_id
SELECT 
    COUNT(*) as null_guideline_concepts
FROM entity_triples
WHERE entity_type = 'guideline_concept' 
AND guideline_id IS NULL;

-- Show examples of triples with NULL guideline_id
SELECT 
    id,
    subject_label,
    predicate_label,
    COALESCE(object_label, object_literal, object_uri) as object_value,
    entity_id,
    world_id
FROM entity_triples
WHERE entity_type = 'guideline_concept' 
AND guideline_id IS NULL
LIMIT 10;