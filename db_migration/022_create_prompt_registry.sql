-- Migration: Create prompt_registry table for tracking LLM prompts across phases
-- Date: 2025-12-19
-- Purpose: Registry mapping prompts to extraction phases and source files
-- Designed for future NeMo/DSPy integration

-- Create prompt_registry table
CREATE TABLE IF NOT EXISTS prompt_registry (
    id SERIAL PRIMARY KEY,

    -- Unique identifier for the prompt
    prompt_key VARCHAR(100) UNIQUE NOT NULL,  -- e.g., 'pass1.roles', 'step4.decision_points'

    -- Phase/Step categorization
    phase VARCHAR(20) NOT NULL,               -- 'pass1', 'pass2', 'pass3', 'step4', 'step5'
    concept_type VARCHAR(50) NOT NULL,        -- 'roles', 'obligations', 'decision_points', etc.
    section_type VARCHAR(50) DEFAULT 'all',   -- 'facts', 'discussion', 'all'

    -- Source code location
    source_file VARCHAR(200) NOT NULL,        -- Relative path from project root
    source_function VARCHAR(100) NOT NULL,    -- Function/method name containing prompt

    -- Documentation
    description TEXT,
    academic_references TEXT[],               -- Citations: e.g., ARRAY['McLaren 2003', 'Kong 2020']

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Future: NeMo/DSPy integration fields
    nemo_compatible BOOLEAN DEFAULT FALSE,    -- Flag for NeMo MIPROv2 export
    dspy_module VARCHAR(100),                 -- DSPy module name for optimization
    langsmith_id VARCHAR(100),                -- LangSmith Hub prompt ID

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_prompt_registry_phase ON prompt_registry(phase);
CREATE INDEX idx_prompt_registry_concept ON prompt_registry(concept_type);
CREATE INDEX idx_prompt_registry_active ON prompt_registry(is_active);
CREATE INDEX idx_prompt_registry_phase_concept ON prompt_registry(phase, concept_type);

-- Comments for documentation
COMMENT ON TABLE prompt_registry IS 'Registry mapping LLM prompts to extraction phases, source files, and future optimization tools';
COMMENT ON COLUMN prompt_registry.prompt_key IS 'Unique identifier: phase.concept_type (e.g., pass1.roles, step4.decision_points)';
COMMENT ON COLUMN prompt_registry.phase IS 'Extraction phase: pass1=Contextual, pass2=Normative, pass3=Temporal, step4=Analysis, step5=Interactive';
COMMENT ON COLUMN prompt_registry.concept_type IS 'ProEthica concept or analysis type being extracted';
COMMENT ON COLUMN prompt_registry.source_file IS 'Relative path to Python file containing the prompt';
COMMENT ON COLUMN prompt_registry.source_function IS 'Function/method name that generates the prompt';
COMMENT ON COLUMN prompt_registry.academic_references IS 'Array of academic citations grounding the prompt design';
COMMENT ON COLUMN prompt_registry.nemo_compatible IS 'Future: Flag indicating prompt is ready for NeMo MIPROv2 optimization';
COMMENT ON COLUMN prompt_registry.dspy_module IS 'Future: DSPy module name for declarative prompt optimization';
COMMENT ON COLUMN prompt_registry.langsmith_id IS 'Future: LangSmith Hub prompt ID for version control';

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Migration 022 completed: prompt_registry table created';
END $$;
