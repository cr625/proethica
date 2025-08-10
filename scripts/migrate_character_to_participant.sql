-- Migration: Character to Participant Model Rename + BFO Ontology Fields
-- Date: 2025-08-08
-- Purpose: Rename characters table to participants and add BFO ontology classification fields

BEGIN;

-- 1. Rename the characters table to participants
ALTER TABLE characters RENAME TO participants;

-- 2. Add new ontology classification fields to participants
ALTER TABLE participants ADD COLUMN bfo_class VARCHAR(255) DEFAULT 'BFO_0000040';
ALTER TABLE participants ADD COLUMN proethica_category VARCHAR(50) DEFAULT 'role';
ALTER TABLE participants ADD COLUMN ontology_uri VARCHAR(500);

-- 3. Update foreign key references in other tables
-- Find tables that reference characters.id and update them
DO $$
DECLARE
    rec RECORD;
BEGIN
    -- Find all foreign key constraints that reference characters
    FOR rec IN 
        SELECT 
            tc.table_name, 
            kcu.column_name, 
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            tc.constraint_name
        FROM information_schema.table_constraints AS tc 
        JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name
        WHERE constraint_type = 'FOREIGN KEY' 
        AND ccu.table_name = 'characters'
    LOOP
        -- Drop the old constraint
        EXECUTE 'ALTER TABLE ' || rec.table_name || ' DROP CONSTRAINT ' || rec.constraint_name;
        
        -- Create new constraint referencing participants
        EXECUTE 'ALTER TABLE ' || rec.table_name || ' ADD CONSTRAINT ' || 
                replace(rec.constraint_name, 'characters', 'participants') || 
                ' FOREIGN KEY (' || rec.column_name || ') REFERENCES participants(id)';
                
        RAISE NOTICE 'Updated constraint % in table %', rec.constraint_name, rec.table_name;
    END LOOP;
END $$;

-- 4. Update specific column names (character_id -> participant_id)
-- Check if these columns exist before trying to rename them
DO $$
BEGIN
    -- Update actions table
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'actions' AND column_name = 'character_id') THEN
        ALTER TABLE actions RENAME COLUMN character_id TO participant_id;
        RAISE NOTICE 'Renamed character_id to participant_id in actions table';
    END IF;
    
    -- Update conditions table
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'conditions' AND column_name = 'character_id') THEN
        ALTER TABLE conditions RENAME COLUMN character_id TO participant_id;
        RAISE NOTICE 'Renamed character_id to participant_id in conditions table';
    END IF;
    
    -- Update events table
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'events' AND column_name = 'character_id') THEN
        ALTER TABLE events RENAME COLUMN character_id TO participant_id;
        RAISE NOTICE 'Renamed character_id to participant_id in events table';
    END IF;
    
    -- Update entity_triples table
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'entity_triples' AND column_name = 'character_id') THEN
        ALTER TABLE entity_triples RENAME COLUMN character_id TO participant_id;
        RAISE NOTICE 'Renamed character_id to participant_id in entity_triples table';
    END IF;
END $$;

-- 5. Add BFO classification fields to existing models
-- Events table
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'events' AND column_name = 'bfo_class') THEN
        ALTER TABLE events ADD COLUMN bfo_class VARCHAR(255) DEFAULT 'BFO_0000015'; -- process
        ALTER TABLE events ADD COLUMN proethica_category VARCHAR(50) DEFAULT 'event';
        ALTER TABLE events ADD COLUMN ontology_uri VARCHAR(500);
        RAISE NOTICE 'Added ontology fields to events table';
    END IF;
END $$;

-- Actions table
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'actions' AND column_name = 'bfo_class') THEN
        ALTER TABLE actions ADD COLUMN bfo_class VARCHAR(255) DEFAULT 'BFO_0000015'; -- process
        ALTER TABLE actions ADD COLUMN proethica_category VARCHAR(50) DEFAULT 'action';
        ALTER TABLE actions ADD COLUMN ontology_uri VARCHAR(500);
        ALTER TABLE actions ADD COLUMN is_decision BOOLEAN DEFAULT false;
        RAISE NOTICE 'Added ontology fields to actions table';
    END IF;
END $$;

-- 6. Update any indexes that reference the old table name
DO $$
DECLARE
    idx_rec RECORD;
BEGIN
    FOR idx_rec IN
        SELECT indexname, indexdef 
        FROM pg_indexes 
        WHERE indexdef LIKE '%characters%'
        AND schemaname = 'public'
    LOOP
        EXECUTE 'DROP INDEX ' || idx_rec.indexname;
        EXECUTE replace(idx_rec.indexdef, 'characters', 'participants');
        RAISE NOTICE 'Updated index %', idx_rec.indexname;
    END LOOP;
END $$;

-- 7. Comments for documentation
COMMENT ON TABLE participants IS 'Participants in scenarios (formerly characters table) with BFO ontology classification';
COMMENT ON COLUMN participants.bfo_class IS 'BFO upper ontology classification (default: BFO_0000040 - material entity)';
COMMENT ON COLUMN participants.proethica_category IS 'ProEthica ontology category (role, principle, obligation, etc.)';
COMMENT ON COLUMN participants.ontology_uri IS 'Full ontology URI for this participant';

COMMENT ON COLUMN events.bfo_class IS 'BFO upper ontology classification (default: BFO_0000015 - process)';
COMMENT ON COLUMN events.proethica_category IS 'ProEthica ontology category (default: event)';

COMMENT ON COLUMN actions.bfo_class IS 'BFO upper ontology classification (default: BFO_0000015 - process)';
COMMENT ON COLUMN actions.proethica_category IS 'ProEthica ontology category (action or decision)';
COMMENT ON COLUMN actions.is_decision IS 'Whether this action represents a decision point';

COMMIT;

-- Verification queries
SELECT 'Migration completed successfully!' as status;
SELECT COUNT(*) as participant_count FROM participants;
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'participants' 
ORDER BY ordinal_position;