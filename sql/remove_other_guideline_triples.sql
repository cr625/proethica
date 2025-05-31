-- SQL script to remove "Other Guidelines" triples when only one guideline exists
-- This deletes all guideline concept triples that aren't associated with the single guideline

BEGIN;

-- Get the actual guideline ID
CREATE TEMPORARY TABLE current_guideline AS
SELECT id as guideline_id, title, world_id
FROM guidelines
LIMIT 1;  -- Should only be one guideline

-- Show the current guideline
SELECT 'Current guideline in database:' as info;
SELECT * FROM current_guideline;

-- Count triples that will be kept vs deleted
SELECT 'Triples to be kept (associated with current guideline):' as info;
SELECT COUNT(*) as count
FROM entity_triples
WHERE entity_type = 'guideline_concept'
  AND guideline_id = (SELECT guideline_id FROM current_guideline);

SELECT 'Triples to be DELETED (not associated with current guideline):' as info;
SELECT COUNT(*) as count
FROM entity_triples
WHERE entity_type = 'guideline_concept'
  AND (guideline_id IS NULL OR guideline_id != (SELECT guideline_id FROM current_guideline));

-- Show sample of triples to be deleted
SELECT 'Sample of triples to be deleted:' as info;
SELECT id, guideline_id, subject, predicate, object
FROM entity_triples
WHERE entity_type = 'guideline_concept'
  AND (guideline_id IS NULL OR guideline_id != (SELECT guideline_id FROM current_guideline))
LIMIT 10;

-- Delete triples not associated with the current guideline
DELETE FROM entity_triples
WHERE entity_type = 'guideline_concept'
  AND (guideline_id IS NULL OR guideline_id != (SELECT guideline_id FROM current_guideline));

-- Show final count
SELECT 'Remaining guideline concept triples:' as info;
SELECT guideline_id, COUNT(*) as triple_count
FROM entity_triples
WHERE entity_type = 'guideline_concept'
GROUP BY guideline_id;

COMMIT;