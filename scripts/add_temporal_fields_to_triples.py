#!/usr/bin/env python
"""
Script to add temporal fields to the entity_triples table and demonstrate temporal triple capabilities.
This script:
1. Adds valid_from and valid_to fields to the entity_triples table
2. Extends the EntityTripleService to support temporal queries
3. Demonstrates temporal triple queries with different time perspectives
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from pprint import pprint

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.character import Character
from app.models.entity_triple import EntityTriple
from app.services.entity_triple_service import EntityTripleService
from sqlalchemy import text, Column, DateTime

def add_temporal_fields():
    """Add temporal fields to the entity_triples table."""
    print("\n=== Adding Temporal Fields to entity_triples Table ===")
    
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
        return True
    except Exception as e:
        print(f"Error adding temporal fields: {e}")
        db.session.rollback()
        return False

def extend_entity_triple_model():
    """Extend the EntityTriple model to include temporal fields."""
    print("\n=== Extending EntityTriple Model ===")
    
    try:
        # Add the fields to the model
        EntityTriple.valid_from = Column(DateTime, default=datetime.utcnow)
        EntityTriple.valid_to = Column(DateTime, nullable=True)
        
        print("Successfully extended EntityTriple model")
        return True
    except Exception as e:
        print(f"Error extending EntityTriple model: {e}")
        return False

def extend_entity_triple_service():
    """Extend the EntityTripleService to support temporal queries."""
    print("\n=== Extending EntityTripleService ===")
    
    # The existing service already has the necessary structure
    # We'll just add methods for temporal-specific operations
    
    # Add temporal query capability to the EntityTripleService class
    def find_triples_at_time(self, at_time=None, **kwargs):
        """
        Find triples that were valid at a specific time.
        If at_time is None, returns currently valid triples.
        """
        if at_time is None:
            at_time = datetime.utcnow()
            
        query = db.session.query(EntityTriple)
        
        # Apply standard filters
        for key, value in kwargs.items():
            if hasattr(EntityTriple, key) and value is not None:
                query = query.filter(getattr(EntityTriple, key) == value)
        
        # Apply temporal filter
        query = query.filter(
            (EntityTriple.valid_from <= at_time) &
            ((EntityTriple.valid_to.is_(None)) | (EntityTriple.valid_to > at_time))
        )
        
        return query.all()
    
    # Add the method to the class
    EntityTripleService.find_triples_at_time = find_triples_at_time
    
    print("Successfully extended EntityTripleService")
    return True

def demonstrate_temporal_triples():
    """Demonstrate working with temporal triples."""
    print("\n=== Demonstrating Temporal Triples ===")
    
    # Get a character to work with
    character = Character.query.first()
    if not character:
        print("No characters found for demonstration")
        return False
    
    print(f"Using character: {character.name} (ID: {character.id})")
    
    # Create EntityTripleService
    triple_service = EntityTripleService()
    
    # Get the current time and some time points
    now = datetime.utcnow()
    past = now - timedelta(days=30)
    future = now + timedelta(days=30)
    
    # Create a triple with a past valid_from
    print("\nCreating a triple with past validity:")
    past_triple = EntityTriple(
        subject=str(triple_service.generate_uri('character', character.name, character.id)),
        predicate=str(triple_service.namespaces['proethica']['pastRole']),
        object_literal="Past Engineer",
        is_literal=True,
        entity_type='character',
        entity_id=character.id,
        valid_from=past,
        valid_to=now
    )
    db.session.add(past_triple)
    
    # Create a triple with current validity
    print("Creating a triple with current validity:")
    current_triple = EntityTriple(
        subject=str(triple_service.generate_uri('character', character.name, character.id)),
        predicate=str(triple_service.namespaces['proethica']['currentRole']),
        object_literal="Current Engineer",
        is_literal=True,
        entity_type='character',
        entity_id=character.id,
        valid_from=now,
        valid_to=None
    )
    db.session.add(current_triple)
    
    # Create a triple with future validity
    print("Creating a triple with future validity:")
    future_triple = EntityTriple(
        subject=str(triple_service.generate_uri('character', character.name, character.id)),
        predicate=str(triple_service.namespaces['proethica']['futureRole']),
        object_literal="Future Engineer",
        is_literal=True,
        entity_type='character',
        entity_id=character.id,
        valid_from=future,
        valid_to=None
    )
    db.session.add(future_triple)
    
    db.session.commit()
    
    # Now query at different time points
    print("\nQuerying triples at different time points:")
    
    # Past query
    past_time = past + timedelta(hours=1)
    print(f"\nTriples valid at {past_time.isoformat()}:")
    past_results = triple_service.find_triples_at_time(
        at_time=past_time,
        entity_type='character',
        entity_id=character.id
    )
    
    for triple in past_results:
        print(f"  - {triple.predicate} = {triple.object_literal or triple.object_uri}")
        print(f"    Valid from: {triple.valid_from}, Valid to: {triple.valid_to}")
    
    # Current query
    print(f"\nTriples valid now:")
    current_results = triple_service.find_triples_at_time(
        entity_type='character',
        entity_id=character.id
    )
    
    for triple in current_results:
        print(f"  - {triple.predicate} = {triple.object_literal or triple.object_uri}")
        print(f"    Valid from: {triple.valid_from}, Valid to: {triple.valid_to}")
    
    # Future query
    future_time = future + timedelta(hours=1)
    print(f"\nTriples valid at {future_time.isoformat()}:")
    future_results = triple_service.find_triples_at_time(
        at_time=future_time,
        entity_type='character',
        entity_id=character.id
    )
    
    for triple in future_results:
        print(f"  - {triple.predicate} = {triple.object_literal or triple.object_uri}")
        print(f"    Valid from: {triple.valid_from}, Valid to: {triple.valid_to}")
    
    return True

def main(args):
    """Run the script steps."""
    app = create_app()
    
    with app.app_context():
        print("=== Adding Temporal Features to Entity Triples ===")
        
        # Step 1: Add temporal fields to the entity_triples table
        if not add_temporal_fields():
            if not args.force:
                print("Failed to add temporal fields. Aborting.")
                return
            print("Failed to add temporal fields but continuing due to --force flag.")
        
        # Step 2: Extend the EntityTriple model
        if not extend_entity_triple_model():
            if not args.force:
                print("Failed to extend EntityTriple model. Aborting.")
                return
            print("Failed to extend EntityTriple model but continuing due to --force flag.")
        
        # Step 3: Extend the EntityTripleService
        if not extend_entity_triple_service():
            if not args.force:
                print("Failed to extend EntityTripleService. Aborting.")
                return
            print("Failed to extend EntityTripleService but continuing due to --force flag.")
        
        # Step 4: Demonstrate temporal triples
        if not demonstrate_temporal_triples():
            print("Failed to demonstrate temporal triples.")
        
        print("\n=== Temporal Features Implementation Complete ===")
        print("""
This implementation now allows for:
1. Tracking validity periods for triples with valid_from and valid_to fields
2. Querying triples that were valid at any specific time point
3. Representing past, present, and future states of entities
4. Time-travel queries to see how the knowledge graph looked at any point in time

These temporal features are particularly valuable for:
- Historical analysis of ethical decisions
- Understanding how character attributes and relationships evolve over time
- Tracing the progression of events in a scenario
- Analyzing how ethical principles were applied at different time points
        """)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Add temporal fields to entity_triples')
    parser.add_argument('--force', action='store_true', help='Continue even if errors occur')
    args = parser.parse_args()
    
    main(args)
