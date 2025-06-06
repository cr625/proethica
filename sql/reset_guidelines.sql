-- Reset guidelines and documents for fresh start

BEGIN;

-- Show current state
SELECT 'Current documents:' as info;
SELECT id, title, document_type FROM documents;

-- Delete all documents and guidelines
DELETE FROM entity_triples WHERE entity_type = 'guideline_concept';
DELETE FROM guidelines;
DELETE FROM documents WHERE document_type = 'guideline';

-- Reset sequences to start from 1
SELECT setval('documents_id_seq', 1, false);
SELECT setval('guidelines_id_seq', 1, false);
SELECT setval('entity_triples_id_seq', 1, false);

-- Verify clean state
SELECT 'After cleanup:' as info;
SELECT COUNT(*) as documents FROM documents;
SELECT COUNT(*) as guidelines FROM guidelines;
SELECT COUNT(*) as guideline_triples FROM entity_triples WHERE entity_type = 'guideline_concept';

SELECT 'Next IDs:' as info;
SELECT nextval('documents_id_seq') as next_document_id;
SELECT nextval('guidelines_id_seq') as next_guideline_id;

-- Reset sequences again after checking
SELECT setval('documents_id_seq', 1, false);
SELECT setval('guidelines_id_seq', 1, false);

SELECT 'Ready for fresh guideline creation!' as status;

COMMIT;