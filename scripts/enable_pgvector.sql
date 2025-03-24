-- SQL script to enable the pgvector extension in PostgreSQL
-- Run this script with: psql -d your_database_name -f scripts/enable_pgvector.sql

-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify the extension is installed
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Create an index on the document_chunks table if it exists
DO $$
BEGIN
    IF EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'document_chunks'
    ) THEN
        -- Check if the index already exists
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes 
            WHERE indexname = 'document_chunks_embedding_idx'
        ) THEN
            -- Create the index
            EXECUTE 'CREATE INDEX document_chunks_embedding_idx ON document_chunks USING ivfflat (embedding vector_cosine_ops)';
            RAISE NOTICE 'Created index on document_chunks.embedding';
        ELSE
            RAISE NOTICE 'Index on document_chunks.embedding already exists';
        END IF;
    ELSE
        RAISE NOTICE 'Table document_chunks does not exist yet';
    END IF;
END
$$;

-- Output a success message
\echo 'pgvector extension enabled successfully!'
\echo 'You can now use vector operations in your database.'
