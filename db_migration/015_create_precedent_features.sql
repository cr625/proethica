-- Migration: 015_create_precedent_features.sql
-- Purpose: Create tables for precedent discovery feature storage
-- Created: 2025-11-28
--
-- References:
-- - CBR-RAG (Wiratunga et al., 2024): https://aclanthology.org/2024.lrec-main.939/
-- - NS-LCR (Sun et al., 2024): https://aclanthology.org/2024.lrec-main.939/

-- Enable pgvector if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Case precedent features table
-- Stores pre-computed features for efficient precedent matching
CREATE TABLE IF NOT EXISTS case_precedent_features (
    id SERIAL PRIMARY KEY,
    case_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,

    -- Outcome classification
    -- 'ethical', 'unethical', 'mixed', 'unclear'
    outcome_type VARCHAR(50),
    outcome_confidence FLOAT,
    outcome_reasoning TEXT,

    -- NSPE Code provision references extracted from references section
    -- Format: ['I.1', 'II.1.a', 'III.2.b']
    provisions_cited TEXT[],
    provision_count INTEGER,

    -- Subject tags from NSPE website extraction
    subject_tags TEXT[],

    -- Principle tensions from Step 4 analysis
    -- Format: [{"principle1": "...", "principle2": "...", "tension_type": "..."}]
    principle_tensions JSONB,

    -- Obligation conflicts from Step 4 analysis
    -- Format: [{"obligation1": "...", "obligation2": "...", "conflict_type": "..."}]
    obligation_conflicts JSONB,

    -- Transformation classification from Step 4
    transformation_type VARCHAR(50),  -- 'transfer', 'stalemate', 'oscillation', 'phase_lag'
    transformation_pattern TEXT,

    -- Hierarchical embeddings for multi-level similarity
    -- Section-level embeddings (384-dim, same as document_sections)
    facts_embedding vector(384),
    discussion_embedding vector(384),
    conclusion_embedding vector(384),

    -- Combined embedding for overall case similarity
    combined_embedding vector(384),

    -- Metadata
    features_version INTEGER DEFAULT 1,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    extraction_method VARCHAR(50),  -- 'automatic', 'manual', 'llm_enhanced'
    llm_model_used VARCHAR(100),
    extraction_metadata JSONB,

    UNIQUE(case_id)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_precedent_features_outcome
    ON case_precedent_features(outcome_type);

CREATE INDEX IF NOT EXISTS idx_precedent_features_transformation
    ON case_precedent_features(transformation_type);

CREATE INDEX IF NOT EXISTS idx_precedent_features_version
    ON case_precedent_features(features_version);

-- Vector indexes for similarity search (IVFFlat for moderate dataset size)
-- Using 10 lists since we have ~20-30 cases
CREATE INDEX IF NOT EXISTS idx_precedent_features_facts_embedding
    ON case_precedent_features
    USING ivfflat (facts_embedding vector_cosine_ops) WITH (lists = 10);

CREATE INDEX IF NOT EXISTS idx_precedent_features_discussion_embedding
    ON case_precedent_features
    USING ivfflat (discussion_embedding vector_cosine_ops) WITH (lists = 10);

CREATE INDEX IF NOT EXISTS idx_precedent_features_combined_embedding
    ON case_precedent_features
    USING ivfflat (combined_embedding vector_cosine_ops) WITH (lists = 10);

-- GIN index for array searching (provisions and tags)
CREATE INDEX IF NOT EXISTS idx_precedent_features_provisions
    ON case_precedent_features USING GIN (provisions_cited);

CREATE INDEX IF NOT EXISTS idx_precedent_features_tags
    ON case_precedent_features USING GIN (subject_tags);

-- Precedent similarity cache table
-- Stores pre-computed pairwise similarities for faster retrieval
CREATE TABLE IF NOT EXISTS precedent_similarity_cache (
    id SERIAL PRIMARY KEY,
    source_case_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    target_case_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,

    -- Component similarity scores
    facts_similarity FLOAT,
    discussion_similarity FLOAT,
    conclusion_similarity FLOAT,
    provision_overlap FLOAT,
    outcome_alignment FLOAT,
    tag_overlap FLOAT,
    principle_overlap FLOAT,

    -- Weighted overall score
    overall_similarity FLOAT,

    -- Weights used for this calculation
    weights_used JSONB,

    -- Metadata
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    computation_method VARCHAR(50),  -- 'static_weights', 'llm_dynamic'

    UNIQUE(source_case_id, target_case_id)
);

CREATE INDEX IF NOT EXISTS idx_similarity_cache_source
    ON precedent_similarity_cache(source_case_id);

CREATE INDEX IF NOT EXISTS idx_similarity_cache_overall
    ON precedent_similarity_cache(overall_similarity DESC);

-- Add columns to precedent_discoveries for enhanced analysis
-- (table already exists from earlier migration)
DO $$
BEGIN
    -- Add component scores if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'precedent_discoveries'
        AND column_name = 'component_scores'
    ) THEN
        ALTER TABLE precedent_discoveries
        ADD COLUMN component_scores JSONB;
    END IF;

    -- Add matching provisions if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'precedent_discoveries'
        AND column_name = 'matching_provisions'
    ) THEN
        ALTER TABLE precedent_discoveries
        ADD COLUMN matching_provisions TEXT[];
    END IF;

    -- Add weights used if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'precedent_discoveries'
        AND column_name = 'weights_used'
    ) THEN
        ALTER TABLE precedent_discoveries
        ADD COLUMN weights_used JSONB;
    END IF;

    -- Add relevance explanation if not exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'precedent_discoveries'
        AND column_name = 'relevance_explanation'
    ) THEN
        ALTER TABLE precedent_discoveries
        ADD COLUMN relevance_explanation TEXT;
    END IF;
