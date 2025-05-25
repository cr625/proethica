-- Verify guidelines and entity_triples tables for concept extraction
-- This script checks that all required columns exist and reports any issues

-- Set the right schema
SET search_path TO public;

-- Check if the guidelines table exists
DO $$
DECLARE
    table_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'guidelines'
    ) INTO table_exists;
    
    IF NOT table_exists THEN
        RAISE NOTICE 'The guidelines table does not exist! Create it first.';
    ELSE
        RAISE NOTICE 'The guidelines table exists.';
    END IF;
END $$;

-- Check if all required columns exist in the guidelines table
DO $$
DECLARE
    missing_columns TEXT := '';
    column_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'guidelines'
    ) INTO column_exists;
    
    IF NOT column_exists THEN
        RAISE NOTICE 'No columns found in guidelines table!';
        RETURN;
    END IF;
    
    -- Check for each required column
    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'guidelines' 
        AND column_name = 'id'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'id, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'guidelines' 
        AND column_name = 'world_id'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'world_id, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'guidelines' 
        AND column_name = 'title'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'title, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'guidelines' 
        AND column_name = 'content'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'content, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'guidelines' 
        AND column_name = 'guideline_metadata'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'guideline_metadata, '; END IF;

    -- Report missing columns
    IF missing_columns <> '' THEN
        missing_columns := LEFT(missing_columns, LENGTH(missing_columns) - 2); -- Remove trailing comma
        RAISE NOTICE 'Missing columns in guidelines table: %', missing_columns;
    ELSE
        RAISE NOTICE 'The guidelines table has all required columns.';
    END IF;
END $$;

-- Check if the entity_triples table exists
DO $$
DECLARE
    table_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples'
    ) INTO table_exists;
    
    IF NOT table_exists THEN
        RAISE NOTICE 'The entity_triples table does not exist! Create it first.';
    ELSE
        RAISE NOTICE 'The entity_triples table exists.';
    END IF;
END $$;

-- Check if all required columns for guideline concepts exist in the entity_triples table
DO $$
DECLARE
    missing_columns TEXT := '';
    column_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples'
    ) INTO column_exists;
    
    IF NOT column_exists THEN
        RAISE NOTICE 'No columns found in entity_triples table!';
        RETURN;
    END IF;
    
    -- Check for each required column - especially ones needed for guideline concepts
    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples' 
        AND column_name = 'id'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'id, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples' 
        AND column_name = 'subject'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'subject, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples' 
        AND column_name = 'predicate'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'predicate, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples' 
        AND column_name = 'object_literal'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'object_literal, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples' 
        AND column_name = 'object_uri'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'object_uri, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples' 
        AND column_name = 'is_literal'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'is_literal, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples' 
        AND column_name = 'subject_label'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'subject_label, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples' 
        AND column_name = 'predicate_label'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'predicate_label, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples' 
        AND column_name = 'object_label'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'object_label, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples' 
        AND column_name = 'entity_type'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'entity_type, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples' 
        AND column_name = 'entity_id'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'entity_id, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples' 
        AND column_name = 'world_id'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'world_id, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples' 
        AND column_name = 'guideline_id'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'guideline_id, '; END IF;

    -- Check for enhanced temporal fields that might be needed
    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples' 
        AND column_name = 'temporal_confidence'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'temporal_confidence, '; END IF;

    SELECT NOT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'entity_triples' 
        AND column_name = 'temporal_context'
    ) INTO column_exists;
    IF column_exists THEN missing_columns := missing_columns || 'temporal_context, '; END IF;

    -- Report missing columns
    IF missing_columns <> '' THEN
        missing_columns := LEFT(missing_columns, LENGTH(missing_columns) - 2); -- Remove trailing comma
        RAISE NOTICE 'Missing columns in entity_triples table: %', missing_columns;
    ELSE
        RAISE NOTICE 'The entity_triples table has all required columns.';
    END IF;
END $$;

-- Count and show guideline concept triples
SELECT 
    g.id AS guideline_id,
    g.title AS guideline_title,
    COUNT(et.id) AS triple_count
FROM 
    guidelines g
LEFT JOIN 
    entity_triples et ON g.id = et.guideline_id 
    AND et.entity_type = 'guideline_concept'
GROUP BY 
    g.id, g.title
ORDER BY 
    g.id;

-- Show concept breakdown by type
SELECT 
    et.predicate_label, 
    et.object_label,
    COUNT(et.id) AS concept_count
FROM 
    entity_triples et
WHERE 
    et.entity_type = 'guideline_concept'
    AND et.predicate LIKE '%type%'
GROUP BY 
    et.predicate_label, et.object_label
ORDER BY 
    concept_count DESC;
