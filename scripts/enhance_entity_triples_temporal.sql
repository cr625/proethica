-- Migration script to enhance the entity_triples table with improved temporal representation
-- This script adds new fields and indexes for better temporal reasoning

-- Step 1: Add new fields for enhanced temporal context
ALTER TABLE entity_triples 
    ADD COLUMN IF NOT EXISTS temporal_confidence FLOAT DEFAULT 1.0,
    ADD COLUMN IF NOT EXISTS temporal_context JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS timeline_order INTEGER,
    ADD COLUMN IF NOT EXISTS timeline_group VARCHAR(255);

-- Step 2: Create indexes for optimized temporal queries
CREATE INDEX IF NOT EXISTS idx_entity_triples_temporal_start_scenario
    ON entity_triples (scenario_id, temporal_start);

CREATE INDEX IF NOT EXISTS idx_entity_triples_temporal_relations
    ON entity_triples (temporal_relation_type, temporal_relation_to);

CREATE INDEX IF NOT EXISTS idx_entity_triples_timeline_order
    ON entity_triples (scenario_id, timeline_order);

CREATE INDEX IF NOT EXISTS idx_entity_triples_timeline_group
    ON entity_triples (timeline_group);

-- Step 3: Create functions to support temporal operations

-- Function to calculate timeline_order values for existing triples
CREATE OR REPLACE FUNCTION recalculate_timeline_order(scenario_id_param INTEGER)
RETURNS VOID AS $$
DECLARE
    counter INTEGER := 1;
    triple_record RECORD;
BEGIN
    -- Update timeline_order in temporal order
    FOR triple_record IN 
        SELECT id 
        FROM entity_triples
        WHERE scenario_id = scenario_id_param 
        AND temporal_start IS NOT NULL
        ORDER BY temporal_start, id
    LOOP
        UPDATE entity_triples 
        SET timeline_order = counter 
        WHERE id = triple_record.id;
        
        counter := counter + 1;
    END LOOP;
    
    -- For triples without temporal_start, place them at the end
    FOR triple_record IN 
        SELECT id 
        FROM entity_triples
        WHERE scenario_id = scenario_id_param 
        AND temporal_start IS NULL
    LOOP
        UPDATE entity_triples 
        SET timeline_order = counter 
        WHERE id = triple_record.id;
        
        counter := counter + 1;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Function to infer temporal relationships based on timeline order and timestamps
CREATE OR REPLACE FUNCTION infer_temporal_relationships(scenario_id_param INTEGER)
RETURNS INTEGER AS $$
DECLARE
    counter INTEGER := 0;
    curr_triple RECORD;
    prev_triple RECORD;
    prev_id INTEGER := NULL;
BEGIN
    -- Clear any existing inferred relationships (ones that are automatically calculated)
    UPDATE entity_triples 
    SET temporal_relation_type = NULL, temporal_relation_to = NULL
    WHERE scenario_id = scenario_id_param
    AND triple_metadata->>'relationship_source' = 'inferred';
    
    -- Infer 'precedes'/'follows' relationships based on temporal order
    FOR curr_triple IN 
        SELECT id, temporal_start, temporal_end, entity_type, entity_id
        FROM entity_triples
        WHERE scenario_id = scenario_id_param 
        AND temporal_start IS NOT NULL
        ORDER BY temporal_start, id
    LOOP
        -- If we have a previous triple, create relationship
        IF prev_id IS NOT NULL THEN
            -- Current precedes next
            UPDATE entity_triples 
            SET temporal_relation_type = 'precedes', 
                temporal_relation_to = curr_triple.id,
                triple_metadata = jsonb_set(
                    COALESCE(triple_metadata, '{}'::jsonb),
                    '{relationship_source}',
                    '"inferred"'
                )
            WHERE id = prev_id;
            
            -- Next follows current
            UPDATE entity_triples 
            SET temporal_relation_type = 'follows', 
                temporal_relation_to = prev_id,
                triple_metadata = jsonb_set(
                    COALESCE(triple_metadata, '{}'::jsonb),
                    '{relationship_source}',
                    '"inferred"'
                )
            WHERE id = curr_triple.id;
            
            counter := counter + 2;
        END IF;
        
        prev_id := curr_triple.id;
    END LOOP;
    
    RETURN counter;
END;
$$ LANGUAGE plpgsql;

-- Step 4: Initialize the new fields for existing data

-- Initialize timeline_order for all scenarios
DO $$
DECLARE
    scenario_rec RECORD;
BEGIN
    FOR scenario_rec IN 
        SELECT DISTINCT scenario_id 
        FROM entity_triples 
        WHERE scenario_id IS NOT NULL
    LOOP
        PERFORM recalculate_timeline_order(scenario_rec.scenario_id);
    END LOOP;
END $$;

-- Step 5: Create trigger to maintain timeline_order on inserts/updates
CREATE OR REPLACE FUNCTION maintain_timeline_order()
RETURNS TRIGGER AS $$
BEGIN
    -- If timeline_order was not specified but we have a temporal_start
    IF (NEW.timeline_order IS NULL AND NEW.temporal_start IS NOT NULL) THEN
        -- Find the highest timeline_order for triples with earlier or equal temporal_start
        SELECT COALESCE(MAX(timeline_order), 0) + 1 INTO NEW.timeline_order
        FROM entity_triples
        WHERE scenario_id = NEW.scenario_id
        AND (temporal_start < NEW.temporal_start OR 
             (temporal_start = NEW.temporal_start AND id < NEW.id));
        
        -- Shift all later items
        UPDATE entity_triples
        SET timeline_order = timeline_order + 1
        WHERE scenario_id = NEW.scenario_id
        AND timeline_order >= NEW.timeline_order
        AND id != NEW.id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_maintain_timeline_order
BEFORE INSERT OR UPDATE ON entity_triples
FOR EACH ROW
EXECUTE FUNCTION maintain_timeline_order();

-- Step 6: Create a view for timeline visualization
CREATE OR REPLACE VIEW timeline_view AS
SELECT 
    et.id,
    et.scenario_id,
    et.entity_type,
    et.entity_id,
    et.subject,
    et.predicate,
    et.object_literal,
    et.object_uri,
    et.is_literal,
    et.temporal_start,
    et.temporal_end,
    et.temporal_region_type,
    et.temporal_relation_type,
    et.temporal_relation_to,
    et.temporal_granularity,
    et.timeline_order,
    et.timeline_group,
    et.temporal_confidence,
    et.temporal_context,
    -- Additional information based on entity type
    CASE 
        WHEN et.entity_type = 'event' THEN e.description
        WHEN et.entity_type = 'action' THEN a.name || ': ' || a.description
        ELSE NULL
    END as display_name,
    CASE 
        WHEN et.entity_type = 'action' AND a.is_decision THEN true
        ELSE false
    END as is_decision,
    CASE 
        WHEN et.entity_type = 'action' AND a.is_decision THEN a.options
        ELSE NULL
    END as decision_options,
    CASE 
        WHEN et.entity_type = 'action' AND a.is_decision THEN a.selected_option
        ELSE NULL
    END as decision_selected_option
FROM 
    entity_triples et
LEFT JOIN 
    events e ON et.entity_type = 'event' AND et.entity_id = e.id
LEFT JOIN 
    actions a ON et.entity_type = 'action' AND et.entity_id = a.id
ORDER BY 
    et.scenario_id, 
    COALESCE(et.timeline_order, 999999), 
    et.temporal_start;
