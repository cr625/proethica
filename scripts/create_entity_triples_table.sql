-- Entity Triples Migration Script
-- This script creates the entity_triples table for unified RDF triple storage
-- and migrates existing character triples to the new table

-- First, enable pgvector if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the entity_triples table
CREATE TABLE entity_triples (
    id SERIAL PRIMARY KEY,
    subject VARCHAR(255) NOT NULL,          -- Entity URI
    predicate VARCHAR(255) NOT NULL,        -- Property URI
    object_literal TEXT,                    -- Value as string when is_literal=True
    object_uri VARCHAR(255),                -- Value as URI when is_literal=False
    is_literal BOOLEAN NOT NULL,            -- Whether object is a literal or URI
    graph VARCHAR(255),                     -- Named graph (e.g., scenario ID)
    
    -- Vector embeddings for semantic similarity searches
    subject_embedding VECTOR(384),          -- Vector embedding of subject (adjust dimension if needed)
    predicate_embedding VECTOR(384),        -- Vector embedding of predicate
    object_embedding VECTOR(384),           -- Vector embedding of object
    
    -- Metadata and timestamps
    triple_metadata JSONB DEFAULT '{}',     -- Additional metadata
    created_at TIMESTAMP DEFAULT NOW(),     -- Creation timestamp
    updated_at TIMESTAMP DEFAULT NOW(),     -- Last update timestamp
    
    -- Polymorphic entity reference
    entity_type VARCHAR(50) NOT NULL,       -- 'character', 'action', 'event', 'resource'
    entity_id INTEGER NOT NULL,             -- ID in respective entity table
    scenario_id INTEGER REFERENCES scenarios(id) ON DELETE CASCADE,
    
    -- Foreign keys for backward compatibility (nullable)
    -- These are optional and only set when entity_type matches
    character_id INTEGER REFERENCES characters(id) ON DELETE CASCADE
);

-- Add comment for the table
COMMENT ON TABLE entity_triples IS 'Unified RDF triple storage for all entity types in ProEthica';

-- Create indexes for efficient querying
CREATE INDEX idx_entity_triples_entity ON entity_triples (entity_type, entity_id);
CREATE INDEX idx_entity_triples_subject ON entity_triples (subject);
CREATE INDEX idx_entity_triples_predicate ON entity_triples (predicate);
CREATE INDEX idx_entity_triples_graph ON entity_triples (graph);
CREATE INDEX idx_entity_triples_scenario ON entity_triples (scenario_id);

-- Add vector indexes for similarity search
CREATE INDEX idx_entity_triples_subject_embedding ON entity_triples USING ivfflat (subject_embedding vector_cosine_ops);
CREATE INDEX idx_entity_triples_object_embedding ON entity_triples USING ivfflat (object_embedding vector_cosine_ops);

-- Migrate existing character triples to the new table
INSERT INTO entity_triples (
    subject, predicate, object_literal, object_uri, is_literal,
    graph, subject_embedding, predicate_embedding, object_embedding,
    triple_metadata, created_at, updated_at, 
    entity_type, entity_id, scenario_id, character_id
)
SELECT
    subject, predicate, object_literal, object_uri, is_literal,
    graph, subject_embedding, predicate_embedding, object_embedding,
    triple_metadata, created_at, updated_at, 
    'character', character_id, scenario_id, character_id
FROM character_triples
WHERE character_id IS NOT NULL;

-- Create a function to maintain backward compatibility with character_triples
CREATE OR REPLACE FUNCTION sync_entity_triples_to_character_triples()
RETURNS TRIGGER AS $$
BEGIN
    -- If the new triple is for a character, insert/update it in character_triples
    IF NEW.entity_type = 'character' THEN
        -- Delete any existing triples for this character and predicate
        DELETE FROM character_triples 
        WHERE character_id = NEW.entity_id 
        AND predicate = NEW.predicate
        AND (
            (NEW.is_literal AND object_literal = NEW.object_literal) OR
            (NOT NEW.is_literal AND object_uri = NEW.object_uri)
        );
        
        -- Insert the new triple
        INSERT INTO character_triples (
            subject, predicate, object_literal, object_uri, is_literal,
            graph, subject_embedding, predicate_embedding, object_embedding,
            triple_metadata, created_at, updated_at,
            character_id, scenario_id
        ) VALUES (
            NEW.subject, NEW.predicate, NEW.object_literal, NEW.object_uri, NEW.is_literal,
            NEW.graph, NEW.subject_embedding, NEW.predicate_embedding, NEW.object_embedding,
            NEW.triple_metadata, NEW.created_at, NEW.updated_at,
            NEW.entity_id, NEW.scenario_id
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create a trigger to sync entity_triples to character_triples
CREATE TRIGGER sync_to_character_triples
AFTER INSERT OR UPDATE ON entity_triples
FOR EACH ROW
EXECUTE FUNCTION sync_entity_triples_to_character_triples();

-- Create a view for easy querying of the graph structure
CREATE OR REPLACE VIEW entity_graph AS
SELECT 
    t1.id AS source_id,
    t1.entity_type AS source_type,
    t1.entity_id AS source_entity_id,
    t1.subject AS source_uri,
    t1.predicate AS relationship,
    t2.id AS target_id,
    t2.entity_type AS target_type,
    t2.entity_id AS target_entity_id,
    CASE 
        WHEN t2.is_literal THEN t2.object_literal
        ELSE t2.object_uri
    END AS target_uri,
    t1.scenario_id
FROM entity_triples t1
JOIN entity_triples t2 ON t1.object_uri = t2.subject
WHERE t1.is_literal = FALSE;

-- Add comment for the view
COMMENT ON VIEW entity_graph IS 'View for easy querying of relationships between entities';

-- Create a utility function for path traversal
CREATE OR REPLACE FUNCTION get_entity_paths(
    start_uri TEXT, 
    end_uri TEXT, 
    max_depth INT DEFAULT 5
)
RETURNS TABLE (
    path TEXT[],
    path_predicates TEXT[],
    depth INT
) AS $$
WITH RECURSIVE graph_path(current_uri, path, path_predicates, depth) AS (
    -- Base case: start with the starting URI
    SELECT 
        subject AS current_uri, 
        ARRAY[subject] AS path,
        ARRAY[]::TEXT[] AS path_predicates,
        1 AS depth
    FROM entity_triples
    WHERE subject = start_uri
    
    UNION ALL
    
    -- Recursive case: follow relationships
    SELECT 
        t.object_uri AS current_uri, 
        gp.path || t.object_uri AS path, 
        gp.path_predicates || t.predicate AS path_predicates,
        gp.depth + 1 AS depth
    FROM graph_path gp
    JOIN entity_triples t ON gp.current_uri = t.subject
    WHERE 
        t.is_literal = FALSE AND 
        gp.depth < max_depth AND
        t.object_uri NOT IN (SELECT unnest(gp.path)) -- Prevent cycles
)
SELECT path, path_predicates, depth 
FROM graph_path 
WHERE current_uri = end_uri
ORDER BY depth;
$$ LANGUAGE SQL;

-- Add comment for the function
COMMENT ON FUNCTION get_entity_paths IS 'Find paths between two entities in the RDF graph';
