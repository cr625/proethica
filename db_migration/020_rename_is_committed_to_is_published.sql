-- Migration 020: Rename is_committed to is_published
-- Part of Draft/Publish workflow redesign
-- Date: 2025-12-10

-- Rename the column
ALTER TABLE temporary_rdf_storage
RENAME COLUMN is_committed TO is_published;

-- Note: There is no committed_at column in the current schema
-- The model has it but it was never added via migration
-- We'll add published_at as a new column if needed

-- Add index for common query pattern
CREATE INDEX IF NOT EXISTS idx_temp_rdf_case_published
ON temporary_rdf_storage(case_id, is_published);

-- Update any views or constraints if they exist (none currently)

-- Verification query (run manually to confirm):
-- SELECT column_name FROM information_schema.columns
-- WHERE table_name = 'temporary_rdf_storage' AND column_name IN ('is_committed', 'is_published');
