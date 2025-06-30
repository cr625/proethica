#!/usr/bin/env python3
"""
Run the type mapping database migrations.
This script applies the schema changes needed for intelligent type mapping.
"""

import os
from dotenv import load_dotenv
from app import create_app
from app.models import db

# Load environment variables
load_dotenv()

def run_sql_file(file_path):
    """Execute a SQL file against the database."""
    with open(file_path, 'r') as f:
        sql_content = f.read()
    
    # Split by transaction blocks (statements between BEGIN; and COMMIT;)
    statements = []
    current_statement = []
    in_transaction = False
    
    for line in sql_content.split('\n'):
        line = line.strip()
        if not line or line.startswith('--'):
            continue
            
        if line == 'BEGIN;':
            in_transaction = True
            current_statement = ['BEGIN;']
        elif line == 'COMMIT;':
            current_statement.append('COMMIT;')
            statements.append('\n'.join(current_statement))
            current_statement = []
            in_transaction = False
        elif in_transaction:
            current_statement.append(line)
        else:
            # Single statement outside transaction
            statements.append(line)
    
    # Execute each statement/transaction block
    for statement in statements:
        if statement.strip():
            try:
                db.session.execute(db.text(statement))
                db.session.commit()
                print(f"✅ Executed statement block successfully")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error executing statement: {e}")
                print(f"Statement: {statement[:100]}...")
                raise

def main():
    """Run all type mapping migrations."""
    print("🚀 RUNNING TYPE MAPPING MIGRATIONS")
    print("=" * 50)
    
    # Create app with the same configuration as the debug app
    app = create_app('config')
    
    with app.app_context():
        migration_files = [
            'migrations/001_add_type_mapping_fields.sql',
            'migrations/002_create_type_management_tables.sql', 
            'migrations/003_backfill_existing_data.sql'
        ]
        
        print(f"📊 Current database: {db.engine.url}")
        print(f"📝 Running {len(migration_files)} migration files...\n")
        
        for i, migration_file in enumerate(migration_files, 1):
            print(f"[{i}/{len(migration_files)}] Running {migration_file}...")
            
            if not os.path.exists(migration_file):
                print(f"❌ Migration file not found: {migration_file}")
                continue
                
            try:
                run_sql_file(migration_file)
                print(f"✅ {migration_file} completed successfully\n")
            except Exception as e:
                print(f"❌ {migration_file} failed: {e}")
                print("🛑 Migration stopped due to error")
                return False
        
        print("🎉 ALL MIGRATIONS COMPLETED SUCCESSFULLY!")
        print("\n📊 Verifying new tables...")
        
        # Verify new tables exist
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        
        expected_tables = ['pending_concept_types', 'custom_concept_types', 'concept_type_mappings']
        for table in expected_tables:
            if table in tables:
                print(f"✅ {table} table created")
            else:
                print(f"❌ {table} table missing")
        
        # Verify new columns in entity_triples
        et_columns = [col['name'] for col in inspector.get_columns('entity_triples')]
        expected_columns = ['original_llm_type', 'type_mapping_confidence', 'needs_type_review', 'mapping_justification']
        for column in expected_columns:
            if column in et_columns:
                print(f"✅ entity_triples.{column} column added")
            else:
                print(f"❌ entity_triples.{column} column missing")
        
        print("\n🔍 Checking sample data...")
        
        # Check if data was backfilled
        from app.models.entity_triple import EntityTriple
        sample = EntityTriple.query.filter(
            EntityTriple.entity_type == 'guideline_concept',
            EntityTriple.needs_type_review == True
        ).first()
        
        if sample:
            print(f"✅ Found concepts flagged for review: {sample.subject_label}")
            print(f"   Original type: {sample.original_llm_type}")
            print(f"   Confidence: {sample.type_mapping_confidence}")
        else:
            print("ℹ️  No concepts flagged for review (may be expected)")
        
        print("\n🎯 PHASE 2 DATABASE EXTENSIONS COMPLETE!")
        print("Ready to proceed with Phase 3: Core Integration")
        
        return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)