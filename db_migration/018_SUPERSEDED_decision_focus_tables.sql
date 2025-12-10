-- Migration 018: Create decision focus and argument tables
-- Part of Step 4 Parts E & F: Pros/Cons Analysis for Scenario Generation
-- Created: 2025-12-09
-- Purpose: Store decision focuses and pro/con arguments extracted from cases
--
-- References:
-- - Hobbs & Moore (2005): Scenario-directed computational framework
-- - IAAI Paper: "Pros and Cons in Ethical Decisions" - Evaluative AI approach

-- Decision focuses extracted from cases
-- These identify key points where ethical choices must be made
CREATE TABLE IF NOT EXISTS case_decision_focuses (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Focus identification
    focus_id VARCHAR(50) NOT NULL,           -- e.g., "DF1", "DF2"
    focus_number INTEGER,                     -- Sequential number within case

    -- Core content
    description TEXT NOT NULL,                -- What choice must be made
    decision_question TEXT,                   -- The question form of the decision

    -- Participants and provisions
    involved_roles TEXT[],                    -- Which roles are involved (e.g., ["Engineer A", "Client"])
    applicable_provisions TEXT[],             -- Which NSPE provisions apply (e.g., ["II.2.b", "I.1"])

    -- Decision options identified
    options JSONB,                            -- Array of {option_id, description, is_board_choice}

    -- Board resolution
    board_resolution TEXT,                    -- How the Board resolved this focus
    board_reasoning TEXT,                     -- Why the Board chose this resolution

    -- Metadata
    extraction_method VARCHAR(50),            -- 'llm', 'rule_based', 'manual'
    llm_model_used VARCHAR(100),
    confidence FLOAT,
    metadata JSONB,                           -- Additional extraction details
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(case_id, focus_id)
);

-- Arguments for/against each decision option
CREATE TABLE IF NOT EXISTS decision_arguments (
    id SERIAL PRIMARY KEY,
    focus_id INTEGER NOT NULL REFERENCES case_decision_focuses(id) ON DELETE CASCADE,

    -- Argument identification
    argument_id VARCHAR(50),                  -- e.g., "PRO1", "CON1"
    argument_type VARCHAR(10) NOT NULL,       -- 'pro' or 'con'
    option_id VARCHAR(50),                    -- Links to options JSONB in case_decision_focuses

    -- Argument content
    argument_text TEXT NOT NULL,              -- The argument itself
    reasoning TEXT,                           -- Expanded reasoning/justification

    -- Supporting evidence
    supporting_provision VARCHAR(50),         -- e.g., "II.2.b"
    provision_text TEXT,                      -- Relevant excerpt from NSPE Code

    -- Precedent linking (Pass 2)
    supporting_precedent_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    precedent_case_number VARCHAR(50),        -- e.g., "92-1"
    precedent_description TEXT,               -- Brief description of how precedent applies
    precedent_relationship VARCHAR(50),       -- 'supporting', 'contrasting', 'analogous'

    -- Quality indicators
    strength VARCHAR(20),                     -- 'strong', 'moderate', 'weak'
    confidence FLOAT,

    -- Metadata
    extraction_pass INTEGER,                  -- 1 = argument gen, 2 = precedent linking
    llm_model_used VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Evaluation summaries for each decision focus
-- Provides structured guidance for analysis
CREATE TABLE IF NOT EXISTS decision_evaluation_summaries (
    id SERIAL PRIMARY KEY,
    focus_id INTEGER NOT NULL REFERENCES case_decision_focuses(id) ON DELETE CASCADE,

    -- Evaluation steps
    evaluation_steps JSONB,                   -- Array of {step_number, description}

    -- Key considerations
    key_principles TEXT[],                    -- Principles at stake
    key_tensions TEXT[],                      -- Tension points to consider

    -- Board alignment
    board_alignment_score FLOAT,              -- How well arguments align with Board decision
    board_alignment_explanation TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(focus_id)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_decision_focuses_case
    ON case_decision_focuses(case_id);

CREATE INDEX IF NOT EXISTS idx_decision_focuses_focus_id
    ON case_decision_focuses(focus_id);

CREATE INDEX IF NOT EXISTS idx_decision_arguments_focus
    ON decision_arguments(focus_id);

CREATE INDEX IF NOT EXISTS idx_decision_arguments_type
    ON decision_arguments(argument_type);

CREATE INDEX IF NOT EXISTS idx_decision_arguments_precedent
    ON decision_arguments(supporting_precedent_id);

-- GIN indexes for array searching
CREATE INDEX IF NOT EXISTS idx_decision_focuses_roles
    ON case_decision_focuses USING GIN (involved_roles);

CREATE INDEX IF NOT EXISTS idx_decision_focuses_provisions
    ON case_decision_focuses USING GIN (applicable_provisions);

-- Comments for documentation
COMMENT ON TABLE case_decision_focuses IS
    'Key decision points in ethics cases where choices must be made. Part of Step 4 Part E.';

COMMENT ON TABLE decision_arguments IS
    'Pro/con arguments for each decision option with precedent linking. Part of Step 4 Part F.';

COMMENT ON TABLE decision_evaluation_summaries IS
    'Structured evaluation guidance for each decision focus.';

COMMENT ON COLUMN case_decision_focuses.options IS
    'JSON array: [{"option_id": "O1", "description": "Disclose AI use", "is_board_choice": true}]';

COMMENT ON COLUMN decision_arguments.precedent_relationship IS
    'How precedent relates: supporting (same outcome), contrasting (different outcome), analogous (similar situation)';

COMMENT ON COLUMN decision_arguments.extraction_pass IS
    'Pass 1 = initial argument generation, Pass 2 = precedent linking enhancement';
