-- Migration: Add extraction_section_prompts table for multi-section case extraction
-- Date: 2025-10-01
-- Purpose: Store prompts for extracting ProEthica concepts from NSPE case sections
-- Note: Separate from section_prompt_templates (used for LangExtract ontology-driven extraction)

-- Create extraction_section_prompts table
CREATE TABLE IF NOT EXISTS extraction_section_prompts (
    id SERIAL PRIMARY KEY,

    -- Section identification
    section_type VARCHAR(50) NOT NULL,  -- 'facts', 'discussion', 'questions', 'conclusions', 'dissenting_opinion', 'references'
    extraction_pass INTEGER NOT NULL,   -- 1 (Contextual), 2 (Normative), 3 (Behavioral), 4 (Synthesis)
    concept_type VARCHAR(50) NOT NULL,  -- 'roles', 'states', 'resources', 'principles', 'obligations', etc.

    -- Prompt components
    system_prompt TEXT,
    instruction_template TEXT,  -- May contain {section_text}, {existing_entities}, etc.
    examples JSONB,             -- Few-shot examples specific to section

    -- Section-specific extraction guidance
    extraction_guidance TEXT,
    -- Examples:
    -- "Extract roles as they existed in the scenario" (Facts)
    -- "Extract roles mentioned in ethical reasoning. Match to entities from Facts section when possible." (Discussion)

    -- Metadata
    prompt_name VARCHAR(200),
    description TEXT,

    -- Versioning
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,

    -- Usage statistics
    times_used INTEGER DEFAULT 0,
    avg_entities_extracted FLOAT,
    avg_confidence FLOAT,
    last_used_at TIMESTAMP,

    -- Constraints
    CONSTRAINT unique_extraction_section_prompt UNIQUE (section_type, extraction_pass, concept_type, version),
    CONSTRAINT valid_section_type CHECK (section_type IN ('facts', 'discussion', 'questions', 'conclusions', 'dissenting_opinion', 'references', 'synthesis')),
    CONSTRAINT valid_extraction_pass CHECK (extraction_pass BETWEEN 1 AND 4),
    CONSTRAINT valid_concept_type CHECK (concept_type IN ('roles', 'states', 'resources', 'principles', 'obligations', 'constraints', 'capabilities', 'actions', 'events', 'synthesis'))
);

-- Create indexes for performance
CREATE INDEX idx_extraction_section_type ON extraction_section_prompts(section_type);
CREATE INDEX idx_extraction_pass ON extraction_section_prompts(extraction_pass);
CREATE INDEX idx_extraction_concept ON extraction_section_prompts(concept_type);
CREATE INDEX idx_extraction_active ON extraction_section_prompts(section_type, extraction_pass, concept_type, is_active);

-- Add comments
COMMENT ON TABLE extraction_section_prompts IS 'Storage for section-specific ProEthica concept extraction prompts for multi-section NSPE case processing';
COMMENT ON COLUMN extraction_section_prompts.section_type IS 'NSPE case section: facts, discussion, questions, conclusions, dissenting_opinion, references, synthesis';
COMMENT ON COLUMN extraction_section_prompts.extraction_pass IS 'Extraction pass: 1=Contextual, 2=Normative, 3=Behavioral, 4=Synthesis';
COMMENT ON COLUMN extraction_section_prompts.concept_type IS 'ProEthica concept type: roles, states, resources, principles, obligations, constraints, capabilities, actions, events';
COMMENT ON COLUMN extraction_section_prompts.extraction_guidance IS 'Section-specific instructions on how to extract this concept type from this section';

-- Insert baseline prompts for Facts section (Pass 1)
-- These represent the working prompts from current single-section implementation

INSERT INTO extraction_section_prompts (
    section_type, extraction_pass, concept_type,
    prompt_name, extraction_guidance, description,
    created_by, is_active
) VALUES
    -- Pass 1 - Contextual Framework (Facts section - working baseline)
    ('facts', 1, 'roles',
     'Facts - Roles (Contextual)',
     'Extract roles as they existed in the scenario. Focus on professional actors and their classifications. Identify WHO acts in the case.',
     'Baseline role extraction for Facts section. Uses dual extraction pattern to discover new role classes and extract individuals.',
     'system', true),

    ('facts', 1, 'states',
     'Facts - States (Contextual)',
     'Extract situational states that establish environmental conditions. Focus on WHEN obligations activate. Identify conditions triggering ethical considerations.',
     'Baseline state extraction for Facts section. Captures environmental triggers and situational contexts.',
     'system', true),

    ('facts', 1, 'resources',
     'Facts - Resources (Contextual)',
     'Extract informational and physical resources available in the scenario. Focus on WHAT guides decisions. Identify documents, guidelines, standards, and tools.',
     'Baseline resource extraction for Facts section. Identifies available professional knowledge and tools.',
     'system', true),

    -- Pass 2 - Normative Requirements (Facts section - working baseline)
    ('facts', 2, 'principles',
     'Facts - Principles (Normative)',
     'Extract fundamental ethical principles implicit in the facts. Focus on WHY (foundations). Identify core values at stake in the scenario.',
     'Baseline principle extraction for Facts section. Identifies foundational ethical values evident in case facts.',
     'system', true),

    ('facts', 2, 'obligations',
     'Facts - Obligations (Normative)',
     'Extract professional duties and requirements evident from the facts. Focus on WHAT MUST be done. Identify concrete professional obligations.',
     'Baseline obligation extraction for Facts section. Captures professional duties arising from the scenario.',
     'system', true),

    ('facts', 2, 'constraints',
     'Facts - Constraints (Normative)',
     'Extract inviolable boundaries and limitations evident in the scenario. Focus on WHAT CANNOT be done. Identify hard constraints on actions.',
     'Baseline constraint extraction for Facts section. Identifies non-negotiable boundaries.',
     'system', true),

    ('facts', 2, 'capabilities',
     'Facts - Capabilities (Normative)',
     'Extract required competencies evident from professional context. Focus on WHO CAN fulfill obligations. Identify needed skills and expertise.',
     'Baseline capability extraction for Facts section. Identifies required professional competencies.',
     'system', true),

    -- Pass 3 - Temporal Dynamics (Facts section - working baseline)
    ('facts', 3, 'actions',
     'Facts - Actions (Temporal)',
     'Extract volitional professional decisions and behaviors. Focus on deliberate choices made by professionals. Capture WHAT happens through intentional acts.',
     'Baseline action extraction for Facts section. Identifies professional decisions and volitional behaviors.',
     'system', true),

    ('facts', 3, 'events',
     'Facts - Events (Temporal)',
     'Extract temporal occurrences and happenings. Focus on events that trigger or result from professional actions. Capture WHAT happens over time.',
     'Baseline event extraction for Facts section. Identifies temporal dynamics and occurrences.',
     'system', true);

-- Log migration completion
SELECT 'Migration completed: extraction_section_prompts table created with ' || COUNT(*) || ' baseline Facts prompts'
FROM extraction_section_prompts;
