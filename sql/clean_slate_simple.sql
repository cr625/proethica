-- SIMPLIFIED CLEAN SLATE: Remove all data except World 1
-- This script safely removes data by checking actual table schemas

BEGIN;

-- 1. Show current state
SELECT '=== CURRENT STATE ===' as info;
SELECT COUNT(*) as total_entity_triples FROM entity_triples;
SELECT COUNT(*) as total_guidelines FROM guidelines;
SELECT COUNT(*) as total_documents FROM documents;
SELECT COUNT(*) as total_worlds FROM worlds;

-- 2. Show World 1 details (what we're keeping)
SELECT '=== KEEPING WORLD 1 ===' as info;
SELECT id, name FROM worlds WHERE id = 1;

-- 3. Delete data in correct order (handle foreign key constraints)

-- Delete all entity triples
DELETE FROM entity_triples;

-- Delete all guidelines
DELETE FROM guidelines;

-- Delete all documents
DELETE FROM documents;

-- Delete simulation data
DELETE FROM simulation_sessions;
DELETE FROM simulation_states;

-- Delete experiment data
DELETE FROM experiments;
DELETE FROM evaluations;

-- Delete scenarios and related data
DELETE FROM characters;
DELETE FROM events;
DELETE FROM scenarios;

-- Delete other world-related data
DELETE FROM resources;
DELETE FROM roles;
DELETE FROM conditions;
DELETE FROM decisions;

-- Delete other worlds (keep only world 1)
DELETE FROM worlds WHERE id != 1;

-- 4. Reset all ID sequences to start from 1
SELECT '=== RESETTING ID SEQUENCES ===' as info;

-- Reset sequences to start fresh (except worlds which should start from 2)
SELECT setval('worlds_id_seq', 2, false);
SELECT setval('documents_id_seq', 1, false);
SELECT setval('guidelines_id_seq', 1, false);
SELECT setval('entity_triples_id_seq', 1, false);
SELECT setval('scenarios_id_seq', 1, false);
SELECT setval('characters_id_seq', 1, false);
SELECT setval('events_id_seq', 1, false);
SELECT setval('resources_id_seq', 1, false);
SELECT setval('roles_id_seq', 1, false);
SELECT setval('conditions_id_seq', 1, false);
SELECT setval('decisions_id_seq', 1, false);
SELECT setval('simulation_sessions_id_seq', 1, false);
SELECT setval('simulation_states_id_seq', 1, false);
SELECT setval('experiments_id_seq', 1, false);
SELECT setval('evaluations_id_seq', 1, false);

-- 5. Verify clean state
SELECT '=== FINAL CLEAN STATE ===' as info;
SELECT COUNT(*) as remaining_entity_triples FROM entity_triples;
SELECT COUNT(*) as remaining_guidelines FROM guidelines;
SELECT COUNT(*) as remaining_documents FROM documents;
SELECT COUNT(*) as remaining_worlds FROM worlds;

-- 6. Show remaining world
SELECT 'Remaining world:' as info;
SELECT id, name FROM worlds;

-- 7. Test next IDs
SELECT '=== NEXT ID TESTS ===' as info;
SELECT 'Next document ID:' as test, nextval('documents_id_seq') as next_id;
SELECT 'Next guideline ID:' as test, nextval('guidelines_id_seq') as next_id;
SELECT 'Next triple ID:' as test, nextval('entity_triples_id_seq') as next_id;

-- Reset the sequences again since we just tested them
SELECT setval('documents_id_seq', 1, false);
SELECT setval('guidelines_id_seq', 1, false);
SELECT setval('entity_triples_id_seq', 1, false);

SELECT '✅ CLEAN SLATE COMPLETE!' as status;

COMMIT;