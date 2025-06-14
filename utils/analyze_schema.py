#!/usr/bin/env python3
"""
Analyze the current database schema to understand what we're working with
for the type mapping implementation.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app import create_app
from app.models import db

# Create app with the same configuration as the debug app
app = create_app('config')

with app.app_context():
    # Get all table names
    inspector = db.inspect(db.engine)
    tables = inspector.get_table_names()
    
    print("📊 CURRENT DATABASE SCHEMA ANALYSIS")
    print("=" * 60)
    print(f"Total tables: {len(tables)}")
    print("\nAll tables:")
    for table in sorted(tables):
        print(f"  - {table}")
    
    print("\n🎯 KEY TABLES FOR TYPE MAPPING")
    print("=" * 40)
    
    key_tables = ['guidelines', 'entity_triples', 'documents', 'users']
    for table in key_tables:
        if table in tables:
            print(f"\n=== {table.upper()} ===")
            columns = inspector.get_columns(table)
            for col in columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                default = f" DEFAULT {col['default']}" if col.get('default') else ""
                print(f"  {col['name']:<25} {str(col['type']):<20} {nullable}{default}")
            
            # Show foreign keys
            fks = inspector.get_foreign_keys(table)
            if fks:
                print("  Foreign Keys:")
                for fk in fks:
                    print(f"    {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")
            
            # Show indexes
            indexes = inspector.get_indexes(table)
            if indexes:
                print("  Indexes:")
                for idx in indexes:
                    cols = ", ".join(idx['column_names'])
                    unique = " (UNIQUE)" if idx['unique'] else ""
                    print(f"    {idx['name']}: {cols}{unique}")
    
    print("\n🔍 ENTITY_TRIPLES DATA SAMPLE")
    print("=" * 30)
    
    # Get a sample of entity_triples to understand current data structure
    from app.models.entity_triple import EntityTriple
    
    sample_triples = EntityTriple.query.filter(
        EntityTriple.entity_type == 'guideline_concept'
    ).limit(5).all()
    
    if sample_triples:
        print("Sample guideline concept triples:")
        for triple in sample_triples:
            print(f"  {triple.subject_label} --[{triple.predicate_label}]--> {triple.object_label or triple.object_literal}")
            if hasattr(triple, 'original_llm_type'):
                print(f"    Original LLM Type: {triple.original_llm_type}")
            print(f"    Metadata: {triple.triple_metadata}")
    else:
        print("No guideline concept triples found in database")
    
    print("\n📋 RECOMMENDATIONS FOR SCHEMA EXTENSIONS")
    print("=" * 45)
    
    # Check if the entity_triples table already has type mapping fields
    et_columns = [col['name'] for col in inspector.get_columns('entity_triples')]
    
    if 'original_llm_type' not in et_columns:
        print("✅ Need to add: original_llm_type to entity_triples")
    else:
        print("✅ Already exists: original_llm_type")
        
    if 'type_mapping_confidence' not in et_columns:
        print("✅ Need to add: type_mapping_confidence to entity_triples")
    else:
        print("✅ Already exists: type_mapping_confidence")
        
    if 'needs_type_review' not in et_columns:
        print("✅ Need to add: needs_type_review to entity_triples")
    else:
        print("✅ Already exists: needs_type_review")
        
    # Check if we need new tables
    new_tables_needed = []
    if 'pending_concept_types' not in tables:
        new_tables_needed.append('pending_concept_types')
    if 'custom_concept_types' not in tables:
        new_tables_needed.append('custom_concept_types')
    if 'concept_type_mappings' not in tables:
        new_tables_needed.append('concept_type_mappings')
        
    if new_tables_needed:
        print(f"\n🆕 New tables needed: {', '.join(new_tables_needed)}")
    else:
        print("\n✅ All required tables already exist")

if __name__ == "__main__":
    pass