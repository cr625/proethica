#!/usr/bin/env python3
"""
Script to debug ontology ID type conversions.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology

def test_ontology_id_types():
    """Test fetching ontologies with different ID types."""
    app = create_app()
    
    with app.app_context():
        print("Testing different ontology ID types:")
        
        # Test with integer ID
        print("\n1. Using integer ID (1):")
        ontology_int = Ontology.query.get(1)
        if ontology_int:
            print(f"  Found ontology: ID={ontology_int.id}, Name={ontology_int.name}")
        else:
            print("  No ontology found")
        
        # Test with string ID
        print("\n2. Using string ID ('1'):")
        ontology_str = Ontology.query.get('1')
        if ontology_str:
            print(f"  Found ontology: ID={ontology_str.id}, Name={ontology_str.name}")
        else:
            print("  No ontology found")
        
        # Test with explicit type conversion
        print("\n3. Using explicit int conversion (int('1')):")
        ontology_conv = Ontology.query.get(int('1'))
        if ontology_conv:
            print(f"  Found ontology: ID={ontology_conv.id}, Name={ontology_conv.name}")
        else:
            print("  No ontology found")
        
        # Check ontology ID data type
        print("\n4. Checking Ontology ID column type:")
        ontology = Ontology.query.first()
        if ontology:
            print(f"  Ontology ID: {ontology.id} (Python type: {type(ontology.id).__name__})")
            print(f"  SQLAlchemy declared type: {Ontology.__table__.c.id.type}")
        else:
            print("  No ontologies available to check")

if __name__ == "__main__":
    test_ontology_id_types()
