#!/usr/bin/env python
"""
Implementation script for Phase 1 of RDF Triple-Based Data Structure
This script properly implements Phase 1 with better error handling
"""

import os
import sys
import subprocess
import argparse
from datetime import datetime
from sqlalchemy import text, Column, DateTime

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.triple import Triple
from app.models.entity_triple import EntityTriple

def create_backup():
    """Create a database backup."""
    print("\n=== Creating Database Backup ===")
    try:
        # Run the backup script
        result = subprocess.run(['bash', 'backups/backup_database.sh'], 
                               capture_output=True, text=True, check=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Backup failed: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False

def create_entity_triples_table():
    """Create the entity_triples table directly using SQL commands."""
    print("\n=== Creating Entity Triples Table ===")
    
    # Check if table already exists
    query = """
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'entity_triples'
    );
    """
    result = db.session.execute(text(query)).fetchone()
    if result[0]:
        print("entity_triples table already exists. Skipping creation.")
        return True
    
    # Create the table and related objects step by step
    steps = [
        # 1. Create extension
        "CREATE EXTENSION IF NOT EXISTS vector;",
        
        # 2. Create the table
        """
        CREATE TABLE entity_triples (
            id SERIAL PRIMARY KEY,
            subject VARCHAR(255) NOT NULL,
            predicate VARCHAR(255) NOT NULL,
            object_literal TEXT,
            object_uri VARCHAR(255),
            is_literal BOOLEAN NOT NULL,
            graph VARCHAR(255),
            subject_embedding VECTOR(384),
            predicate_embedding VECTOR(384),
            object_embedding VECTOR(384),
            triple_metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            entity_type VARCHAR(50) NOT NULL,
            entity_id INTEGER NOT NULL,
            scenario_id INTEGER REFERENCES scenarios(id) ON DELETE CASCADE,
            character_id INTEGER REFERENCES characters(id) ON DELETE CASCADE
        );
        """,
        
        # 3. Add table comment
        "COMMENT ON TABLE entity_triples IS 'Unified RDF triple storage for all entity types in ProEthica';",
        
        # 4. Create indexes
        "CREATE INDEX idx_entity_triples_entity ON entity_triples (entity_type, entity_id);",
        "CREATE INDEX idx_entity_triples_subject ON entity_triples (subject);",
        "CREATE INDEX idx_entity_triples_predicate ON entity_triples (predicate);",
        "CREATE INDEX idx_entity_triples_graph ON entity_triples (graph);",
        "CREATE INDEX idx_entity_triples_scenario ON entity_triples (scenario_id);",
        
        # 5. Create vector indexes
        "CREATE INDEX idx_entity_triples_subject_embedding ON entity_triples USING ivfflat (subject_embedding vector_cosine_ops);",
        "CREATE INDEX idx_entity_triples_object_embedding ON entity_triples USING ivfflat (object_embedding vector_cosine_ops);",
        
        # 6. Migrate existing data
        """
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
        """,
        
        # 7. Create sync function
        """
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
        """,
        
        # 8. Create trigger
        """
        CREATE TRIGGER sync_to_character_triples
        AFTER INSERT OR UPDATE ON entity_triples
        FOR EACH ROW
        EXECUTE FUNCTION sync_entity_triples_to_character_triples();
        """,
        
        # 9. Create view
        """
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
        """,
        
        # 10. Add view comment
        "COMMENT ON VIEW entity_graph IS 'View for easy querying of relationships between entities';",
        
        # 11. Create path function
        """
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
        """,
        
        # 12. Add function comment
        "COMMENT ON FUNCTION get_entity_paths IS 'Find paths between two entities in the RDF graph';"
    ]
    
    # Execute each step with proper error handling
    for i, step in enumerate(steps):
        try:
            print(f"Executing step {i+1}/{len(steps)}...")
            db.session.execute(text(step))
            db.session.commit()
            print(f"Step {i+1} completed successfully")
        except Exception as e:
            db.session.rollback()
            print(f"Error in step {i+1}: {e}")
            if i < 2:  # Critical steps (extension and table creation)
                print("Critical error. Aborting.")
                return False
            print("Continuing with next step...")
    
    print("Entity triples table creation completed")
    return True

def verify_entity_triples_table():
    """Verify that the entity_triples table was created correctly."""
    print("\n=== Verifying Entity Triples Table ===")
    
    # Check if table exists
    query = """
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'entity_triples'
    );
    """
    result = db.session.execute(text(query)).fetchone()
    if not result[0]:
        print("entity_triples table does not exist!")
        return False
    
    print("entity_triples table exists")
    
    # Check if character triples were migrated
    char_triples_count = db.session.query(Triple).count()
    entity_triples_count = db.session.query(EntityTriple).filter_by(entity_type='character').count()
    
    print(f"Character triples count: {char_triples_count}")
    print(f"Entity triples for characters: {entity_triples_count}")
    
    if entity_triples_count >= char_triples_count:
        print("All character triples appear to be migrated")
        return True
    else:
        print(f"Migration incomplete: {entity_triples_count}/{char_triples_count} triples migrated")
        return False

def add_temporal_fields():
    """Add temporal fields to the entity_triples table."""
    print("\n=== Adding Temporal Fields to Entity Triples ===")
    
    # Check if the fields already exist
    check_query = """
    SELECT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_name = 'entity_triples' 
        AND column_name = 'valid_from'
    );
    """
    result = db.session.execute(text(check_query)).fetchone()
    
    if result[0]:
        print("Temporal fields already exist")
        return True
    
    # Add the fields
    alter_query = """
    ALTER TABLE entity_triples 
    ADD COLUMN valid_from TIMESTAMP DEFAULT NOW(),
    ADD COLUMN valid_to TIMESTAMP;
    
    CREATE INDEX idx_entity_triples_temporal ON entity_triples (entity_id, entity_type, predicate, valid_from, valid_to);
    """
    
    try:
        db.session.execute(text(alter_query))
        db.session.commit()
        print("Successfully added temporal fields to entity_triples table")
        
        # Extend the model
        EntityTriple.valid_from = Column(DateTime, default=datetime.utcnow)
        EntityTriple.valid_to = Column(DateTime, nullable=True)
        print("Successfully extended EntityTriple model")
        
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Error adding temporal fields: {e}")
        return False

def main():
    """Run the implementation of Phase 1."""
    parser = argparse.ArgumentParser(description='Implement Phase 1 of RDF Triple-Based Data Structure')
    parser.add_argument('--with-backup', action='store_true', help='Create a database backup before making changes')
    parser.add_argument('--force', action='store_true', help='Continue even if errors occur')
    args = parser.parse_args()
    
    app = create_app()
    
    with app.app_context():
        print("=== ProEthica RDF Triple-Based Data Structure - Phase 1 Implementation ===")
        
        failures = 0
        steps_executed = 0
        
        # Step 1: Create backup if requested
        if args.with_backup:
            backup_success = create_backup()
            steps_executed += 1
            if not backup_success:
                failures += 1
                if not args.force:
                    print("Backup failed and --force not specified. Aborting.")
                    return
                
        # Step 2: Create entity_triples table
        table_success = create_entity_triples_table()
        steps_executed += 1
        if not table_success:
            failures += 1
            print("Entity triples table creation failed. This is a required step. Aborting.")
            return
        
        # Step 3: Verify the table structure
        verify_success = verify_entity_triples_table()
        steps_executed += 1
        if not verify_success:
            failures += 1
            if not args.force:
                print("Table verification failed and --force not specified. Aborting.")
                return
        
        # Step 4: Add temporal fields
        temporal_success = add_temporal_fields()
        steps_executed += 1
        if not temporal_success:
            failures += 1
            if not args.force:
                print("Adding temporal fields failed and --force not specified. Aborting.")
                return
        
        # Summary
        print("\n=== Phase 1 Implementation Summary ===")
        print(f"Total steps executed: {steps_executed}")
        print(f"Successful steps: {steps_executed - failures}")
        print(f"Failed steps: {failures}")
        
        if failures == 0:
            print("\n✓ Phase 1 Implementation Complete")
            print("Phase 1 of the RDF Triple-Based Data Structure has been implemented successfully.")
        else:
            print("\n⚠ Phase 1 Implementation Completed with Errors")
            print(f"{failures} out of {steps_executed} steps had errors. Check the output above for details.")
        
        print("\nYou can now use the following features:")
        print("  - Unified triple storage for all entity types")
        print("  - Temporal triple support for time-based queries")
        print("  - SPARQL-like query capabilities")
        print("  - Semantic similarity search integration")
        print("\nSee docs/rdf_implementation_phase1.md for detailed documentation.")

if __name__ == "__main__":
    main()
