-- SQL script to selectively clean up guideline triples
-- This will preserve only triples associated with guideline document ID 190 (Engineering Ethics)

-- Begin Transaction
BEGIN;

-- Store the current state for verification
CREATE TEMPORARY TABLE guideline_state_before AS
SELECT COUNT(*) as total FROM entity_triples WHERE entity_type = 'guideline_concept';

-- First check which triples we want to keep (associated with guideline ID 43)
CREATE TEMPORARY TABLE guideline_triples_to_keep AS
SELECT id FROM entity_triples 
WHERE entity_type = 'guideline_concept' 
AND world_id = 1
AND id BETWEEN 3096 AND 3222;

-- Count triples to keep for verification
CREATE TEMPORARY TABLE keep_count AS
SELECT COUNT(*) as count FROM guideline_triples_to_keep;

-- Count triples to delete
CREATE TEMPORARY TABLE delete_count AS
SELECT (SELECT total FROM guideline_state_before) - (SELECT count FROM keep_count) as count;

-- Get guidelines info
CREATE TEMPORARY TABLE guidelines_info AS
SELECT id, title, guideline_metadata->>'document_id' as referenced_guideline_id 
FROM guidelines;

-- Print tables to verify counts
SELECT * FROM guidelines_info;

-- Show counts of triples
SELECT (SELECT total FROM guideline_state_before) AS "Total Guideline Concept Triples";
SELECT (SELECT count FROM keep_count) AS "Guideline Triples to Keep";
SELECT (SELECT count FROM delete_count) AS "Guideline Triples to Delete";

-- List guidelines
SELECT id, title, guideline_metadata->>'document_id' as referenced_guideline_id FROM guidelines;

-- Delete all guideline triples EXCEPT those associated with guideline ID 43 (linked to document 190)
DELETE FROM entity_triples 
WHERE entity_type = 'guideline_concept' 
AND id NOT IN (SELECT id FROM guideline_triples_to_keep);

-- Show the counts after deletion
SELECT COUNT(*) as "Remaining Guideline Concept Triples" FROM entity_triples WHERE entity_type = 'guideline_concept';

-- List remaining guidelines
SELECT g.id, g.title, COUNT(et.id) as "Remaining Guidelines" 
FROM guidelines g
LEFT JOIN entity_triples et ON et.entity_type = 'guideline_concept' AND et.world_id = g.world_id
GROUP BY g.id, g.title;

-- Check documents still having guideline references
SELECT COUNT(*) as "Documents still having guideline references"
FROM documents d
WHERE d.doc_metadata->>'guideline_id' IS NOT NULL;

-- COMMIT or ROLLBACK depending on verification
COMMIT;
