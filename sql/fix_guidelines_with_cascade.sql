-- Fix duplicate guidelines with CASCADE option

BEGIN;

-- Show current state
SELECT 'Current guidelines:' as info;
SELECT id, title FROM guidelines ORDER BY id;

-- Count triples for each guideline
SELECT 'Triples per guideline before:' as info;
SELECT guideline_id, COUNT(*) as count 
FROM entity_triples 
WHERE guideline_id IN (43, 44, 45, 46)
GROUP BY guideline_id
ORDER BY guideline_id;

-- Update all triples to point to guideline 46
UPDATE entity_triples
SET guideline_id = 46
WHERE guideline_id IN (43, 44, 45);

-- Check if update worked
SELECT 'Triples after update:' as info;
SELECT guideline_id, COUNT(*) as count 
FROM entity_triples 
WHERE guideline_id IN (43, 44, 45, 46)
GROUP BY guideline_id
ORDER BY guideline_id;

-- Try to delete old guidelines
DELETE FROM guidelines WHERE id IN (43, 44, 45);

-- Check final state
SELECT 'Final guidelines:' as info;
SELECT id, title FROM guidelines ORDER BY id;

-- Check final triple count
SELECT 'Total triples for guideline 46:' as info;
SELECT COUNT(*) FROM entity_triples WHERE guideline_id = 46;

COMMIT;