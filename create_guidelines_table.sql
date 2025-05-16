-- Create guidelines table matching the SQLAlchemy model definition
CREATE TABLE IF NOT EXISTS guidelines (
    id SERIAL PRIMARY KEY,
    world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    source_url VARCHAR(1024),
    file_path VARCHAR(1024),
    file_type VARCHAR(50),
    embedding FLOAT[],
    guideline_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on world_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_guidelines_world_id ON guidelines(world_id);

-- Add or update required columns in entity_triples table
DO $$
BEGIN
    -- Add guideline_id column if it doesn't exist
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'entity_triples' AND column_name = 'guideline_id'
    ) THEN
        ALTER TABLE entity_triples ADD COLUMN guideline_id INTEGER REFERENCES guidelines(id) ON DELETE CASCADE;
    END IF;
    
    -- Add world_id column if it doesn't exist
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'entity_triples' AND column_name = 'world_id'
    ) THEN
        ALTER TABLE entity_triples ADD COLUMN world_id INTEGER REFERENCES worlds(id) ON DELETE CASCADE;
    END IF;
    
    -- Add label columns if they don't exist
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'entity_triples' AND column_name = 'subject_label'
    ) THEN
        ALTER TABLE entity_triples ADD COLUMN subject_label VARCHAR(255);
    END IF;
    
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'entity_triples' AND column_name = 'predicate_label'
    ) THEN
        ALTER TABLE entity_triples ADD COLUMN predicate_label VARCHAR(255);
    END IF;
    
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'entity_triples' AND column_name = 'object_label'
    ) THEN
        ALTER TABLE entity_triples ADD COLUMN object_label VARCHAR(255);
    END IF;
    
    -- Add temporal columns if they don't exist
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'entity_triples' AND column_name = 'temporal_confidence'
    ) THEN
        ALTER TABLE entity_triples ADD COLUMN temporal_confidence FLOAT DEFAULT 1.0;
    END IF;
    
    IF NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'entity_triples' AND column_name = 'temporal_context'
    ) THEN
        ALTER TABLE entity_triples ADD COLUMN temporal_context JSONB DEFAULT '{}';
    END IF;
END $$;
