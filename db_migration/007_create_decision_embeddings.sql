-- Migration 007: Create decision_embeddings table for precedent discovery
-- Purpose: Store decision-level embeddings for fine-grained case similarity search
-- Uses OpenAI text-embedding-3-small (1536 dimensions) for semantic matching

-- Create decision_embeddings table
CREATE TABLE IF NOT EXISTS decision_embeddings (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    decision_id VARCHAR(255) NOT NULL,
    decision_question TEXT NOT NULL,

    -- Decision context for embedding
    decision_context JSONB NOT NULL,  -- ethical tensions, stakes, competing values, etc.

    -- OpenAI embedding (1536 dimensions for text-embedding-3-small)
    embedding vector(1536) NOT NULL,

    -- Metadata
    embedding_model VARCHAR(100) DEFAULT 'text-embedding-3-small',
    embedding_provider VARCHAR(50) DEFAULT 'openai',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure unique decision per case
    UNIQUE(case_id, decision_id)
);

-- Create indexes for efficient similarity search
CREATE INDEX IF NOT EXISTS idx_decision_embeddings_case_id
    ON decision_embeddings(case_id);

CREATE INDEX IF NOT EXISTS idx_decision_embeddings_embedding_cosine
    ON decision_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Create precedent_discoveries table to store similarity results
CREATE TABLE IF NOT EXISTS precedent_discoveries (
    id SERIAL PRIMARY KEY,

    -- Source decision
    source_case_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    source_decision_id VARCHAR(255) NOT NULL,

    -- Target precedent decision
    target_case_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    target_decision_id VARCHAR(255) NOT NULL,

    -- Similarity metrics
    similarity_score FLOAT NOT NULL,  -- Cosine similarity 0-1

    -- Precedent classification (by Claude)
    precedent_type VARCHAR(50) NOT NULL,  -- 'supporting', 'distinguishable', 'analogous', 'contra'

    -- Claude's analysis
    llm_analysis JSONB,  -- {reasoning, distinguishing_factors, key_similarities, narrative}

    -- Metadata
    classified_by VARCHAR(50) DEFAULT 'claude',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure unique precedent pairs
    UNIQUE(source_case_id, source_decision_id, target_case_id, target_decision_id)
);

-- Indexes for precedent lookups
CREATE INDEX IF NOT EXISTS idx_precedent_discoveries_source
    ON precedent_discoveries(source_case_id, source_decision_id);

CREATE INDEX IF NOT EXISTS idx_precedent_discoveries_target
    ON precedent_discoveries(target_case_id, target_decision_id);

CREATE INDEX IF NOT EXISTS idx_precedent_discoveries_similarity
    ON precedent_discoveries(similarity_score DESC);

CREATE INDEX IF NOT EXISTS idx_precedent_discoveries_type
    ON precedent_discoveries(precedent_type);

-- Comments
COMMENT ON TABLE decision_embeddings IS
    'Stores decision-level embeddings for fine-grained precedent discovery. Uses OpenAI text-embedding-3-small (1536-dim) for better semantic understanding than local embeddings.';

COMMENT ON TABLE precedent_discoveries IS
    'Stores precedent relationships between decisions across cases, classified by Claude into supporting/distinguishable/analogous/contra categories.';

COMMENT ON COLUMN decision_embeddings.decision_context IS
    'JSONB containing: ethical_tension, stakes, competing_values, decision_maker, situation_context, principles, obligations';

COMMENT ON COLUMN precedent_discoveries.precedent_type IS
    'Classification: supporting (same decision/outcome), distinguishable (similar facts/different decision), analogous (different facts/same principle), contra (opposite outcome)';

COMMENT ON COLUMN precedent_discoveries.llm_analysis IS
    'Claude analysis: {reasoning: why similar/different, distinguishing_factors: [], key_similarities: [], narrative: teaching explanation}';
