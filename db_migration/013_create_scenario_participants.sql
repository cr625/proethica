-- Migration 013: Create scenario_participants table
-- Part of Step 5 Stage 3: Participant Mapping
-- Created: 2025-11-16
-- Purpose: Store enriched participant profiles for teaching scenarios

CREATE TABLE IF NOT EXISTS scenario_participants (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    role_entity_uri TEXT,  -- Link to original role entity from extraction

    -- Basic participant info
    name VARCHAR(200) NOT NULL,  -- e.g., "Engineer A", "Client X"
    title VARCHAR(300),           -- e.g., "Senior Structural Engineer"
    background TEXT,              -- Professional context and experience

    -- Rich profile data (LLM-enhanced)
    motivations TEXT[],           -- Array of motivation strings
    ethical_tensions TEXT[],      -- Array of competing obligations/values
    character_arc TEXT,           -- How participant develops through case

    -- Relationships with other participants
    key_relationships JSONB,      -- [{"participant_id": "r1", "relationship": "reports to", "description": "..."}]

    -- Metadata
    metadata JSONB,               -- LLM usage, confidence, extraction details
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_scenario_participants_case
    ON scenario_participants(case_id);

CREATE INDEX IF NOT EXISTS idx_scenario_participants_role
    ON scenario_participants(role_entity_uri);

CREATE INDEX IF NOT EXISTS idx_scenario_participants_name
    ON scenario_participants(name);

-- Comments
COMMENT ON TABLE scenario_participants IS
    'Enhanced participant profiles for teaching scenarios, enriched from role entities using LLM analysis';

COMMENT ON COLUMN scenario_participants.role_entity_uri IS
    'URI of the original role entity from extraction (links back to TemporaryRDFStorage or OntServe)';

COMMENT ON COLUMN scenario_participants.motivations IS
    'What drives this participant''s decisions and actions';

COMMENT ON COLUMN scenario_participants.ethical_tensions IS
    'Competing obligations, values, or pressures this participant faces';

COMMENT ON COLUMN scenario_participants.character_arc IS
    'How this participant changes or develops through the ethical dilemma';

COMMENT ON COLUMN scenario_participants.key_relationships IS
    'JSON array of relationships: [{"participant_id": "r1", "relationship": "reports to", "description": "...", "role_entity_uri": "..."}]';

COMMENT ON COLUMN scenario_participants.metadata IS
    'LLM usage statistics, confidence scores, extraction timestamp, etc.';
