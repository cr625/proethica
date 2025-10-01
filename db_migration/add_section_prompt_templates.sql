-- Migration: Add section_prompt_templates table for multi-section extraction
-- Date: 2025-10-01
-- Purpose: Store section-specific extraction prompt templates for NSPE case structure

-- Create section_prompt_templates table
CREATE TABLE IF NOT EXISTS section_prompt_templates (
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
    -- "Extract roles mentioned in ethical reasoning" (Discussion)
    -- "Extract roles involved in the ethical question" (Questions)

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

    -- Constraints
    CONSTRAINT unique_section_prompt UNIQUE (section_type, extraction_pass, concept_type, version),
    CONSTRAINT valid_section_type CHECK (section_type IN ('facts', 'discussion', 'questions', 'conclusions', 'dissenting_opinion', 'references', 'synthesis')),
    CONSTRAINT valid_extraction_pass CHECK (extraction_pass BETWEEN 1 AND 4),
    CONSTRAINT valid_concept_type CHECK (concept_type IN ('roles', 'states', 'resources', 'principles', 'obligations', 'constraints', 'capabilities', 'actions', 'events', 'synthesis'))
);

-- Create indexes for performance
CREATE INDEX idx_section_prompt_section_type ON section_prompt_templates(section_type);
CREATE INDEX idx_section_prompt_pass ON section_prompt_templates(extraction_pass);
CREATE INDEX idx_section_prompt_concept ON section_prompt_templates(concept_type);
CREATE INDEX idx_section_prompt_active ON section_prompt_templates(section_type, extraction_pass, concept_type, is_active);

-- Add comments
COMMENT ON TABLE section_prompt_templates IS 'Storage for section-specific extraction prompt templates enabling modular multi-section case extraction';
COMMENT ON COLUMN section_prompt_templates.section_type IS 'NSPE case section: facts, discussion, questions, conclusions, dissenting_opinion, references, synthesis';
COMMENT ON COLUMN section_prompt_templates.extraction_pass IS 'Extraction pass number: 1=Contextual, 2=Normative, 3=Behavioral, 4=Synthesis';
COMMENT ON COLUMN section_prompt_templates.concept_type IS 'ProEthica concept type being extracted in this section';
COMMENT ON COLUMN section_prompt_templates.extraction_guidance IS 'Section-specific instructions for how to extract concepts from this type of content';

-- Insert baseline prompts for Facts section (Pass 1)
-- These are the working prompts from current implementation

INSERT INTO section_prompt_templates (
    section_type, extraction_pass, concept_type,
    prompt_name, extraction_guidance, description,
    created_by, is_active
) VALUES
    -- Pass 1 - Contextual Framework (Facts section baseline)
    ('facts', 1, 'roles',
     'Facts Section - Roles Extraction',
     'Extract roles as they existed in the scenario. Focus on professional actors and their classifications.',
     'Baseline role extraction for Facts section using established dual extraction pattern.',
     'system', true),

    ('facts', 1, 'states',
     'Facts Section - States Extraction',
     'Extract situational states that establish environmental conditions. Focus on conditions triggering ethical considerations.',
     'Baseline state extraction for Facts section capturing situational triggers.',
     'system', true),

    ('facts', 1, 'resources',
     'Facts Section - Resources Extraction',
     'Extract informational and physical resources available in the scenario. Focus on documents, guidelines, and tools.',
     'Baseline resource extraction for Facts section identifying available knowledge.',
     'system', true),

    -- Pass 2 - Normative Requirements (Facts section baseline)
    ('facts', 2, 'principles',
     'Facts Section - Principles Extraction',
     'Extract fundamental ethical principles implicit in the facts. Focus on values at stake.',
     'Baseline principle extraction for Facts section identifying foundational values.',
     'system', true),

    ('facts', 2, 'obligations',
     'Facts Section - Obligations Extraction',
     'Extract professional duties and requirements evident from the facts. Focus on concrete obligations.',
     'Baseline obligation extraction for Facts section identifying professional duties.',
     'system', true),

    ('facts', 2, 'constraints',
     'Facts Section - Constraints Extraction',
     'Extract inviolable boundaries and limitations evident in the scenario. Focus on hard constraints.',
     'Baseline constraint extraction for Facts section identifying boundaries.',
     'system', true),

    ('facts', 2, 'capabilities',
     'Facts Section - Capabilities Extraction',
     'Extract required competencies evident from professional context. Focus on needed skills.',
     'Baseline capability extraction for Facts section identifying required competencies.',
     'system', true),

    -- Pass 3 - Temporal Dynamics (Facts section baseline)
    ('facts', 3, 'actions',
     'Facts Section - Actions Extraction',
     'Extract volitional professional decisions and behaviors. Focus on deliberate choices.',
     'Baseline action extraction for Facts section capturing professional decisions.',
     'system', true),

    ('facts', 3, 'events',
     'Facts Section - Events Extraction',
     'Extract temporal occurrences and happenings. Focus on triggers and state changes.',
     'Baseline event extraction for Facts section identifying temporal dynamics.',
     'system', true);

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Migration completed: section_prompt_templates table created with baseline Facts prompts';
END $$;
