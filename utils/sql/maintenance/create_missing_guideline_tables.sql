-- Create missing guideline_term_candidates table
-- This table is referenced in the model but doesn't exist in the database

CREATE TABLE IF NOT EXISTS guideline_term_candidates (
    id SERIAL PRIMARY KEY,
    guideline_id INTEGER REFERENCES guidelines(id) ON DELETE CASCADE,
    term_label VARCHAR(255) NOT NULL,
    term_uri VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL,
    parent_class_uri VARCHAR(255),
    definition TEXT,
    confidence FLOAT,
    is_existing BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    reviewed_by INTEGER REFERENCES users(id),
    review_notes TEXT
);

-- Create index for better performance
CREATE INDEX IF NOT EXISTS idx_guideline_term_candidates_guideline_id 
ON guideline_term_candidates(guideline_id);

-- Verify table creation
SELECT 'Table created successfully' as status, COUNT(*) as row_count 
FROM guideline_term_candidates;