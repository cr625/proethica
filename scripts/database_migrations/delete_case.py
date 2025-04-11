#!/usr/bin/env python3
"""
Script to delete a case by ID.
"""

import sys
from app import create_app, db
from app.models.document import Document
from app.models.entity_triple import EntityTriple

def delete_case(case_id):
    """
    Delete a case (document) by ID and any associated entity triples.
    
    Args:
        case_id: ID of the case/document to delete
    """
    app = create_app()
    with app.app_context():
        # Find the document
        document = Document.query.get(case_id)
        
        if not document:
            print(f"Case with ID {case_id} not found.")
            return False
        
        print(f"Found case: {document.title}")
        
        # Delete associated entity triples first
        triples = EntityTriple.query.filter_by(
            entity_type='document',
            entity_id=document.id
        ).all()
        
        if triples:
            print(f"Deleting {len(triples)} associated triples...")
            for triple in triples:
                db.session.delete(triple)
        
        # Now delete the document
        print(f"Deleting document ID {document.id}: {document.title}")
        db.session.delete(document)
        
        # Commit changes
        db.session.commit()
        print("Case deleted successfully.")
        return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python delete_case.py <case_id>")
        sys.exit(1)
    
    try:
        case_id = int(sys.argv[1])
    except ValueError:
        print("Error: case_id must be an integer")
        sys.exit(1)
    
    success = delete_case(case_id)
    if not success:
        sys.exit(1)
