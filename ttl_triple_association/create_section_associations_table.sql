-- SQL migration script to create the section_ontology_associations table
-- This table stores associations between document sections and ontology concepts

-- Check if the table exists, if not create it
CREATE TABLE IF NOT EXISTS section_ontology_associations (
    id SERIAL PRIMARY KEY,
    section_id INTEGER NOT NULL,
    concept_uri TEXT NOT NULL,
    concept_label TEXT,
    match_score FLOAT NOT NULL,
    match_type TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Add indexes for performance
    CONSTRAINT section_concept_unique UNIQUE (section_id, concept_uri),
    CONSTRAINT fk_section FOREIGN KEY (section_id) REFERENCES document_sections (id) ON DELETE CASCADE
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_section_ontology_section_id ON section_ontology_associations (section_id);
CREATE INDEX IF NOT EXISTS idx_section_ontology_concept_uri ON section_ontology_associations (concept_uri);
CREATE INDEX IF NOT EXISTS idx_section_ontology_match_type ON section_ontology_associations (match_type);
CREATE INDEX IF NOT EXISTS idx_section_ontology_match_score ON section_ontology_associations (match_score DESC);

-- Add comment to explain table purpose
COMMENT ON TABLE section_ontology_associations IS 'Stores associations between document sections and ontology concepts using the TTL-based approach';
