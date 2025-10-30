-- Migration 014: Create Step 4 Enhanced Analysis Tables
-- Purpose: Store case-level institutional, action-rule, and transformation analysis
-- Part of Step 4 (Enhanced Case Analysis & Synthesis) - Parts D, E, F

-- Part D: Case-level institutional rule analysis
CREATE TABLE IF NOT EXISTS case_institutional_analysis (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE UNIQUE,
    
    -- Principle tensions
    principle_tensions JSONB,  -- [{principle1, principle2, tension_description, symbolic_significance}]
    principle_conflict_description TEXT,
    
    -- Obligation conflicts
    obligation_conflicts JSONB,  -- [{obligation1, obligation2, conflict_description, code_sections}]
    obligation_conflict_description TEXT,
    
    -- Constraining factors
    constraining_factors JSONB,  -- [{constraint, impact_description, type}]
    constraint_influence_description TEXT,
    
    -- Case significance
    case_significance TEXT,  -- Why this case matters / what it represents
    
    -- LLM metadata
    llm_model VARCHAR(100),
    llm_prompt TEXT,
    llm_response TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Part E: Action-rule mapping (three-rule framework)
CREATE TABLE IF NOT EXISTS case_action_mapping (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE UNIQUE,
    
    -- Action Rule (What?)
    actions_taken JSONB,  -- [action labels/descriptions]
    actions_not_taken JSONB,  -- [alternatives not chosen]
    alternatives_available JSONB,  -- [other options]
    capability_constraints JSONB,  -- [what prevented actions]
    resource_constraints JSONB,  -- [what was unavailable]
    
    -- Institutional Rule (Why?)
    justifications JSONB,  -- [reasons for actions]
    oppositions JSONB,  -- [reasons against actions]
    relevant_obligations JSONB,  -- [NSPE Code sections]
    relevant_principles JSONB,  -- [ethical principles]
    
    -- Operations Rule (How?)
    situational_context JSONB,  -- [contextual factors]
    organizational_constraints JSONB,  -- [structural limitations]
    resource_availability JSONB,  -- [what was available]
    key_events JSONB,  -- [events that shaped operations]
    
    -- Steering Rule (Transformation)
    transformation_points JSONB,  -- [moments of rule shift]
    rule_shifts JSONB,  -- [how rules transformed]
    
    -- LLM metadata
    llm_model VARCHAR(100),
    llm_prompt TEXT,
    llm_response TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Part F: Transformation classification
CREATE TABLE IF NOT EXISTS case_transformation (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE UNIQUE,
    
    -- Transformation type
    transformation_type VARCHAR(50),  -- transfer, stalemate, oscillation, phase_lag
    confidence FLOAT,  -- 0.0-1.0
    
    -- Rationale
    type_rationale TEXT,
    indicators JSONB,  -- [evidence for classification]
    
    -- Symbolic significance
    symbolic_significance TEXT,  -- What strategic issue this represents
    
    -- Pattern template
    pattern_id VARCHAR(100),
    pattern_name VARCHAR(255),
    institutional_tension VARCHAR(255),
    typical_transformation VARCHAR(50),
    resolution_approaches JSONB,
    
    -- Similar cases
    similar_case_ids INTEGER[],
    
    -- LLM metadata
    llm_model VARCHAR(100),
    llm_prompt TEXT,
    llm_response TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_case_institutional_case_id
    ON case_institutional_analysis(case_id);

CREATE INDEX IF NOT EXISTS idx_case_action_mapping_case_id
    ON case_action_mapping(case_id);

CREATE INDEX IF NOT EXISTS idx_case_transformation_case_id
    ON case_transformation(case_id);

CREATE INDEX IF NOT EXISTS idx_case_transformation_type
    ON case_transformation(transformation_type);

CREATE INDEX IF NOT EXISTS idx_case_transformation_pattern
    ON case_transformation(pattern_id);

-- Comments
COMMENT ON TABLE case_institutional_analysis IS
    'Step 4 Part D: Case-level institutional rule analysis (principles, obligations, constraints)';

COMMENT ON TABLE case_action_mapping IS
    'Step 4 Part E: Three-rule framework mapping (action, institutional, operations, steering rules)';

COMMENT ON TABLE case_transformation IS
    'Step 4 Part F: Transformation classification and symbolic significance';

COMMENT ON COLUMN case_transformation.transformation_type IS
    'transfer: escalation to new rules; stalemate: trapped; oscillation: cycling; phase_lag: misaligned frames';
