-- Migration: Add section_type to extraction_prompts table
-- Date: 2025-10-04
-- Purpose: Support multi-section extraction (Facts, Discussion, Questions, Conclusions, etc.)
--
-- This enables tracking which NSPE case section each prompt was used for,
-- supporting the Multi-Section Extraction Architecture.

BEGIN;

-- Add section_type column with default value 'facts' for existing records
ALTER TABLE extraction_prompts
ADD COLUMN section_type VARCHAR(50) DEFAULT 'facts' NOT NULL;

-- Add check constraint for valid section types
ALTER TABLE extraction_prompts
ADD CONSTRAINT valid_section_type CHECK (
    section_type IN (
        'facts',
        'discussion',
        'questions',
        'conclusions',
        'dissenting_opinion',
        'references'
    )
);

-- Create index for faster section-specific queries
CREATE INDEX ix_extraction_prompts_section ON extraction_prompts(section_type, case_id, concept_type);

-- Update the compound index to include section_type
DROP INDEX IF EXISTS ix_active_prompts;
CREATE INDEX ix_active_prompts ON extraction_prompts(case_id, section_type, concept_type, is_active);

-- Add comment to document the column
COMMENT ON COLUMN extraction_prompts.section_type IS 'NSPE case section this prompt was used for (facts, discussion, questions, etc.)';

COMMIT;

-- Verification queries:
-- SELECT section_type, COUNT(*) FROM extraction_prompts GROUP BY section_type;
-- SELECT * FROM extraction_prompts WHERE section_type != 'facts' LIMIT 5;
