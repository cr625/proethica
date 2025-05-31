#!/usr/bin/env python3
"""Check for entity_triples with NULL guideline_id."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the project root to Python path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()

# Set database URL if not set
if not os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = 'postgresql://postgres:postgres@localhost:5433/ai_ethical_dm'
if not os.getenv('SQLALCHEMY_DATABASE_URI'):
    os.environ['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']

from app import create_app, db
from app.models.entity_triple import EntityTriple
from app.models.guideline import Guideline

app = create_app()

with app.app_context():
    # Count total guidelines
    total_guidelines = Guideline.query.count()
    print(f"\nTotal guidelines in database: {total_guidelines}")
    
    # List all guidelines
    guidelines = Guideline.query.all()
    for g in guidelines:
        triple_count = EntityTriple.query.filter_by(guideline_id=g.id).count()
        print(f"  - Guideline {g.id}: {g.title} ({triple_count} triples)")
    
    # Count triples by guideline_id
    print("\n=== Entity Triple Counts by guideline_id ===")
    
    # Get all unique guideline_ids (including NULL)
    from sqlalchemy import func, distinct
    guideline_ids = db.session.query(distinct(EntityTriple.guideline_id)).all()
    
    for (gid,) in guideline_ids:
        count = EntityTriple.query.filter_by(guideline_id=gid).count()
        if gid is None:
            print(f"NULL guideline_id: {count} triples")
        else:
            print(f"guideline_id {gid}: {count} triples")
    
    # Check specifically for guideline_concept type with NULL guideline_id
    null_guideline_concepts = EntityTriple.query.filter(
        EntityTriple.entity_type == 'guideline_concept',
        EntityTriple.guideline_id == None
    ).count()
    
    print(f"\n=== Guideline Concept Triples with NULL guideline_id: {null_guideline_concepts} ===")
    
    # Show a few examples if there are any
    if null_guideline_concepts > 0:
        examples = EntityTriple.query.filter(
            EntityTriple.entity_type == 'guideline_concept',
            EntityTriple.guideline_id == None
        ).limit(5).all()
        
        print("\nExample triples with NULL guideline_id:")
        for triple in examples:
            print(f"  - {triple.subject_label or triple.subject} -> {triple.predicate_label} -> {triple.object_label or triple.object_literal or triple.object_uri}")
            print(f"    Entity ID: {triple.entity_id}, World ID: {triple.world_id}")