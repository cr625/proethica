-- Drop the column if it exists with the wrong type
DO $$
BEGIN
    BEGIN
        -- Check if column exists with wrong type
        IF EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'guidelines' 
            AND column_name = 'embedding' 
            AND data_type <> 'ARRAY'
        ) THEN
            ALTER TABLE guidelines DROP COLUMN embedding;
            RAISE NOTICE 'Dropped existing embedding column with incorrect type';
        END IF;
    EXCEPTION
        WHEN others THEN
            RAISE NOTICE 'Error checking/dropping column: %', SQLERRM;
    END;

    BEGIN
        -- Add column with correct type (if it doesn't exist)
        IF NOT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'guidelines' 
            AND column_name = 'embedding' 
            AND data_type = 'ARRAY'
        ) THEN
            ALTER TABLE guidelines ADD COLUMN embedding FLOAT[];
            RAISE NOTICE 'Added embedding column with FLOAT[] type';
        ELSE
            RAISE NOTICE 'Column embedding already exists with correct type';
        END IF;
    EXCEPTION
        WHEN others THEN
            RAISE NOTICE 'Error adding column: %', SQLERRM;
    END;
END $$;
