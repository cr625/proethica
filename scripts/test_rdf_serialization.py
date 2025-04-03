#!/usr/bin/env python
"""
Test script for the RDFSerializationService.
This script demonstrates how to:
1. Export entity triples to various RDF formats
2. Import RDF data back into the entity_triples table
"""

import os
import sys
import json
import tempfile
from datetime import datetime
from pprint import pprint

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.character import Character
from app.models.entity_triple import EntityTriple
from app.services.entity_triple_service import EntityTripleService
from app.services.rdf_serialization_service import RDFSerializationService

def test_export_to_turtle():
    """Test exporting entity triples to Turtle format."""
    print("\n=== Testing Export to Turtle ===")
    
    # Create RDFSerializationService
    serialization_service = RDFSerializationService()
    
    # Get a character to export
    character = Character.query.first()
    if not character:
        print("No characters found for testing")
        return False
    
    print(f"Exporting triples for character: {character.name} (ID: {character.id})")
    
    # Create output directory if it doesn't exist
    os.makedirs('exports', exist_ok=True)
    
    # Export to Turtle
    output_path = os.path.join('exports', f'character_{character.id}.ttl')
    turtle_data = serialization_service.export_to_turtle(
        output_path=output_path,
        entity_type='character',
        entity_id=character.id
    )
    
    print(f"Exported Turtle data to: {output_path}")
    print(f"First 500 characters of Turtle data:\n{turtle_data[:500]}...")
    
    return True

def test_export_to_rdfxml():
    """Test exporting entity triples to RDF/XML format."""
    print("\n=== Testing Export to RDF/XML ===")
    
    # Create RDFSerializationService
    serialization_service = RDFSerializationService()
    
    # Export all triples for a scenario
    # First, find a scenario with triples
    scenario_query = """
    SELECT DISTINCT scenario_id 
    FROM entity_triples 
    WHERE scenario_id IS NOT NULL
    LIMIT 1;
    """
    
    from sqlalchemy import text
    scenario_result = db.session.execute(text(scenario_query)).fetchone()
    
    if not scenario_result:
        print("No scenarios found with triples")
        return False
    
    scenario_id = scenario_result[0]
    print(f"Exporting triples for scenario ID: {scenario_id}")
    
    # Create output directory if it doesn't exist
    os.makedirs('exports', exist_ok=True)
    
    # Export to RDF/XML
    output_path = os.path.join('exports', f'scenario_{scenario_id}.rdf')
    rdfxml_data = serialization_service.export_to_rdfxml(
        output_path=output_path,
        scenario_id=scenario_id
    )
    
    print(f"Exported RDF/XML data to: {output_path}")
    print(f"First 500 characters of RDF/XML data:\n{rdfxml_data[:500]}...")
    
    return True

def test_export_to_jsonld():
    """Test exporting entity triples to JSON-LD format."""
    print("\n=== Testing Export to JSON-LD ===")
    
    # Create RDFSerializationService
    serialization_service = RDFSerializationService()
    
    # Export all decision triples
    print("Exporting triples for all decisions")
    
    # Create output directory if it doesn't exist
    os.makedirs('exports', exist_ok=True)
    
    # Export to JSON-LD
    output_path = os.path.join('exports', 'decisions.jsonld')
    jsonld_data = serialization_service.export_to_jsonld(
        output_path=output_path,
        entity_type='action',
        predicate=str(serialization_service.namespaces['rdf']['type']),
        object_uri=str(serialization_service.namespaces['proethica']['Decision']),
        is_literal=False
    )
    
    print(f"Exported JSON-LD data to: {output_path}")
    print(f"First 500 characters of JSON-LD data:\n{jsonld_data[:500]}...")
    
    return True

