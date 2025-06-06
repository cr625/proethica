-- COMPREHENSIVE CLEAN SLATE: Keep only World 1, remove everything else
-- This script removes all data except World 1 and resets ID sequences

BEGIN;

-- 1. Show current state before cleanup
SELECT '=== CURRENT STATE BEFORE CLEANUP ===' as info;

SELECT 'Worlds:' as entity_type, COUNT(*) as count FROM worlds
UNION ALL
SELECT 'Documents:' as entity_type, COUNT(*) as count FROM documents
UNION ALL
SELECT 'Guidelines:' as entity_type, COUNT(*) as count FROM guidelines
UNION ALL
SELECT 'Entity Triples:' as entity_type, COUNT(*) as count FROM entity_triples
UNION ALL
SELECT 'Scenarios:' as entity_type, COUNT(*) as count FROM scenarios
UNION ALL
SELECT 'Characters:' as entity_type, COUNT(*) as count FROM characters
UNION ALL
SELECT 'Events:' as entity_type, COUNT(*) as count FROM events
UNION ALL
SELECT 'Resources:' as entity_type, COUNT(*) as count FROM resources
UNION ALL
SELECT 'Roles:' as entity_type, COUNT(*) as count FROM roles
UNION ALL
SELECT 'Conditions:' as entity_type, COUNT(*) as count FROM conditions
UNION ALL
SELECT 'Decisions:' as entity_type, COUNT(*) as count FROM decisions;

-- 2. Show details of World 1 (what we're keeping)
SELECT '=== WORLD 1 DETAILS (KEEPING) ===' as info;
SELECT id, name, description, created_at FROM worlds WHERE id = 1;

-- 3. Delete all data except World 1 (with CASCADE to handle foreign keys)

-- Delete entity triples not associated with world 1
DELETE FROM entity_triples WHERE world_id != 1 OR world_id IS NULL;

-- Delete guidelines not associated with world 1
DELETE FROM guidelines WHERE world_id != 1 OR world_id IS NULL;

-- Delete documents not associated with world 1
DELETE FROM documents WHERE world_id != 1 OR world_id IS NULL;

-- Delete scenarios not associated with world 1
DELETE FROM scenarios WHERE world_id != 1 OR world_id IS NULL;

-- Delete characters not associated with world 1
DELETE FROM characters WHERE world_id != 1 OR world_id IS NULL;

-- Delete events not associated with world 1
DELETE FROM events WHERE world_id != 1 OR world_id IS NULL;

-- Delete resources not associated with world 1
DELETE FROM resources WHERE world_id != 1 OR world_id IS NULL;

-- Delete roles not associated with world 1
DELETE FROM roles WHERE world_id != 1 OR world_id IS NULL;

-- Delete conditions not associated with world 1
DELETE FROM conditions WHERE world_id != 1 OR world_id IS NULL;

-- Delete decisions not associated with world 1
DELETE FROM decisions WHERE world_id != 1 OR world_id IS NULL;

-- Delete all worlds except world 1
DELETE FROM worlds WHERE id != 1;

-- Delete any orphaned records that might not have world_id constraints
DELETE FROM users WHERE id > 1; -- Keep admin user if exists
DELETE FROM simulation_sessions;
DELETE FROM simulation_states;
DELETE FROM experiments;
DELETE FROM evaluations;

-- 4. Reset ID sequences to start from low numbers
-- This ensures new records start with clean, low IDs

-- Reset sequences for main tables (start from 2 since World 1 exists)
SELECT 'Resetting ID sequences...' as info;

-- Reset world sequence to 2 (since we have world 1)
SELECT setval('worlds_id_seq', 2, false);

-- Reset other sequences to 1 (fresh start)
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
SELECT setval('users_id_seq', 2, false);
SELECT setval('simulation_sessions_id_seq', 1, false);
SELECT setval('simulation_states_id_seq', 1, false);
SELECT setval('experiments_id_seq', 1, false);
SELECT setval('evaluations_id_seq', 1, false);

-- 5. Show final clean state
SELECT '=== FINAL CLEAN STATE ===' as info;

SELECT 'Worlds:' as entity_type, COUNT(*) as count FROM worlds
UNION ALL
SELECT 'Documents:' as entity_type, COUNT(*) as count FROM documents
UNION ALL
SELECT 'Guidelines:' as entity_type, COUNT(*) as count FROM guidelines
UNION ALL
SELECT 'Entity Triples:' as entity_type, COUNT(*) as count FROM entity_triples
UNION ALL
SELECT 'Scenarios:' as entity_type, COUNT(*) as count FROM scenarios
UNION ALL
SELECT 'Characters:' as entity_type, COUNT(*) as count FROM characters
UNION ALL
SELECT 'Events:' as entity_type, COUNT(*) as count FROM events
UNION ALL
SELECT 'Resources:' as entity_type, COUNT(*) as count FROM resources
UNION ALL
SELECT 'Roles:' as entity_type, COUNT(*) as count FROM roles
UNION ALL
SELECT 'Conditions:' as entity_type, COUNT(*) as count FROM conditions
UNION ALL
SELECT 'Decisions:' as entity_type, COUNT(*) as count FROM decisions;

-- 6. Show remaining World 1
SELECT 'Remaining World:' as info;
SELECT id, name, description FROM worlds;

-- 7. Show next IDs that will be assigned
SELECT 'Next ID assignments:' as info;
SELECT 
    'documents' as table_name,
    nextval('documents_id_seq') as next_id
UNION ALL
SELECT 
    'guidelines' as table_name,
    nextval('guidelines_id_seq') as next_id
UNION ALL
SELECT 
    'entity_triples' as table_name,
    nextval('entity_triples_id_seq') as next_id;

-- Reset the sequences again since we just used nextval
SELECT setval('documents_id_seq', 1, false);
SELECT setval('guidelines_id_seq', 1, false);
SELECT setval('entity_triples_id_seq', 1, false);

SELECT '=== CLEAN SLATE COMPLETE ===' as status;
SELECT 'Database now contains only World 1 with fresh ID sequences starting from 1' as summary;

COMMIT;