-- Migration: Add temporary_concepts table for storing extracted concepts during review workflow
-- Date: 2025-01-21
-- Purpose: Create persistent storage for guideline concepts that can be manipulated before commitment

-- Create the temporary_concepts table
CREATE TABLE IF NOT EXISTS temporary_concepts (
    id SERIAL PRIMARY KEY,
    
    -- Links to source
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
    
    -- Session management
    session_id VARCHAR(100) NOT NULL,
    
    -- The concept data (JSONB for flexibility)
    concept_data JSONB NOT NULL,
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'pending',
    
    -- Extraction metadata
    extraction_method VARCHAR(50),
    extraction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    
    -- User tracking
    created_by VARCHAR(100),
    modified_by VARCHAR(100),
    
    -- Additional metadata
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_temp_concepts_session ON temporary_concepts(session_id);
CREATE INDEX IF NOT EXISTS idx_temp_concepts_document ON temporary_concepts(document_id);
CREATE INDEX IF NOT EXISTS idx_temp_concepts_world ON temporary_concepts(world_id);
CREATE INDEX IF NOT EXISTS idx_temp_concepts_status ON temporary_concepts(status);
CREATE INDEX IF NOT EXISTS idx_temp_concepts_expires ON temporary_concepts(expires_at);

-- Create compound index for common queries
CREATE INDEX IF NOT EXISTS idx_temp_concepts_doc_status ON temporary_concepts(document_id, status);
CREATE INDEX IF NOT EXISTS idx_temp_concepts_session_status ON temporary_concepts(session_id, status);

-- Add GIN index for JSONB queries
CREATE INDEX IF NOT EXISTS idx_temp_concepts_data ON temporary_concepts USING GIN(concept_data);
CREATE INDEX IF NOT EXISTS idx_temp_concepts_metadata ON temporary_concepts USING GIN(metadata);

-- Create function to automatically update last_modified timestamp
CREATE OR REPLACE FUNCTION update_temp_concepts_modified()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for auto-updating last_modified
DROP TRIGGER IF EXISTS update_temp_concepts_modified_trigger ON temporary_concepts;
CREATE TRIGGER update_temp_concepts_modified_trigger
    BEFORE UPDATE ON temporary_concepts
    FOR EACH ROW
    EXECUTE FUNCTION update_temp_concepts_modified();

-- Create function to cleanup expired concepts (can be called periodically)
CREATE OR REPLACE FUNCTION cleanup_expired_temp_concepts()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM temporary_concepts 
    WHERE expires_at < CURRENT_TIMESTAMP
    OR (expires_at IS NULL AND extraction_timestamp < CURRENT_TIMESTAMP - INTERVAL '7 days');
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Add comment to table for documentation
COMMENT ON TABLE temporary_concepts IS 'Temporary storage for extracted guideline concepts during review and manipulation workflow before final commitment to ontology';

-- Add comments to important columns
COMMENT ON COLUMN temporary_concepts.session_id IS 'Groups concepts from the same extraction session';
COMMENT ON COLUMN temporary_concepts.concept_data IS 'JSON structure containing concept details: label, type, description, source_text, confidence, is_new, ontology_match, selected, edited, original_data';
COMMENT ON COLUMN temporary_concepts.status IS 'Workflow status: pending, reviewed, committed, discarded';
COMMENT ON COLUMN temporary_concepts.expires_at IS 'Auto-cleanup timestamp, defaults to 7 days from creation';

-- Grant appropriate permissions (adjust as needed for your setup)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON temporary_concepts TO your_app_user;
-- GRANT USAGE, SELECT ON SEQUENCE temporary_concepts_id_seq TO your_app_user;