def test_import_from_turtle():
    """Test importing Turtle data into entity triples."""
    print("\n=== Testing Import from Turtle ===")
    
    # Create a sample Turtle file
    sample_turtle = """
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
    @prefix proethica: <http://proethica.org/ontology/> .
    @prefix time: <http://www.w3.org/2006/time#> .
    
    <http://proethica.org/entity/test_import_01>
        rdf:type proethica:TestEntity ;
        rdfs:label "Test Import Entity" ;
        proethica:hasValue "42"^^xsd:integer ;
        proethica:hasDescription "This is a test entity created through RDF import" .
    
    <http://proethica.org/entity/test_import_02>
        rdf:type proethica:TestEntity ;
        rdfs:label "Another Test Entity" ;
        proethica:hasRelationship <http://proethica.org/entity/test_import_01> .
    """
    
    # Create a temporary file for the Turtle data
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.ttl', delete=False) as temp:
        temp.write(sample_turtle)
        temp_path = temp.name
    
    print(f"Created sample Turtle file: {temp_path}")
    
    # Create RDFSerializationService
    serialization_service = RDFSerializationService()
    
    # Import the Turtle data
    print("Importing Turtle data...")
    triples = serialization_service.import_from_rdf(
        temp_path,
        format='turtle',
        entity_type='test',
        entity_id=9999,  # Use a dummy ID for testing
        scenario_id=None
    )
    
    print(f"Imported {len(triples)} triples")
    
    # Display the imported triples
    for i, triple in enumerate(triples[:5]):
        print(f"  {i+1}. {triple.subject} {triple.predicate} {triple.object_literal or triple.object_uri}")
    
    # Clean up
    os.unlink(temp_path)
    
    return True

def round_trip_test():
    """Test a complete round trip: export to RDF and import back."""
    print("\n=== Testing Round-Trip Export and Import ===")
    
    # Create RDFSerializationService
    serialization_service = RDFSerializationService()
    
    # Get a character to export
    character = Character.query.first()
    if not character:
        print("No characters found for testing")
        return False
    
    print(f"Exporting triples for character: {character.name} (ID: {character.id})")
    
    # Export to Turtle
    turtle_data = serialization_service.export_to_turtle(
        entity_type='character',
        entity_id=character.id
    )
    
    print(f"Exported {len(turtle_data)} bytes of Turtle data")
    
    # Count existing triples
    existing_count = db.session.query(EntityTriple).filter_by(
        entity_type='test',
        entity_id=8888
    ).count()
    
    # Delete any existing test triples
    if existing_count > 0:
        db.session.query(EntityTriple).filter_by(
            entity_type='test',
            entity_id=8888
        ).delete()
        db.session.commit()
    
    # Import the Turtle data with a different entity type and ID
    print("Importing Turtle data...")
    triples = serialization_service.import_from_rdf(
        turtle_data,
        format='turtle',
        entity_type='test',
        entity_id=8888,  # Use a different ID for testing
        scenario_id=character.scenario_id
    )
    
    print(f"Imported {len(triples)} triples")
    
    # Check if the import worked
    imported_count = db.session.query(EntityTriple).filter_by(
        entity_type='test',
        entity_id=8888
    ).count()
    
    print(f"Found {imported_count} imported triples (expected {len(triples)})")
    
    return imported_count == len(triples)

def main():
    """Run all tests."""
    app = create_app()
    
    with app.app_context():
        print("\n=== RDFSerializationService Tests ===")
        
        # Run tests
        turtle_test = test_export_to_turtle()
        rdfxml_test = test_export_to_rdfxml()
        jsonld_test = test_export_to_jsonld()
        import_test = test_import_from_turtle()
        round_trip_test_result = round_trip_test()
        
        # Print summary
        print("\n=== Test Results ===")
        print(f"Export to Turtle test: {'✓ Passed' if turtle_test else '✗ Failed'}")
        print(f"Export to RDF/XML test: {'✓ Passed' if rdfxml_test else '✗ Failed'}")
        print(f"Export to JSON-LD test: {'✓ Passed' if jsonld_test else '✗ Failed'}")
        print(f"Import from Turtle test: {'✓ Passed' if import_test else '✗ Failed'}")
        print(f"Round-trip test: {'✓ Passed' if round_trip_test_result else '✗ Failed'}")
        
        if turtle_test and rdfxml_test and jsonld_test and import_test and round_trip_test_result:
            print("\n✓ All tests passed!")
        else:
            print("\n⚠ Some tests failed")
        
        print("\nExported files are available in the 'exports' directory.")

if __name__ == "__main__":
    main()
