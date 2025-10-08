-- Migration: Add IAO document reference fields to TemporaryRDFStorage
-- Date: 2025-10-07
-- Purpose: Support linking Resources to IAO documents for References section
-- Related: Phase 1 of IAO Resources Implementation Plan

-- Add IAO document reference fields (all nullable for backwards compatibility)
ALTER TABLE temporary_rdf_storage
ADD COLUMN IF NOT EXISTS iao_document_uri VARCHAR(500),
ADD COLUMN IF NOT EXISTS iao_document_label VARCHAR(500),
ADD COLUMN IF NOT EXISTS iao_document_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS cited_by_role VARCHAR(200),
ADD COLUMN IF NOT EXISTS available_to_role VARCHAR(200);

-- Add comments explaining the new columns
COMMENT ON COLUMN temporary_rdf_storage.iao_document_uri IS
'URI of the IAO document or document part (iao:0000300 or iao:0000310) that this resource refers to';

COMMENT ON COLUMN temporary_rdf_storage.iao_document_label IS
'Human-readable label of the IAO document (e.g., "NSPE Code Section II.4.a")';

COMMENT ON COLUMN temporary_rdf_storage.iao_document_type IS
'Type of IAO document: "document" (iao:0000300) or "document_part" (iao:0000310)';

COMMENT ON COLUMN temporary_rdf_storage.cited_by_role IS
'Which role/agent cited this resource (e.g., "Board of Ethical Review"). Used for References section.';

COMMENT ON COLUMN temporary_rdf_storage.available_to_role IS
'Which role/agent has access to this resource in the case scenario. Used for case context resources.';

-- Create index for querying by cited resources
CREATE INDEX IF NOT EXISTS idx_temp_rdf_cited_by
ON temporary_rdf_storage(cited_by_role)
WHERE cited_by_role IS NOT NULL;

-- Create index for querying by IAO documents
CREATE INDEX IF NOT EXISTS idx_temp_rdf_iao_document
ON temporary_rdf_storage(iao_document_uri)
WHERE iao_document_uri IS NOT NULL;

-- Verification query (commented out - uncomment to test)
-- SELECT COUNT(*) as existing_rows FROM temporary_rdf_storage;
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'temporary_rdf_storage'
-- AND column_name LIKE 'iao_%' OR column_name LIKE '%_role';
