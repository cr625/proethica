#!/usr/bin/env python3
"""
Script to delete ALL guidelines and related data from the database.

This will delete:
- All guidelines from the guidelines table
- All guideline_sections
- All entity_triples related to guidelines
- All guideline_semantic_triples
- All guideline_term_candidates
- All document_concept_annotations for guidelines

WARNING: This is irreversible! All guideline data will be permanently deleted.
"""

import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(__file__))

def get_db_session():
    """Get database session"""
    database_uri = os.environ.get('SQLALCHEMY_DATABASE_URI', 
                                 'postgresql://proethica_user:proethica_development_password@localhost:5432/ai_ethical_dm')
    engine = create_engine(database_uri)
    Session = sessionmaker(bind=engine)
    return Session(), engine

def delete_all_guidelines():
    """Delete all guidelines and related data"""
    session, engine = get_db_session()
    
    try:
        print("=== GUIDELINE DATA DELETION ===")
        print(f"Started at: {datetime.now()}")
        print("\nWARNING: This will permanently delete ALL guideline data!")
        
        # Get counts before deletion
        print("\n1. Checking current data...")
        
        # Count guidelines
        result = session.execute(text("SELECT COUNT(*) FROM guidelines"))
        guideline_count = result.scalar()
        print(f"   Guidelines to delete: {guideline_count}")
        
        # Count guideline_sections
        result = session.execute(text("SELECT COUNT(*) FROM guideline_sections"))
        section_count = result.scalar()
        print(f"   Guideline sections to delete: {section_count}")
        
        # Count entity_triples with guideline_id
        result = session.execute(text("SELECT COUNT(*) FROM entity_triples WHERE guideline_id IS NOT NULL"))
        triple_count = result.scalar()
        print(f"   Entity triples to delete: {triple_count}")
        
        # Count guideline_semantic_triples
        result = session.execute(text("SELECT COUNT(*) FROM guideline_semantic_triples"))
        semantic_triple_count = result.scalar()
        print(f"   Semantic triples to delete: {semantic_triple_count}")
        
        # Count guideline_term_candidates
        result = session.execute(text("SELECT COUNT(*) FROM guideline_term_candidates"))
        term_count = result.scalar()
        print(f"   Term candidates to delete: {term_count}")
        
        # Count document_concept_annotations for guidelines
        result = session.execute(text("SELECT COUNT(*) FROM document_concept_annotations WHERE document_type = 'guideline'"))
        annotation_count = result.scalar()
        print(f"   Document concept annotations to delete: {annotation_count}")
        
        # Confirm deletion
        response = input("\nAre you sure you want to delete ALL guideline data? Type 'YES' to confirm: ")
        if response != 'YES':
            print("Deletion cancelled.")
            return False
        
        print("\n2. Deleting related data...")
        
        # Delete document_concept_annotations
        result = session.execute(text("DELETE FROM document_concept_annotations WHERE document_type = 'guideline'"))
        print(f"   Deleted {result.rowcount} document_concept_annotations")
        
        # Delete guideline_term_candidates
        result = session.execute(text("DELETE FROM guideline_term_candidates"))
        print(f"   Deleted {result.rowcount} guideline_term_candidates")
        
        # Delete guideline_semantic_triples
        result = session.execute(text("DELETE FROM guideline_semantic_triples"))
        print(f"   Deleted {result.rowcount} guideline_semantic_triples")
        
        # Delete entity_triples with guideline_id
        result = session.execute(text("DELETE FROM entity_triples WHERE guideline_id IS NOT NULL"))
        print(f"   Deleted {result.rowcount} entity_triples")
        
        # Delete guideline_sections
        result = session.execute(text("DELETE FROM guideline_sections"))
        print(f"   Deleted {result.rowcount} guideline_sections")
        
        # Delete guidelines
        result = session.execute(text("DELETE FROM guidelines"))
        print(f"   Deleted {result.rowcount} guidelines")
        
        # Reset the sequence for guidelines table
        print("\n3. Resetting ID sequences...")
        session.execute(text("SELECT setval('guidelines_id_seq', 1, false)"))
        session.execute(text("SELECT setval('guideline_sections_id_seq', 1, false)"))
        print("   ID sequences reset to start from 1")
        
        # Commit all changes
        session.commit()
        print(f"\n=== Deletion completed successfully at {datetime.now()} ===")
        
        return True
        
    except Exception as e:
        print(f"\nERROR during deletion: {e}")
        session.rollback()
        return False
    
    finally:
        session.close()

def verify_deletion():
    """Verify all guideline data has been deleted"""
    session, engine = get_db_session()
    
    try:
        print("\n=== Verification ===")
        
        # Check guidelines
        result = session.execute(text("SELECT COUNT(*) FROM guidelines"))
        count = result.scalar()
        print(f"Remaining guidelines: {count}")
        
        # Check guideline_sections
        result = session.execute(text("SELECT COUNT(*) FROM guideline_sections"))
        count = result.scalar()
        print(f"Remaining guideline_sections: {count}")
        
        # Check entity_triples
        result = session.execute(text("SELECT COUNT(*) FROM entity_triples WHERE guideline_id IS NOT NULL"))
        count = result.scalar()
        print(f"Remaining entity_triples with guideline_id: {count}")
        
        # Check document_concept_annotations
        result = session.execute(text("SELECT COUNT(*) FROM document_concept_annotations WHERE document_type = 'guideline'"))
        count = result.scalar()
        print(f"Remaining guideline annotations: {count}")
        
        print("\nDatabase is ready for fresh guideline uploads!")
        return True
        
    except Exception as e:
        print(f"Error during verification: {e}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    print("Guideline Data Deletion Tool")
    print("=" * 40)
    
    # Set environment
    os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://proethica_user:proethica_development_password@localhost:5432/ai_ethical_dm'
    
    # Run deletion
    if delete_all_guidelines():
        verify_deletion()
    else:
        print("Deletion was not completed.")