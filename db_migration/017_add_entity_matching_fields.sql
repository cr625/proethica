-- Migration 017: Add entity matching fields for OntServe class linking
-- Part of Entity-Ontology Linking implementation
-- Created: December 1, 2025

-- Add matching fields to temporary_rdf_storage for tracking
-- which OntServe class each extracted entity maps to

ALTER TABLE temporary_rdf_storage
ADD COLUMN IF NOT EXISTS matched_ontology_uri VARCHAR(500),
ADD COLUMN IF NOT EXISTS matched_ontology_label VARCHAR(255),
ADD COLUMN IF NOT EXISTS match_confidence FLOAT,
ADD COLUMN IF NOT EXISTS match_method VARCHAR(50),
ADD COLUMN IF NOT EXISTS match_reasoning TEXT;

-- Add comment to explain the match_method values
COMMENT ON COLUMN temporary_rdf_storage.match_method IS
'Method used to determine match: llm (LLM suggested), embedding (similarity match), exact_label (exact label match), user_override (manually set by user)';

-- Index for efficient queries on matched entities
CREATE INDEX IF NOT EXISTS idx_temp_rdf_matched_uri
ON temporary_rdf_storage(matched_ontology_uri)
WHERE matched_ontology_uri IS NOT NULL;

-- Index for finding unmatched entities that need review
CREATE INDEX IF NOT EXISTS idx_temp_rdf_unmatched
ON temporary_rdf_storage(case_id, extraction_type)
WHERE matched_ontology_uri IS NULL AND is_committed = FALSE;

-- Add entity_classes to case_precedent_features for Jaccard overlap calculation
ALTER TABLE case_precedent_features
ADD COLUMN IF NOT EXISTS entity_classes JSONB;

COMMENT ON COLUMN case_precedent_features.entity_classes IS
'JSON object mapping entity types to lists of OntServe class URIs for Jaccard overlap calculation. Example: {"roles": ["proeth-int:Engineer", "proeth-int:Client"], "states": [...], ...}';

-- Index for efficient JSONB queries on entity_classes
CREATE INDEX IF NOT EXISTS idx_precedent_entity_classes
ON case_precedent_features USING GIN (entity_classes);

-- Verify changes
DO $$
BEGIN
    RAISE NOTICE 'Migration 017 completed: Entity matching fields added';
    RAISE NOTICE 'New columns on temporary_rdf_storage: matched_ontology_uri, matched_ontology_label, match_confidence, match_method, match_reasoning';
    RAISE NOTICE 'New column on case_precedent_features: entity_classes';
END $$;