END $$;

-- Create function for provision overlap calculation
CREATE OR REPLACE FUNCTION calculate_provision_overlap(
    provisions_a TEXT[],
    provisions_b TEXT[]
) RETURNS FLOAT AS $$
DECLARE
    intersection_size INTEGER;
    union_size INTEGER;
BEGIN
    IF provisions_a IS NULL OR provisions_b IS NULL THEN
        RETURN 0.0;
    END IF;

    IF array_length(provisions_a, 1) IS NULL OR array_length(provisions_b, 1) IS NULL THEN
        RETURN 0.0;
    END IF;

    -- Calculate Jaccard similarity
    SELECT COUNT(*) INTO intersection_size
    FROM unnest(provisions_a) a
    WHERE a = ANY(provisions_b);

    union_size := array_length(provisions_a, 1) + array_length(provisions_b, 1) - intersection_size;

    IF union_size = 0 THEN
        RETURN 0.0;
    END IF;

    RETURN intersection_size::FLOAT / union_size::FLOAT;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Create function for outcome alignment score
CREATE OR REPLACE FUNCTION calculate_outcome_alignment(
    outcome_a VARCHAR,
    outcome_b VARCHAR
) RETURNS FLOAT AS $$
BEGIN
    IF outcome_a IS NULL OR outcome_b IS NULL THEN
        RETURN 0.5;  -- Neutral when unknown
    END IF;

    IF outcome_a = outcome_b THEN
        RETURN 1.0;  -- Same outcome
    END IF;

    -- Opposite outcomes
    IF (outcome_a = 'ethical' AND outcome_b = 'unethical') OR
       (outcome_a = 'unethical' AND outcome_b = 'ethical') THEN
        RETURN 0.0;
    END IF;

    -- Mixed or partial match
    RETURN 0.5;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Comment on tables for documentation
COMMENT ON TABLE case_precedent_features IS
'Pre-computed features for precedent discovery. References: CBR-RAG (2024), NS-LCR (2024)';

COMMENT ON TABLE precedent_similarity_cache IS
'Cached pairwise similarity scores for efficient precedent retrieval';

COMMENT ON COLUMN case_precedent_features.provisions_cited IS
'NSPE Code of Ethics section references (e.g., I.1, II.1.a, III.2.b)';

COMMENT ON COLUMN case_precedent_features.transformation_type IS
'From Step 4 analysis: transfer, stalemate, oscillation, or phase_lag';
