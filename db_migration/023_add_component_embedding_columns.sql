-- Migration 023: Add per-component embedding columns to case_precedent_features
-- Date: 2026-02-13
-- Purpose: Store individual D-tuple component embeddings (384-dim each) for
--          per-component similarity computation: Σ wk * cos(ei,k, ej,k)
--          Previously only the aggregated combined_embedding was stored.

ALTER TABLE case_precedent_features
ADD COLUMN IF NOT EXISTS embedding_R vector(384),
ADD COLUMN IF NOT EXISTS embedding_P vector(384),
ADD COLUMN IF NOT EXISTS embedding_O vector(384),
ADD COLUMN IF NOT EXISTS embedding_S vector(384),
ADD COLUMN IF NOT EXISTS embedding_Rs vector(384),
ADD COLUMN IF NOT EXISTS embedding_A vector(384),
ADD COLUMN IF NOT EXISTS embedding_E vector(384),
ADD COLUMN IF NOT EXISTS embedding_Ca vector(384),
ADD COLUMN IF NOT EXISTS embedding_Cs vector(384);

-- Column comments
COMMENT ON COLUMN case_precedent_features.embedding_R IS 'Roles component embedding (384-dim)';
COMMENT ON COLUMN case_precedent_features.embedding_P IS 'Principles component embedding (384-dim)';
COMMENT ON COLUMN case_precedent_features.embedding_O IS 'Obligations component embedding (384-dim)';
COMMENT ON COLUMN case_precedent_features.embedding_S IS 'States component embedding (384-dim)';
COMMENT ON COLUMN case_precedent_features.embedding_Rs IS 'Resources component embedding (384-dim)';
COMMENT ON COLUMN case_precedent_features.embedding_A IS 'Actions component embedding (384-dim)';
COMMENT ON COLUMN case_precedent_features.embedding_E IS 'Events component embedding (384-dim)';
COMMENT ON COLUMN case_precedent_features.embedding_Ca IS 'Capabilities component embedding (384-dim)';
COMMENT ON COLUMN case_precedent_features.embedding_Cs IS 'Constraints component embedding (384-dim)';

-- Verify columns added
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'case_precedent_features'
AND column_name LIKE 'embedding_%'
ORDER BY column_name;
