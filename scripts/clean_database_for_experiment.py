#!/usr/bin/env python3
"""
Clean database script for ProEthica experiments.

This script removes all guidelines, cases/documents, and their associated data
while preserving the core system components (ontologies, worlds, users).
It also resets auto-increment sequences for clean numbering.
"""

import sys
import os
import argparse
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment variables
os.environ['BYPASS_AUTH'] = 'true'
os.environ['ENVIRONMENT'] = 'development'

from app import create_app, db
from sqlalchemy import text, inspect


def get_table_counts():
    """Get current counts of key tables."""
    counts = {}
    
    # Tables to check
    tables = [
        'documents', 'guidelines', 'document_sections', 
        'entity_triples', 'deconstructed_cases'
    ]
    
    try:
        # Also check for association tables that might exist
        inspector = inspect(db.engine)
        all_tables = inspector.get_table_names()
        
        # Add any association tables
        association_tables = [t for t in all_tables if 'association' in t.lower() or 'guideline' in t.lower()]
        tables.extend(association_tables)
        
        for table in set(tables):  # Remove duplicates
            try:
                result = db.session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                counts[table] = result.scalar()
            except Exception as e:
                counts[table] = f"Error: {e}"
    
    except Exception as e:
        print(f"Error getting table counts: {e}")
    
    return counts


