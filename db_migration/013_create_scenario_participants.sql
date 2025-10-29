-- Migration 013: Create scenario_participants table for Stage 3
-- Purpose: Store enriched character profiles for interactive teaching scenarios
-- Part of Step 5 (Interactive Scenario Generation) - Stage 3 (Participant Mapping)

-- Create scenario_participants table
CREATE TABLE IF NOT EXISTS scenario_participants (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Identity
    participant_id VARCHAR(255) NOT NULL,  -- Internal ID (e.g., "participant_1")
    source_role_uri VARCHAR(500),  -- Original role entity URI
    name VARCHAR(255) NOT NULL,  -- Character name (e.g., "Engineer L", "Client X")
    role_type VARCHAR(255),  -- Professional role type

    -- Profile
    background TEXT,  -- Professional background and experience
    expertise JSONB,  -- Array of expertise areas
    qualifications JSONB,  -- Array of licenses/certifications

    -- Character arc elements
    motivations JSONB,  -- Array of character motivations
    goals JSONB,  -- Array of character goals
    obligations JSONB,  -- Array of professional obligations
    constraints JSONB,  -- Array of constraints limiting actions

    -- Narrative elements
    ethical_tensions JSONB,  -- Array of internal/external conflicts
    character_arc TEXT,  -- How character changes/is challenged
    narrative_role VARCHAR(50),  -- protagonist, antagonist, supporting, mentor, etc.

    -- Relationships
    relationships JSONB,  -- Array of {type, target_id, target_name, description}

    -- LLM Enhancement
    llm_enhanced BOOLEAN DEFAULT FALSE,
    llm_enrichment JSONB,  -- {enhanced_arc, suggested_motivations, teaching_notes}
    llm_model VARCHAR(100),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure unique participant per case
    UNIQUE(case_id, participant_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_scenario_participants_case_id
    ON scenario_participants(case_id);

CREATE INDEX IF NOT EXISTS idx_scenario_participants_narrative_role
    ON scenario_participants(narrative_role);

CREATE INDEX IF NOT EXISTS idx_scenario_participants_source_role
    ON scenario_participants(source_role_uri);

-- Create scenario_relationship_map table for explicit relationship tracking
CREATE TABLE IF NOT EXISTS scenario_relationship_map (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    source_participant_id VARCHAR(255) NOT NULL,
    target_participant_id VARCHAR(255) NOT NULL,

    relationship_type VARCHAR(100),  -- contracted_by, supervises, advises, etc.
    relationship_description TEXT,

    -- Bidirectional flag
    is_bidirectional BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure unique relationships
    UNIQUE(case_id, source_participant_id, target_participant_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_scenario_relationships_case
    ON scenario_relationship_map(case_id);

CREATE INDEX IF NOT EXISTS idx_scenario_relationships_source
    ON scenario_relationship_map(source_participant_id);

CREATE INDEX IF NOT EXISTS idx_scenario_relationships_target
    ON scenario_relationship_map(target_participant_id);

-- Comments
COMMENT ON TABLE scenario_participants IS
    'Stage 3: Participant Mapping - Enriched character profiles for interactive teaching scenarios';

COMMENT ON COLUMN scenario_participants.participant_id IS
    'Internal participant ID (e.g., participant_1, participant_2) - stable across regenerations';

COMMENT ON COLUMN scenario_participants.narrative_role IS
    'Narrative role in teaching scenario: protagonist (primary decision-maker), antagonist (opposing force), supporting, mentor';

COMMENT ON COLUMN scenario_participants.llm_enrichment IS
    'LLM-enhanced content: {enhanced_arc: fuller narrative, suggested_motivations: [], teaching_notes: pedagogical insights}';

COMMENT ON TABLE scenario_relationship_map IS
    'Explicit bidirectional relationships between scenario participants for visualization';
