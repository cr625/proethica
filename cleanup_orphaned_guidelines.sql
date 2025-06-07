-- Cleanup orphaned guidelines and their triples
-- Guidelines 2 and 3 have no associated documents but still have triples

-- Step 1: Show the orphaned guidelines
SELECT 
    'Orphaned Guidelines' as info,
    g.id as guideline_id,
    g.title,
    COUNT(et.id) as triple_count,
    d.id as associated_document_id
FROM guidelines g
LEFT JOIN documents d ON d.doc_metadata->>'guideline_id' = g.id::text
LEFT JOIN entity_triples et ON et.guideline_id = g.id
WHERE d.id IS NULL
GROUP BY g.id, g.title, d.id
ORDER BY g.id;

-- Step 2: Show sample triples from orphaned guidelines
SELECT 
    'Sample Orphaned Triples' as info,
    et.guideline_id,
    et.subject_label,
    et.predicate_label,
    et.object_label
FROM entity_triples et
WHERE et.guideline_id IN (
    SELECT g.id 
    FROM guidelines g
    LEFT JOIN documents d ON d.doc_metadata->>'guideline_id' = g.id::text
    WHERE d.id IS NULL
)
LIMIT 10;

-- Step 3: Count total orphaned triples
SELECT 
    'Total Orphaned Triples' as info,
    COUNT(*) as total_count
FROM entity_triples et
WHERE et.guideline_id IN (
    SELECT g.id 
    FROM guidelines g
    LEFT JOIN documents d ON d.doc_metadata->>'guideline_id' = g.id::text
    WHERE d.id IS NULL
);

-- Step 4: DELETE orphaned triples and guidelines (uncomment to execute)
-- WARNING: This will permanently delete orphaned guidelines and their triples!

-- Delete triples first (due to foreign key constraint)
/*
DELETE FROM entity_triples 
WHERE guideline_id IN (
    SELECT g.id 
    FROM guidelines g
    LEFT JOIN documents d ON d.doc_metadata->>'guideline_id' = g.id::text
    WHERE d.id IS NULL
);
*/

-- Then delete the orphaned guidelines
/*
DELETE FROM guidelines 
WHERE id IN (
    SELECT g.id 
    FROM guidelines g
    LEFT JOIN documents d ON d.doc_metadata->>'guideline_id' = g.id::text
    WHERE d.id IS NULL
);
*/

-- Step 5: Verify cleanup (run after deletion)
/*
SELECT 
    'After Cleanup: Remaining Guidelines' as info,
    g.id as guideline_id,
    g.title,
    d.id as document_id
FROM guidelines g
LEFT JOIN documents d ON d.doc_metadata->>'guideline_id' = g.id::text
ORDER BY g.id;
*/