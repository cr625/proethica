-- SQL script to clean up triples for a specific guideline that no longer exists
-- This example targets Guideline 46, but can be modified for other guideline IDs

-- Begin Transaction
BEGIN;

-- Set the guideline ID to clean up
\set target_guideline_id 46

-- Show what we're about to clean
SELECT 'Cleaning up triples for Guideline ID: ' || :target_guideline_id as info;

-- Check if the guideline exists
SELECT 
    CASE 
        WHEN EXISTS(SELECT 1 FROM guidelines WHERE id = :target_guideline_id) 
        THEN 'WARNING: Guideline ' || :target_guideline_id || ' EXISTS in database!'
        ELSE 'Guideline ' || :target_guideline_id || ' does not exist - safe to clean'
    END as status;

-- Count triples to be deleted
SELECT COUNT(*) as "Triples to be deleted"
FROM entity_triples et
WHERE et.entity_type = 'guideline_concept'
  AND (
    et.guideline_id = :target_guideline_id
    OR (et.doc_metadata->>'guideline_id')::INTEGER = :target_guideline_id
  );

-- Show sample of triples to be deleted
SELECT 'Sample triples to be deleted:' as info;
SELECT id, subject, predicate, object, guideline_id, 
       doc_metadata->>'guideline_id' as metadata_guideline_id
FROM entity_triples et
WHERE et.entity_type = 'guideline_concept'
  AND (
    et.guideline_id = :target_guideline_id
    OR (et.doc_metadata->>'guideline_id')::INTEGER = :target_guideline_id
  )
LIMIT 5;

-- Delete the triples
DELETE FROM entity_triples et
WHERE et.entity_type = 'guideline_concept'
  AND (
    et.guideline_id = :target_guideline_id
    OR (et.doc_metadata->>'guideline_id')::INTEGER = :target_guideline_id
  );

-- Clean up document metadata
UPDATE documents 
SET doc_metadata = doc_metadata - 'guideline_id'
WHERE (doc_metadata->>'guideline_id')::INTEGER = :target_guideline_id;

-- Show results
SELECT 'Cleanup complete!' as info;
SELECT 'Triples deleted: ' || COUNT(*) as result
FROM entity_triples et
WHERE et.entity_type = 'guideline_concept'
  AND (
    et.guideline_id = :target_guideline_id
    OR (et.doc_metadata->>'guideline_id')::INTEGER = :target_guideline_id
  );

-- COMMIT the changes
COMMIT;