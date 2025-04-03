#!/usr/bin/env python
"""
Initialization script for RDF triple storage for characters.
This script performs the necessary setup steps to use RDF triples in the application.
"""

import os
import sys
import argparse

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from sqlalchemy import text

def check_prerequisites():
    """Check if required prerequisites are installed."""
    try:
        import rdflib
        print("✓ rdflib is installed")
    except ImportError:
        print("✗ rdflib is not installed")
        print("  Please install it with: pip install rdflib")
        return False

    try:
        import numpy
        print("✓ numpy is installed")
    except ImportError:
        print("✗ numpy is not installed")
        print("  Please install it with: pip install numpy")
        return False

    return True

def check_pgvector(app):
    """Check if pgvector extension is enabled in PostgreSQL."""
    with app.app_context():
        try:
            result = db.session.execute(text("SELECT * FROM pg_extension WHERE extname = 'vector'"))
            if result.rowcount == 0:
                print("✗ pgvector extension is not enabled")
                print("  Please run: python scripts/install_pgvector.sh")
                return False
            print("✓ pgvector extension is enabled")
            return True
        except Exception as e:
            print(f"✗ Error checking pgvector extension: {str(e)}")
            return False

def setup_character_triples_table(app, force=False):
    """Set up the character_triples table."""
    with app.app_context():
        try:
            # Check if the table exists
            result = db.session.execute(text("SELECT to_regclass('character_triples')"))
            table_exists = result.scalar() is not None
            
            if table_exists and not force:
                print("✓ character_triples table already exists")
                print("  Use --force to recreate the table if needed")
                return True
            
            if table_exists and force:
                # Drop the table
                print("Dropping existing character_triples table...")
                db.session.execute(text('DROP TABLE IF EXISTS character_triples CASCADE'))
                db.session.commit()
                print("✓ Dropped character_triples table")
            
            # Import and create the table
            from app.models.triple import Triple
            
            # Create the table using SQLAlchemy's create_all
            print("Creating character_triples table...")
            Triple.__table__.create(db.engine)
            print("✓ Created character_triples table")
            
            # Alter the table to use vector type for embeddings
            try:
                # Convert ARRAY columns to vector type
                db.session.execute(text('ALTER TABLE character_triples ALTER COLUMN subject_embedding TYPE vector USING subject_embedding::vector'))
                db.session.execute(text('ALTER TABLE character_triples ALTER COLUMN predicate_embedding TYPE vector USING predicate_embedding::vector'))
                db.session.execute(text('ALTER TABLE character_triples ALTER COLUMN object_embedding TYPE vector USING object_embedding::vector'))
                db.session.commit()
                print("✓ Altered embedding columns to use vector type")
            except Exception as e:
                print(f"! Warning: Could not alter embedding columns: {str(e)}")
                print("  Continuing without vector columns...")
            
            # Create vector similarity indexes
            try:
                db.session.execute(text('CREATE INDEX IF NOT EXISTS character_triples_subject_embedding_idx ON character_triples USING ivfflat (subject_embedding vector_cosine_ops)'))
                db.session.execute(text('CREATE INDEX IF NOT EXISTS character_triples_predicate_embedding_idx ON character_triples USING ivfflat (predicate_embedding vector_cosine_ops)'))
                db.session.execute(text('CREATE INDEX IF NOT EXISTS character_triples_object_embedding_idx ON character_triples USING ivfflat (object_embedding vector_cosine_ops)'))
                db.session.commit()
                print("✓ Created vector similarity indexes")
            except Exception as e:
                print(f"! Warning: Could not create vector indexes: {str(e)}")
                print("  Continuing without vector indexes...")
            
            # Create composite indexes for common query patterns
            try:
                db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_triples_subject_predicate ON character_triples(subject, predicate)'))
                db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_triples_predicate_object ON character_triples(predicate, object_uri) WHERE NOT is_literal'))
                db.session.execute(text('CREATE INDEX IF NOT EXISTS idx_triples_graph_subject ON character_triples(graph, subject)'))
                db.session.commit()
                print("✓ Created composite indexes for common query patterns")
            except Exception as e:
                print(f"! Warning: Could not create composite indexes: {str(e)}")
                print("  Continuing without composite indexes...")
            
            return True
        except Exception as e:
            print(f"✗ Error setting up character_triples table: {str(e)}")
            return False

def register_services():
    """Register the RDF service with the application."""
    try:
        from app.services.rdf_service import RDFService
        print("✓ RDF service is available")
        return True
    except ImportError as e:
        print(f"✗ RDF service is not available: {str(e)}")
        return False

def main():
    """Initialize RDF triple storage for characters."""
    parser = argparse.ArgumentParser(description="Initialize RDF triple storage for characters")
    parser.add_argument("--force", action="store_true", help="Force recreation of tables")
    args = parser.parse_args()

    print("Initializing RDF triple storage for characters...")
    
    # Check prerequisites
    if not check_prerequisites():
        print("\nPlease install the required packages and try again.")
        return 1
    
    # Create app and push application context
    app = create_app()
    
    # Check pgvector
    if not check_pgvector(app):
        print("\nPlease set up pgvector and try again.")
        return 1
    
    # Set up character_triples table
    if not setup_character_triples_table(app, args.force):
        print("\nFailed to set up character_triples table.")
        return 1
    
    # Register services
    if not register_services():
        print("\nFailed to register RDF services.")
        return 1
    
    print("\nRDF triple storage initialization completed successfully!")
    print("\nNext steps:")
    print("1. Run example script: python scripts/test_character_rdf_triples.py")
    print("2. Run semantic search example: python scripts/test_rdf_embeddings.py")
    print("3. Try integration with existing code: python scripts/integrate_character_rdf.py")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
