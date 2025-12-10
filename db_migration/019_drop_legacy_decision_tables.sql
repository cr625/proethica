-- Migration 019: Drop legacy decision focus tables
-- Created: 2025-12-09
-- Purpose: Remove legacy tables in favor of RDF storage pattern
--
-- Decision points are now stored in temporary_rdf_storage table with:
--   - extraction_type = 'decision_point' or 'decision_option'
--   - entity_type = 'DecisionPoint' or 'DecisionOption'
--   - Proper RDF JSON-LD in rdf_json_ld column
--   - Provenance in extraction_prompts table
--
-- This aligns with the established pattern used for all other entity types.

-- Drop the legacy tables (if they still exist)
DROP TABLE IF EXISTS decision_evaluation_summaries CASCADE;
DROP TABLE IF EXISTS decision_arguments CASCADE;
DROP TABLE IF EXISTS case_decision_focuses CASCADE;

-- Note: The ArgumentGenerator service (Step 4 Part F) will use the same
-- RDF storage pattern when implemented.
