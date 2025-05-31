-- MINIMAL CLEAN SLATE: Remove all data except World 1
-- This script only touches tables that actually exist

BEGIN;

-- 1. Show current state
SELECT '=== CURRENT STATE ===' as info;
SELECT COUNT(*) as entity_triples FROM entity_triples;
SELECT COUNT(*) as guidelines FROM guidelines;
SELECT COUNT(*) as documents FROM documents;
SELECT COUNT(*) as worlds FROM worlds;

-- 2. Show World 1 (what we're keeping)
SELECT 'Keeping World 1:' as info;
SELECT id, name FROM worlds WHERE id = 1;

-- 3. Delete data (only tables that exist)
DELETE FROM entity_triples;
DELETE FROM guidelines;
DELETE FROM documents;
DELETE FROM characters;
DELETE FROM events;
DELETE FROM scenarios;

-- Keep only World 1
DELETE FROM worlds WHERE id != 1;

-- 4. Reset ID sequences
SELECT setval('worlds_id_seq', 2, false);
SELECT setval('documents_id_seq', 1, false);
SELECT setval('guidelines_id_seq', 1, false);
SELECT setval('entity_triples_id_seq', 1, false);
SELECT setval('scenarios_id_seq', 1, false);
SELECT setval('characters_id_seq', 1, false);
SELECT setval('events_id_seq', 1, false);

-- 5. Verify clean state
SELECT '=== CLEAN STATE ===' as info;
SELECT COUNT(*) as entity_triples FROM entity_triples;
SELECT COUNT(*) as guidelines FROM guidelines;
SELECT COUNT(*) as documents FROM documents;
SELECT COUNT(*) as worlds FROM worlds;

-- 6. Test next IDs
SELECT '=== NEXT IDS ===' as info;
SELECT nextval('documents_id_seq') as next_document_id;
SELECT nextval('guidelines_id_seq') as next_guideline_id;
SELECT nextval('entity_triples_id_seq') as next_triple_id;

-- Reset sequences after testing
SELECT setval('documents_id_seq', 1, false);
SELECT setval('guidelines_id_seq', 1, false);
SELECT setval('entity_triples_id_seq', 1, false);

SELECT '✅ CLEAN SLATE COMPLETE!' as status;

COMMIT;