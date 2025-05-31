-- SQL script to clean up "Other Guidelines" triples when only one guideline exists
-- This consolidates all guideline concept triples under the single existing guideline

BEGIN;

-- Get the actual guideline ID (should be 46 based on user's information)
CREATE TEMPORARY TABLE current_guideline AS
SELECT id as guideline_id, title, world_id
FROM guidelines
LIMIT 1;  -- Should only be one guideline

-- Show the current guideline
SELECT 'Current guideline in database:' as info;
SELECT * FROM current_guideline;

-- Count triples by their association
CREATE TEMPORARY TABLE triple_counts AS
SELECT 
    CASE 
        WHEN guideline_id = (SELECT guideline_id FROM current_guideline) THEN 'Correctly associated'
        WHEN guideline_id IS NULL THEN 'No guideline_id'
        ELSE 'Other guideline_id (' || guideline_id || ')'
    END as association_type,
    COUNT(*) as count
FROM entity_triples
WHERE entity_type = 'guideline_concept'
GROUP BY association_type
ORDER BY count DESC;

SELECT 'Triple associations before cleanup:' as info;
SELECT * FROM triple_counts;

-- Option 1: Update all guideline concept triples to use the correct guideline_id
UPDATE entity_triples
SET guideline_id = (SELECT guideline_id FROM current_guideline)
WHERE entity_type = 'guideline_concept'
  AND (guideline_id IS NULL OR guideline_id != (SELECT guideline_id FROM current_guideline));

-- Option 2: Also update the metadata to be consistent
UPDATE entity_triples
SET doc_metadata = jsonb_set(
    COALESCE(doc_metadata, '{}'::jsonb),
    '{guideline_id}',
    to_jsonb((SELECT guideline_id FROM current_guideline)::TEXT)
)
WHERE entity_type = 'guideline_concept';

-- Verify the update
SELECT 'Triple associations after cleanup:' as info;
SELECT 
    CASE 
        WHEN guideline_id = (SELECT guideline_id FROM current_guideline) THEN 'Correctly associated'
        WHEN guideline_id IS NULL THEN 'No guideline_id'
        ELSE 'Other guideline_id (' || guideline_id || ')'
    END as association_type,
    COUNT(*) as count
FROM entity_triples
WHERE entity_type = 'guideline_concept'
GROUP BY association_type
ORDER BY count DESC;

-- Update documents table to ensure consistency
UPDATE documents
SET doc_metadata = jsonb_set(
    COALESCE(doc_metadata, '{}'::jsonb),
    '{guideline_id}',
    to_jsonb((SELECT guideline_id FROM current_guideline)::TEXT)
)
WHERE doc_type = 'guideline' 
  AND (doc_metadata->>'guideline_id' IS NULL 
       OR (doc_metadata->>'guideline_id')::INTEGER != (SELECT guideline_id FROM current_guideline));

-- Show final status
SELECT 'All guideline concept triples now associated with guideline:' as info;
SELECT guideline_id, COUNT(*) as triple_count
FROM entity_triples
WHERE entity_type = 'guideline_concept'
GROUP BY guideline_id;

COMMIT;