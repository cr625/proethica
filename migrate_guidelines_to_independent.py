#!/usr/bin/env python3
"""
Migration script to make Guidelines independent entities.

This script:
1. Copies all Documents with document_type='guideline' to the Guidelines table
2. Updates all foreign key references to point to the new Guideline records
3. Preserves all existing data and relationships
4. Provides rollback capability
"""

import os
import sys
import json
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

def migrate_documents_to_guidelines():
    """
    Migrate Document entries with document_type='guideline' to Guidelines table
    """
    session, engine = get_db_session()
    
    try:
        print("=== Guidelines Independence Migration ===")
        print(f"Started at: {datetime.now()}")
        
        # Step 1: Get all documents that are guidelines
        print("\n1. Finding Documents with document_type='guideline'...")
        result = session.execute(text("""
            SELECT id, title, world_id, content, source, file_path, file_type, 
                   doc_metadata, created_at, updated_at, created_by, data_type
            FROM documents 
            WHERE document_type = 'guideline'
        """))
        
        guideline_docs = result.fetchall()
        print(f"   Found {len(guideline_docs)} guideline documents to migrate")
        
        if not guideline_docs:
            print("   No guideline documents to migrate")
            return
        
        # Step 2: Check for ID conflicts in Guidelines table
        print("\n2. Checking for potential ID conflicts...")
        existing_guideline_ids = session.execute(text("SELECT id FROM guidelines")).fetchall()
        existing_ids = {row[0] for row in existing_guideline_ids}
        
        doc_ids = {doc.id for doc in guideline_docs}
        conflicts = doc_ids.intersection(existing_ids)
        
        if conflicts:
            print(f"   WARNING: ID conflicts detected: {conflicts}")
            print("   Migration will use new sequential IDs for migrated guidelines")
        else:
            print("   No ID conflicts detected")
        
        # Step 3: Create mapping for ID changes
        print("\n3. Planning ID mappings...")
        if existing_ids:
            next_id = max(existing_ids) + 1
        else:
            next_id = 1
        
        id_mapping = {}  # old_document_id -> new_guideline_id
        
        for doc in guideline_docs:
            if doc.id in existing_ids:
                # Use new sequential ID
                id_mapping[doc.id] = next_id
                next_id += 1
            else:
                # Keep original ID
                id_mapping[doc.id] = doc.id
        
        print(f"   ID mappings: {id_mapping}")
        
        # Step 4: Migrate documents to guidelines
        print("\n4. Migrating Documents to Guidelines table...")
        for doc in guideline_docs:
            new_id = id_mapping[doc.id]
            
            # Insert into guidelines table (using correct column names from schema)
            session.execute(text("""
                INSERT INTO guidelines (id, world_id, title, content, source_url, file_path, 
                                      file_type, guideline_metadata, created_at, updated_at, 
                                      created_by, data_type)
                VALUES (:id, :world_id, :title, :content, :source_url, :file_path, 
                        :file_type, :metadata, :created_at, :updated_at, 
                        :created_by, :data_type)
            """), {
                'id': new_id,
                'world_id': doc.world_id,
                'title': doc.title,
                'content': doc.content,
                'source_url': doc.source,  # maps to source column
                'file_path': doc.file_path,
                'file_type': doc.file_type,
                'metadata': json.dumps(doc.doc_metadata or {}),
                'created_at': doc.created_at,
                'updated_at': doc.updated_at,
                'created_by': doc.created_by,
                'data_type': doc.data_type
            })
            
            print(f"   Migrated Document ID {doc.id} -> Guideline ID {new_id}: {doc.title}")
        
        # Step 5: Update foreign key references
        print("\n5. Updating foreign key references...")
        
        # Update guideline_sections
        for old_id, new_id in id_mapping.items():
            result = session.execute(text("""
                UPDATE guideline_sections 
                SET guideline_id = :new_id 
                WHERE guideline_id = :old_id
            """), {'old_id': old_id, 'new_id': new_id})
            
            if result.rowcount > 0:
                print(f"   Updated {result.rowcount} guideline_sections records: {old_id} -> {new_id}")
        
        # Update entity_triples
        for old_id, new_id in id_mapping.items():
            result = session.execute(text("""
                UPDATE entity_triples 
                SET guideline_id = :new_id 
                WHERE guideline_id = :old_id
            """), {'old_id': old_id, 'new_id': new_id})
            
            if result.rowcount > 0:
                print(f"   Updated {result.rowcount} entity_triples records: {old_id} -> {new_id}")
        
        # Update document_concept_annotations (note: plural table name)
        for old_id, new_id in id_mapping.items():
            result = session.execute(text("""
                UPDATE document_concept_annotations 
                SET document_id = :new_id 
                WHERE document_type = 'guideline' AND document_id = :old_id
            """), {'old_id': old_id, 'new_id': new_id})
            
            if result.rowcount > 0:
                print(f"   Updated {result.rowcount} document_concept_annotations records: {old_id} -> {new_id}")
        
        # Step 6: Remove migrated documents from documents table
        print("\n6. Removing migrated documents from Documents table...")
        old_doc_ids = list(id_mapping.keys())
        
        # First remove dependent document_chunks
        result = session.execute(text("""
            DELETE FROM document_chunks 
            WHERE document_id = ANY(:doc_ids)
        """), {'doc_ids': old_doc_ids})
        
        if result.rowcount > 0:
            print(f"   Removed {result.rowcount} document_chunks records")
        
        # Then remove the documents
        result = session.execute(text("""
            DELETE FROM documents 
            WHERE document_type = 'guideline' AND id = ANY(:doc_ids)
        """), {'doc_ids': old_doc_ids})
        
        print(f"   Removed {result.rowcount} guideline documents from Documents table")
        
        # Step 7: Reset sequence for guidelines table
        print("\n7. Updating guideline ID sequence...")
        max_guideline_id = session.execute(text("SELECT MAX(id) FROM guidelines")).scalar()
        if max_guideline_id:
            session.execute(text(f"SELECT setval('guidelines_id_seq', {max_guideline_id})"))
            print(f"   Set guidelines sequence to {max_guideline_id}")
        
        # Commit all changes
        session.commit()
        print(f"\n=== Migration completed successfully at {datetime.now()} ===")
        print(f"Migrated {len(guideline_docs)} guidelines to independent entities")
        print(f"ID mappings applied: {id_mapping}")
        
        return True
        
    except Exception as e:
        print(f"\nERROR during migration: {e}")
        session.rollback()
        return False
    
    finally:
        session.close()

