-- Fix document_chunks table columns and extensions
DO $$
BEGIN
    -- Ensure pgvector extension is installed
    CREATE EXTENSION IF NOT EXISTS vector;
    RAISE NOTICE 'Ensured pgvector extension is installed';

    -- Check if the content column doesn't exist
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'document_chunks' 
        AND column_name = 'content'
    ) THEN
        -- Add the content column
        ALTER TABLE document_chunks ADD COLUMN content TEXT;
        
        -- Update existing rows with a default value if there are any
        -- This ensures nullable=False constraint can be applied after
        UPDATE document_chunks SET content = '';
        
        -- Now make it not nullable to match the model definition
        ALTER TABLE document_chunks ALTER COLUMN content SET NOT NULL;
        
        RAISE NOTICE 'Added content column to document_chunks table';
    ELSE
        RAISE NOTICE 'Column content already exists in document_chunks table';
    END IF;

    -- Check if the updated_at column doesn't exist
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'document_chunks' 
        AND column_name = 'updated_at'
    ) THEN
        -- Add the updated_at column with default current timestamp
        ALTER TABLE document_chunks ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        
        RAISE NOTICE 'Added updated_at column to document_chunks table';
    ELSE
        RAISE NOTICE 'Column updated_at already exists in document_chunks table';
    END IF;
    
    -- Fix the embedding column to ensure it exists as FLOAT[]
    -- We'll drop and recreate it rather than trying to cast the vector type
    BEGIN
        -- First check if the column exists
        IF EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'document_chunks' 
            AND column_name = 'embedding'
        ) THEN
            -- Drop the existing embedding column 
            ALTER TABLE document_chunks DROP COLUMN embedding;
            RAISE NOTICE 'Dropped existing embedding column';
        END IF;
        
        -- Add new embedding column with correct type
        ALTER TABLE document_chunks ADD COLUMN embedding FLOAT[];
        RAISE NOTICE 'Added embedding column with FLOAT[] type';
        
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Error modifying embedding column: %', SQLERRM;
    END;
END $$;
