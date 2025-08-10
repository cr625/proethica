-- Phase 2A Migration: Add BFO Ontology Classification Fields
-- Date: 2025-08-08
-- Purpose: Add BFO ontology classification fields to existing models (NON-BREAKING)

BEGIN;

-- Add BFO classification fields to characters table
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'characters' AND column_name = 'bfo_class') THEN
        ALTER TABLE characters ADD COLUMN bfo_class VARCHAR(255) DEFAULT 'BFO_0000040';
        ALTER TABLE characters ADD COLUMN proethica_category VARCHAR(50) DEFAULT 'role';
        ALTER TABLE characters ADD COLUMN ontology_uri VARCHAR(500);
        
        COMMENT ON COLUMN characters.bfo_class IS 'BFO upper ontology classification (default: BFO_0000040 - material entity)';
        COMMENT ON COLUMN characters.proethica_category IS 'ProEthica ontology category (role, principle, obligation, etc.)';
        COMMENT ON COLUMN characters.ontology_uri IS 'Full ontology URI for this character';
        
        RAISE NOTICE 'Added BFO fields to characters table';
    ELSE
        RAISE NOTICE 'BFO fields already exist in characters table';
    END IF;
END $$;

-- Add BFO classification fields to events table  
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'events' AND column_name = 'bfo_class') THEN
        ALTER TABLE events ADD COLUMN bfo_class VARCHAR(255) DEFAULT 'BFO_0000015';
        ALTER TABLE events ADD COLUMN proethica_category VARCHAR(50) DEFAULT 'event';
        ALTER TABLE events ADD COLUMN ontology_uri VARCHAR(500);
        
        COMMENT ON COLUMN events.bfo_class IS 'BFO upper ontology classification (default: BFO_0000015 - process)';
        COMMENT ON COLUMN events.proethica_category IS 'ProEthica ontology category (default: event)';
        COMMENT ON COLUMN events.ontology_uri IS 'Full ontology URI for this event';
        
        RAISE NOTICE 'Added BFO fields to events table';
    ELSE
        RAISE NOTICE 'BFO fields already exist in events table';
    END IF;
END $$;

-- Add BFO classification fields to actions table
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'actions' AND column_name = 'bfo_class') THEN
        ALTER TABLE actions ADD COLUMN bfo_class VARCHAR(255) DEFAULT 'BFO_0000015';
        ALTER TABLE actions ADD COLUMN proethica_category VARCHAR(50) DEFAULT 'action';
        ALTER TABLE actions ADD COLUMN ontology_uri VARCHAR(500);
        ALTER TABLE actions ADD COLUMN is_decision BOOLEAN DEFAULT false;
        
        COMMENT ON COLUMN actions.bfo_class IS 'BFO upper ontology classification (default: BFO_0000015 - process)';
        COMMENT ON COLUMN actions.proethica_category IS 'ProEthica ontology category (action or decision)';
        COMMENT ON COLUMN actions.ontology_uri IS 'Full ontology URI for this action';
        COMMENT ON COLUMN actions.is_decision IS 'Whether this action represents a decision point (BFO disposition)';
        
        RAISE NOTICE 'Added BFO fields to actions table';
    ELSE
        RAISE NOTICE 'BFO fields already exist in actions table';
    END IF;
END $$;

COMMIT;

-- Verification queries
SELECT 'Phase 2A Migration completed successfully!' as status;

SELECT table_name, column_name, data_type, column_default, is_nullable
FROM information_schema.columns 
WHERE table_name IN ('characters', 'events', 'actions')
AND column_name IN ('bfo_class', 'proethica_category', 'ontology_uri', 'is_decision')
ORDER BY table_name, ordinal_position;