def verify_migration():
    """Verify the migration was successful"""
    session, engine = get_db_session()
    
    try:
        print("\n=== Migration Verification ===")
        
        # Check no guideline documents remain
        result = session.execute(text("SELECT COUNT(*) FROM documents WHERE document_type = 'guideline'"))
        doc_count = result.scalar()
        print(f"Documents with document_type='guideline': {doc_count}")
        
        # Check guideline count
        result = session.execute(text("SELECT COUNT(*) FROM guidelines"))
        guideline_count = result.scalar()
        print(f"Total Guidelines: {guideline_count}")
        
        # Check guideline_sections all have valid guideline_id
        result = session.execute(text("""
            SELECT COUNT(*) FROM guideline_sections gs
            WHERE NOT EXISTS (SELECT 1 FROM guidelines g WHERE g.id = gs.guideline_id)
        """))
        orphaned_sections = result.scalar()
        print(f"Orphaned guideline_sections: {orphaned_sections}")
        
        # Check entity_triples all have valid guideline_id
        result = session.execute(text("""
            SELECT COUNT(*) FROM entity_triples et
            WHERE et.guideline_id IS NOT NULL 
            AND NOT EXISTS (SELECT 1 FROM guidelines g WHERE g.id = et.guideline_id)
        """))
        orphaned_triples = result.scalar()
        print(f"Orphaned entity_triples: {orphaned_triples}")
        
        success = (doc_count == 0 and orphaned_sections == 0 and orphaned_triples == 0)
        print(f"\nMigration verification: {'PASSED' if success else 'FAILED'}")
        return success
        
    except Exception as e:
        print(f"Error during verification: {e}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    print("Starting Guidelines Independence Migration")
    
    # Set environment
    os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://proethica_user:proethica_development_password@localhost:5432/ai_ethical_dm'
    
    # Run migration
    if migrate_documents_to_guidelines():
        verify_migration()
    else:
        print("Migration failed - database unchanged")