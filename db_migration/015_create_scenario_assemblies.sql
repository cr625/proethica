-- Migration 015: Create scenario_assemblies table
-- Created: 2025-11-03
-- Purpose: Store assembled scenarios from Step 5 Stage 7

CREATE TABLE IF NOT EXISTS scenario_assemblies (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Assembled scenario data (complete JSON structure)
    scenario_data JSONB NOT NULL,

    -- Quick access metadata
    completeness_score FLOAT DEFAULT 0.0,  -- 0.0-1.0 based on stages included
    stages_included INTEGER DEFAULT 0,      -- Count of stages that contributed data (max 5: timeline, participants, decisions, causal, normative)
    total_components INTEGER DEFAULT 0,     -- Total timepoints + participants + decisions

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Ensure one scenario per case (can be replaced with newer generation)
    UNIQUE(case_id)
);

-- Index for fast case lookup
CREATE INDEX IF NOT EXISTS idx_scenario_assemblies_case_id ON scenario_assemblies(case_id);

-- Index for completeness queries (find well-formed scenarios)
CREATE INDEX IF NOT EXISTS idx_scenario_assemblies_completeness ON scenario_assemblies(completeness_score);

-- Comments
COMMENT ON TABLE scenario_assemblies IS 'Assembled scenarios from Step 5 Stage 7 - combines timeline, participants, decisions, causal chains, normative framework';
COMMENT ON COLUMN scenario_assemblies.scenario_data IS 'Complete assembled scenario as JSONB (all Stage 1-6 outputs combined)';
COMMENT ON COLUMN scenario_assemblies.completeness_score IS 'Completeness score 0.0-1.0 (0.2 per stage: timeline, participants, decisions, causal, normative)';
COMMENT ON COLUMN scenario_assemblies.stages_included IS 'Number of stages that contributed data (1-5)';
