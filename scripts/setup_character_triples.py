#!/usr/bin/env python
"""
Script to create the character_triples table with pgvector support.
"""

import os
import sys
from sqlalchemy import text

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.triple import Triple

def setup_character_triples_table():
    """Set up the character_triples table with pgvector support."""
    app = create_app()
    
    with app.app_context():
        # Check if pgvector extension is enabled
        result = db.session.execute(text("SELECT * FROM pg_extension WHERE extname = 'vector'"))
        if result.rowcount == 0:
            print("pgvector extension is not enabled. Enabling now...")
            try:
                db.session.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
                db.session.commit()
                print("pgvector extension enabled successfully")
            except Exception as e:
                print(f"Error: Could not enable pgvector extension: {str(e)}")
                print("Aborting setup...")
                return
        else:
            print("pgvector extension is already enabled")
        
        # Check if the table exists
        result = db.session.execute(text("SELECT to_regclass('character_triples')"))
        table_exists = result.scalar() is not None
        
        if table_exists:
            print("The character_triples table already exists")
            user_input = input("Do you want to drop and recreate it? (y/n): ")
            if user_input.lower() != 'y':
                print("Skipping table creation")
                return
            
            # Drop the table
            try:
                db.session.execute(text('DROP TABLE IF EXISTS character_triples CASCADE'))
                db.session.commit()
                print("Dropped character_triples table")
            except Exception as e:
                print(f"Error dropping character_triples table: {str(e)}")
                return
        
        # Create the table using SQLAlchemy's create_all
        try:
            Triple.__table__.create(db.engine)
            print("Created character_triples table")
        except Exception as e:
            print(f"Error creating character_triples table: {str(e)}")
            return
        
        # Alter the table to use vector type for embeddings
        try:
            # Convert ARRAY columns to vector type
            db.session.execute(text('ALTER TABLE character_triples ALTER COLUMN subject_embedding TYPE vector USING subject_embedding::vector'))
            db.session.execute(text('ALTER TABLE character_triples ALTER COLUMN predicate_embedding TYPE vector USING predicate_embedding::vector'))
            db.session.execute(text('ALTER TABLE character_triples ALTER COLUMN object_embedding TYPE vector USING object_embedding::vector'))
            db.session.commit()
            print("Altered embedding columns to use vector type")
        except Exception as e:
            print(f"Warning: Could not alter embedding columns: {str(e)}")
            print("Continuing without vector columns...")
        
        # Create vector similarity indexes
        try:
            db.session.execute(text('CREATE INDEX IF NOT EXISTS character_triples_subject_embedding_idx ON character_triples USING ivfflat (subject_embedding vector_cosine_ops)'))
            db.session.execute(text('CREATE INDEX IF NOT EXISTS character_triples_predicate_embedding_idx ON character_triples USING ivfflat (predicate_embedding vector_cosine_ops)'))
            db.session.execute(text('CREATE INDEX IF NOT EXISTS character_triples_object_embedding_idx ON character_triples USING ivfflat (object_embedding vector_cosine_ops)'))
            db.session.commit()
            print("Created vector similarity indexes")
        except Exception as e:
            print(f"Warning: Could not create vector indexes: {str(e)}")
            print("Continuing without vector indexes...")
        
        # Create composite indexes for common query patterns
        try:
            db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_triples_subject_predicate ON character_triples(subject, predicate)'))
            db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_triples_predicate_object ON character_triples(predicate, object_uri) WHERE NOT is_literal'))
            db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_triples_graph_subject ON character_triples(graph, subject)'))
            db.session.commit()
            print("Created composite indexes for common query patterns")
        except Exception as e:
            print(f"Warning: Could not create composite indexes: {str(e)}")
            print("Continuing without composite indexes...")
        
        print("Character triples table setup completed successfully")

if __name__ == "__main__":
    setup_character_triples_table()