def clean_database(dry_run=False):
    """Clean the database of guidelines, cases, and associated data."""
    
    print("=" * 60)
    print("ProEthica Database Cleanup for Experiments")
    print("=" * 60)
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
    else:
        print("⚠️  DESTRUCTIVE MODE - Changes will be made")
    
    # Get initial counts
    print("\n📊 Current database state:")
    initial_counts = get_table_counts()
    for table, count in initial_counts.items():
        print(f"   {table}: {count}")
    
    if not dry_run:
        # Confirm destructive operation (skip if force flag is set)
        import sys
        if '--force' not in sys.argv:
            response = input("\n⚠️  This will permanently delete all guidelines, cases, and associated data. Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Operation cancelled.")
                return
    
    print(f"\n🧹 {'Simulating' if dry_run else 'Executing'} cleanup operations...")
    
    # Define cleanup order (respecting foreign key constraints)
    cleanup_operations = [
        {
            'description': 'Case-guideline associations',
            'tables': ['case_guideline_associations'],
            'condition': None
        },
        {
            'description': 'Outcome patterns',
            'tables': ['outcome_patterns'],
            'condition': None
        },
        {
            'description': 'Case prediction results',
            'tables': ['case_prediction_results'],
            'condition': None
        },
        {
            'description': 'Document sections',
            'tables': ['document_sections'],
            'condition': None
        },
        {
            'description': 'Entity triples for documents',
            'tables': ['entity_triples'],
            'condition': "entity_type IN ('case', 'document', 'guideline')"
        },
        {
            'description': 'Deconstructed cases',
            'tables': ['deconstructed_cases'],
            'condition': None
        },
        {
            'description': 'Documents and cases',
            'tables': ['documents'],
            'condition': None
        },
        {
            'description': 'Guidelines',
            'tables': ['guidelines'],
            'condition': None
        }
    ]
    
    deleted_counts = {}
    
    for operation in cleanup_operations:
        print(f"\n🗑️  {operation['description']}:")
        
        for table in operation['tables']:
            try:
                # Check if table exists
                inspector = inspect(db.engine)
                if table not in inspector.get_table_names():
                    print(f"   ⏭️  Table '{table}' does not exist, skipping")
                    continue
                
                # Build delete query
                if operation['condition']:
                    query = f"DELETE FROM {table} WHERE {operation['condition']}"
                else:
                    query = f"DELETE FROM {table}"
                
                if dry_run:
                    # Get count that would be deleted
                    count_query = query.replace('DELETE', 'SELECT COUNT(*)')
                    result = db.session.execute(text(count_query))
                    count = result.scalar()
                    print(f"   📝 Would delete {count} rows from {table}")
                    deleted_counts[table] = count
                else:
                    # Execute delete
                    result = db.session.execute(text(query))
                    count = result.rowcount
                    print(f"   ✅ Deleted {count} rows from {table}")
                    deleted_counts[table] = count
                    
            except Exception as e:
                print(f"   ❌ Error processing {table}: {e}")
                deleted_counts[table] = f"Error: {e}"
    
    if not dry_run:
        # Commit all changes
        try:
            db.session.commit()
            print("\n✅ All deletions committed successfully")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error committing changes: {e}")
            return
    
    # Reset auto-increment sequences
    print(f"\n🔄 {'Simulating' if dry_run else 'Executing'} sequence resets...")
    
    sequences_to_reset = [
        ('documents', 'id'),
        ('guidelines', 'id'),
        ('document_sections', 'id'),
        ('entity_triples', 'id'),
        ('deconstructed_cases', 'id')
    ]
    
    # Add association table sequences if they exist
    inspector = inspect(db.engine)
    all_tables = inspector.get_table_names()
    for table in all_tables:
        if 'association' in table.lower():
            sequences_to_reset.append((table, 'id'))
    
    for table, id_column in sequences_to_reset:
        try:
            # Check if table exists
            if table not in inspector.get_table_names():
                continue
                
            # Reset sequence to start from 1
            sequence_name = f"{table}_{id_column}_seq"
            reset_query = f"ALTER SEQUENCE {sequence_name} RESTART WITH 1"
            
            if dry_run:
                print(f"   📝 Would reset sequence {sequence_name}")
            else:
                db.session.execute(text(reset_query))
                print(f"   ✅ Reset sequence {sequence_name}")
                
        except Exception as e:
            print(f"   ⚠️  Could not reset sequence for {table}.{id_column}: {e}")
    
    if not dry_run:
        try:
            db.session.commit()
            print("\n✅ All sequence resets committed successfully")
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error committing sequence resets: {e}")
    
    # Show final state
    print(f"\n📊 {'Projected' if dry_run else 'Final'} database state:")
    if not dry_run:
        final_counts = get_table_counts()
        for table, count in final_counts.items():
            print(f"   {table}: {count}")
    else:
        for table, count in initial_counts.items():
            deleted = deleted_counts.get(table, 0)
            if isinstance(deleted, int) and isinstance(count, int):
                remaining = count - deleted
                print(f"   {table}: {count} → {remaining}")
            else:
                print(f"   {table}: {count}")
    
    # Summary
    print(f"\n📋 Cleanup Summary:")
    total_deleted = 0
    for table, count in deleted_counts.items():
        if isinstance(count, int):
            total_deleted += count
            print(f"   {table}: {count} rows {'would be' if dry_run else ''} deleted")
        else:
            print(f"   {table}: {count}")
    
    print(f"\n🎯 Total rows {'would be' if dry_run else ''} deleted: {total_deleted}")
    
    if not dry_run:
        print("\n✅ Database cleanup completed successfully!")
        print("✅ Auto-increment sequences reset to start from 1")
        print("✅ Ready for fresh experiment data")
    else:
        print("\n🔍 Dry run completed - no changes made")
        print("   Run with --execute to perform actual cleanup")
    
    # Show what's preserved
    print(f"\n🛡️  Preserved system components:")
    preserved_items = [
        "✅ User accounts and authentication",
        "✅ Worlds and domain configurations", 
        "✅ Ontologies (engineering-ethics, bfo, proethica-intermediate)",
        "✅ System configuration and settings",
        "✅ MCP server functionality",
        "✅ FIRAC analysis and recommendation engines"
    ]
    
    for item in preserved_items:
        print(f"   {item}")


def main():
    """Main function with argument parsing."""
    parser = argparse.ArgumentParser(description='Clean ProEthica database for experiments')
    parser.add_argument('--execute', action='store_true', 
                       help='Execute the cleanup (default is dry-run)')
    parser.add_argument('--force', action='store_true',
                       help='Skip confirmation prompts')
    
    args = parser.parse_args()
    
    # Create app context
    app = create_app('config')
    
    with app.app_context():
        # Run cleanup
        dry_run = not args.execute
        clean_database(dry_run=dry_run)
        
        if dry_run:
            print(f"\n💡 To execute the cleanup, run:")
            print(f"   python {__file__} --execute")


if __name__ == "__main__":
    main()