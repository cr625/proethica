-- Add role matching fields to characters table
-- These fields will store the original LLM-extracted role and the matched ontology role

BEGIN;

-- Add column to store the original LLM-extracted role text
ALTER TABLE characters 
ADD COLUMN IF NOT EXISTS original_llm_role VARCHAR(255);

-- Add column to store the matched ontology role ID
ALTER TABLE characters 
ADD COLUMN IF NOT EXISTS matched_ontology_role_id VARCHAR(500);

-- Add column to store the matching confidence score
ALTER TABLE characters 
ADD COLUMN IF NOT EXISTS matching_confidence FLOAT;

-- Add column to store the matching method used
ALTER TABLE characters 
ADD COLUMN IF NOT EXISTS matching_method VARCHAR(50) DEFAULT 'semantic_llm_validated';

-- Add column to store the LLM reasoning for the match
ALTER TABLE characters 
ADD COLUMN IF NOT EXISTS matching_reasoning TEXT;

-- Update existing characters to store their current role as original_llm_role
UPDATE characters 
SET original_llm_role = role 
WHERE original_llm_role IS NULL;

-- Verify the changes
SELECT 
    column_name, 
    data_type, 
    character_maximum_length,
    column_default
FROM information_schema.columns 
WHERE table_name = 'characters'
AND column_name IN (
    'original_llm_role', 
    'matched_ontology_role_id', 
    'matching_confidence',
    'matching_method',
    'matching_reasoning'
)
ORDER BY ordinal_position;

COMMIT;