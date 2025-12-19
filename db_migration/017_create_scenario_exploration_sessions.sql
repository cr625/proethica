-- Migration: Create scenario exploration sessions tables
-- Purpose: Track user's interactive scenario explorations with their choices
-- Date: 2025-12-19

-- Main session table
CREATE TABLE IF NOT EXISTS scenario_exploration_sessions (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    session_uuid VARCHAR(36) NOT NULL UNIQUE,

    -- Session state
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress',  -- 'in_progress', 'completed', 'abandoned'
    current_decision_index INTEGER NOT NULL DEFAULT 0,

    -- Exploration mode
    exploration_mode VARCHAR(20) NOT NULL DEFAULT 'interactive',  -- 'interactive', 'guided', 'free'

    -- Event calculus state (JSON)
    active_fluents JSONB DEFAULT '[]'::jsonb,  -- Current state of world
    terminated_fluents JSONB DEFAULT '[]'::jsonb,  -- Fluents no longer active

    -- Metadata
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    last_activity_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Optional user tracking (if authenticated)
    user_id INTEGER,

    -- Analysis results (populated on completion)
    final_analysis JSONB,

    CONSTRAINT valid_status CHECK (status IN ('in_progress', 'completed', 'abandoned'))
);

-- User choices at each decision point
CREATE TABLE IF NOT EXISTS scenario_exploration_choices (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES scenario_exploration_sessions(id) ON DELETE CASCADE,

    -- Which decision point
    decision_point_index INTEGER NOT NULL,
    decision_point_uri VARCHAR(500),
    decision_point_label TEXT,

    -- The choice made
    chosen_option_index INTEGER NOT NULL,
    chosen_option_label TEXT,
    chosen_option_uri VARCHAR(500),

    -- What the board actually chose (for comparison)
    board_choice_index INTEGER,
    board_choice_label TEXT,
    matches_board_choice BOOLEAN,

    -- LLM-generated consequences of this choice
    consequences_narrative TEXT,
    fluents_initiated JSONB DEFAULT '[]'::jsonb,
    fluents_terminated JSONB DEFAULT '[]'::jsonb,

    -- Context provided to LLM for generating consequences
    context_provided JSONB,

    -- Timing
    chosen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    time_spent_seconds INTEGER,  -- How long user deliberated

    CONSTRAINT unique_session_decision UNIQUE (session_id, decision_point_index)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_exploration_sessions_case ON scenario_exploration_sessions(case_id);
CREATE INDEX IF NOT EXISTS idx_exploration_sessions_status ON scenario_exploration_sessions(status);
CREATE INDEX IF NOT EXISTS idx_exploration_sessions_uuid ON scenario_exploration_sessions(session_uuid);
CREATE INDEX IF NOT EXISTS idx_exploration_choices_session ON scenario_exploration_choices(session_id);

-- View for analyzing user choices vs board choices
CREATE OR REPLACE VIEW exploration_choice_analysis AS
SELECT
    ses.case_id,
    ses.session_uuid,
    ses.status as session_status,
    ch.decision_point_index,
    ch.decision_point_label,
    ch.chosen_option_label as user_choice,
    ch.board_choice_label,
    ch.matches_board_choice,
    ch.time_spent_seconds,
    ch.chosen_at
FROM scenario_exploration_sessions ses
JOIN scenario_exploration_choices ch ON ses.id = ch.session_id
ORDER BY ses.case_id, ses.session_uuid, ch.decision_point_index;

-- Comments
COMMENT ON TABLE scenario_exploration_sessions IS 'Tracks user interactive scenario exploration sessions';
COMMENT ON TABLE scenario_exploration_choices IS 'Records user choices at each decision point with LLM-generated consequences';
COMMENT ON COLUMN scenario_exploration_sessions.active_fluents IS 'Event calculus fluents currently holding true';
COMMENT ON COLUMN scenario_exploration_choices.consequences_narrative IS 'LLM-generated narrative of what happens after this choice';
