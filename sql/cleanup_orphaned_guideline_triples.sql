-- SQL script to clean up orphaned guideline triples
-- This removes triples associated with guidelines that no longer exist in the database
-- or triples referencing guideline documents that have been deleted

-- Begin Transaction
BEGIN;

-- Create temporary tables to track cleanup progress
CREATE TEMPORARY TABLE cleanup_stats (
    description TEXT,
    count BIGINT
);

-- 1. Count current state
INSERT INTO cleanup_stats VALUES 
    ('Total guideline concept triples before cleanup', 
     (SELECT COUNT(*) FROM entity_triples WHERE entity_type = 'guideline_concept'));

-- 2. Find orphaned guideline triples (referencing non-existent guidelines)
CREATE TEMPORARY TABLE orphaned_guideline_triples AS
SELECT et.id, et.subject, et.predicate, et.object, et.guideline_id,
       et.doc_metadata->>'guideline_id' as metadata_guideline_id,
       et.doc_metadata->>'document_id' as metadata_document_id
FROM entity_triples et
WHERE et.entity_type = 'guideline_concept'
  AND (
    -- Case 1: guideline_id is set but guideline doesn't exist
    (et.guideline_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM guidelines g WHERE g.id = et.guideline_id
    ))
    OR
    -- Case 2: metadata references a guideline that doesn't exist
    (et.doc_metadata->>'guideline_id' IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM guidelines g WHERE g.id = (et.doc_metadata->>'guideline_id')::INTEGER
    ))
    OR
    -- Case 3: metadata references a document that doesn't exist
    (et.doc_metadata->>'document_id' IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM documents d WHERE d.id = (et.doc_metadata->>'document_id')::INTEGER
    ))
  );

INSERT INTO cleanup_stats VALUES 
    ('Orphaned guideline triples found', 
     (SELECT COUNT(*) FROM orphaned_guideline_triples));

-- 3. Show sample of orphaned triples for verification
SELECT 'Sample orphaned triples:' as info;
SELECT * FROM orphaned_guideline_triples LIMIT 10;

-- 4. Find triples associated with specific non-existent guidelines (like guideline 46)
CREATE TEMPORARY TABLE guideline_references AS
SELECT DISTINCT 
    COALESCE(et.guideline_id, (et.doc_metadata->>'guideline_id')::INTEGER) as referenced_guideline_id,
    COUNT(*) as triple_count,
    BOOL_OR(EXISTS(SELECT 1 FROM guidelines g WHERE g.id = COALESCE(et.guideline_id, (et.doc_metadata->>'guideline_id')::INTEGER))) as guideline_exists
FROM entity_triples et
WHERE et.entity_type = 'guideline_concept'
  AND (et.guideline_id IS NOT NULL OR et.doc_metadata->>'guideline_id' IS NOT NULL)
GROUP BY COALESCE(et.guideline_id, (et.doc_metadata->>'guideline_id')::INTEGER)
ORDER BY referenced_guideline_id;

SELECT 'Guideline references in triples:' as info;
SELECT * FROM guideline_references;

-- 5. Show existing guidelines for comparison
SELECT 'Existing guidelines in database:' as info;
SELECT id, title, guideline_metadata->>'document_id' as document_id 
FROM guidelines 
ORDER BY id;

-- 6. Delete orphaned triples
DELETE FROM entity_triples 
WHERE id IN (SELECT id FROM orphaned_guideline_triples);

INSERT INTO cleanup_stats VALUES 
    ('Guideline triples deleted', 
     (SELECT COUNT(*) FROM orphaned_guideline_triples));

-- 7. Clean up document metadata that references non-existent guidelines
UPDATE documents 
SET doc_metadata = doc_metadata - 'guideline_id'
WHERE doc_metadata->>'guideline_id' IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM guidelines g 
    WHERE g.id = (doc_metadata->>'guideline_id')::INTEGER
  );

INSERT INTO cleanup_stats VALUES 
    ('Documents with cleaned guideline references', 
     ROW_COUNT());

-- 8. Final verification
INSERT INTO cleanup_stats VALUES 
    ('Total guideline concept triples after cleanup', 
     (SELECT COUNT(*) FROM entity_triples WHERE entity_type = 'guideline_concept'));

-- Show cleanup summary
SELECT 'Cleanup Summary:' as info;
SELECT * FROM cleanup_stats ORDER BY description;

-- Show remaining guideline references
SELECT 'Remaining guideline references after cleanup:' as info;
SELECT 
    COALESCE(et.guideline_id, (et.doc_metadata->>'guideline_id')::INTEGER) as guideline_id,
    g.title as guideline_title,
    COUNT(*) as triple_count
FROM entity_triples et
LEFT JOIN guidelines g ON g.id = COALESCE(et.guideline_id, (et.doc_metadata->>'guideline_id')::INTEGER)
WHERE et.entity_type = 'guideline_concept'
  AND (et.guideline_id IS NOT NULL OR et.doc_metadata->>'guideline_id' IS NOT NULL)
GROUP BY COALESCE(et.guideline_id, (et.doc_metadata->>'guideline_id')::INTEGER), g.title
ORDER BY guideline_id;

-- COMMIT or ROLLBACK based on verification
-- Uncomment one of the following:
-- ROLLBACK;  -- Use this to test without making changes
COMMIT;    -- Use this to apply the cleanup