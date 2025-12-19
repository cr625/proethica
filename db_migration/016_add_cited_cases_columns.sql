-- Migration 016: Add cited case tracking columns to case_precedent_features
-- Purpose: Enable tracking of cases cited within NSPE BER decisions
-- Related to: Precedent Discovery Enhancement Plan - Task 2

-- Add columns for cited case tracking
ALTER TABLE case_precedent_features
ADD COLUMN IF NOT EXISTS cited_case_numbers TEXT[],
ADD COLUMN IF NOT EXISTS cited_case_ids INTEGER[];

-- Add comments
COMMENT ON COLUMN case_precedent_features.cited_case_numbers IS 'Case numbers cited in this case (e.g., [Case 92-1, Case 88-4])';
COMMENT ON COLUMN case_precedent_features.cited_case_ids IS 'Resolved document IDs for cited cases (populated when cited cases exist in database)';

-- Verify
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'case_precedent_features'
AND column_name IN ('cited_case_numbers', 'cited_case_ids');
