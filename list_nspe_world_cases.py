#!/usr/bin/env python3
"""
Script to list NSPE ethics cases that are correctly associated with worlds.
This script looks for Document objects with document_type='case_study' 
that are referenced in the world's cases array.
"""

import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import the application and database
from app import create_app, db

def list_nspe_world_cases():
    """
    List all NSPE ethics cases that are associated with worlds.
    """
    app = create_app()
    with app.app_context():
        from app.models.document import Document
        from app.models.world import World
        from app.models.entity_triple import EntityTriple
        
        # Get the Engineering Ethics world
        world = World.query.filter_by(id=1).first()
        if not world:
            print("Error: Engineering Ethics world not found")
            return
        
        print(f"Engineering Ethics World: {world.name}")
        print("=" * 50)
        
        # Check if the world has cases
        if not world.cases or len(world.cases) == 0:
            print("No cases associated with this world.")
            return
        
        # Get all document cases referenced in the world's cases array
        document_ids = world.cases
        documents = Document.query.filter(
            Document.id.in_(document_ids),
            Document.document_type == 'case_study'
        ).all()
        
        # Filter for NSPE cases
        nspe_documents = []
        for document in documents:
            # Check if it's an NSPE case by looking at the title or metadata
            if document.title.startswith("NSPE Case") or (document.doc_metadata and "NSPE" in str(document.doc_metadata)):
                nspe_documents.append(document)
        
        print(f"Found {len(nspe_documents)} NSPE ethics cases:")
        print("=" * 50)
        
        # List each case with some details
        for i, document in enumerate(nspe_documents):
            # Count triples associated with this document
            triple_count = EntityTriple.query.filter_by(
                entity_type='document',
                entity_id=document.id
            ).count()
            
            # Extract metadata if available
            metadata = document.doc_metadata or {}
            
            # Get case number if available
            case_number = metadata.get('case_number', '')
            if not case_number and document.title.startswith("NSPE Case"):
                case_number = document.title.replace("NSPE Case", "").strip()
            
            # Get the principles
            principles = metadata.get('principles', [])
            principles_str = ", ".join(principles) if principles else "N/A"
            
            # Get the outcome
            outcome = metadata.get('outcome', 'Unknown')
            
            # Print the case details
            print(f"{i+1}. {document.title} (ID: {document.id})")
            print(f"   Description: {document.content[:100]}..." if document.content and len(document.content) > 100 else f"   Description: {document.content}")
            print(f"   Principles: {principles_str}")
            print(f"   Outcome: {outcome}")
            print(f"   Triple Count: {triple_count}")
            print(f"   Source: {document.source}")
            print()
        
        print(f"Successfully found {len(nspe_documents)} NSPE ethics cases associated with the world.")
        
        # Now check if there are still any scenarios with NSPE case names
        from app.models.scenario import Scenario
        nspe_scenarios = Scenario.query.filter(
            Scenario.name.like("NSPE Case%")
        ).all()
        
        if nspe_scenarios:
            print("\nWARNING: Found incorrectly created NSPE scenarios still in the database:")
            for scenario in nspe_scenarios:
                # Count triples associated with this scenario
                triple_count = EntityTriple.query.filter_by(scenario_id=scenario.id).count()
                print(f"  - ID {scenario.id}: {scenario.name} (with {triple_count} triples)")
            print("\nRun cleanup_nspe_scenarios.py to remove these scenarios.")
        
        return nspe_documents

if __name__ == "__main__":
    list_nspe_world_cases()
