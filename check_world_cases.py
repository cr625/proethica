#!/usr/bin/env python3
"""
Script to check the world's cases array and list all case study documents in the world.
"""

import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import the application and database
from app import create_app, db

def check_world_cases():
    """
    Check the world's cases array and list all case study documents.
    """
    app = create_app()
    with app.app_context():
        from app.models.world import World
        from app.models.document import Document
        
        # Get the Engineering Ethics world
        world = World.query.get(1)
        if not world:
            print("Error: Engineering Ethics world not found")
            return
        
        print(f"Engineering Ethics World: {world.name}")
        print("=" * 50)
        
        # Check the cases array
        print(f"World cases array: {world.cases}")
        
        # Check if there are any case study documents in the world
        case_docs = Document.query.filter_by(
            world_id=1,
            document_type='case_study'
        ).all()
        
        print(f"Case study documents in the world: {len(case_docs)}")
        for doc in case_docs:
            print(f"  - ID {doc.id}: {doc.title}")
        
        # Update the world's cases array to include any missing documents
        missing_docs = []
        for doc in case_docs:
            if world.cases is None or doc.id not in world.cases:
                missing_docs.append(doc.id)
        
        if missing_docs:
            print(f"\nFound {len(missing_docs)} documents missing from world.cases array: {missing_docs}")
            print("Updating world.cases array...")
            
            # Initialize cases array if None
            if world.cases is None:
                world.cases = []
            
            # Convert case IDs to integers to ensure correct storage
            missing_docs_int = [int(doc_id) for doc_id in missing_docs]
            
            # Create a new list with existing cases (if any) + missing docs
            updated_cases = list(world.cases) if world.cases else []
            for doc_id in missing_docs_int:
                if doc_id not in updated_cases:
                    updated_cases.append(doc_id)
            
            # Set the cases field and save
            world.cases = updated_cases
            
            # Save changes
            try:
                db.session.add(world)
                db.session.commit()
                
                # Verify the update
                db.session.refresh(world)
                print(f"Updated world cases array: {world.cases}")
            except Exception as e:
                print(f"Error updating world.cases: {str(e)}")
                db.session.rollback()
        else:
            print("\nNo missing documents found in world.cases array.")
        
        return world, case_docs

if __name__ == "__main__":
    check_world_cases()
