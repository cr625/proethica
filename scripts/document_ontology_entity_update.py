#!/usr/bin/env python3
"""
Script to document the ontology entity extraction improvements by:
1. Checking the ontology entities from the database directly
2. Showing examples of how the data is used in the app
3. Providing guidelines for future ontology development
"""
import os
import sys
import json
import textwrap
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app import db, app
    from app.models.ontology import Ontology
    from app.services.ontology_entity_service import OntologyEntityService
except ImportError:
    print("Failed to import required modules. Make sure you're running this from the project root.")
    sys.exit(1)

def check_ontology_entities(ontology_id=1):
    """
    Check the entity extraction for a specific ontology using our direct approach.
    
    Args:
        ontology_id: ID of the ontology to check
    """
    print("\n" + "=" * 80)
    print(f"ONTOLOGY ENTITY EXTRACTION CHECK (ID: {ontology_id})")
    print("=" * 80)
    
    try:
        # Set up application context
        with app.app_context():
            # Get the ontology from the database
            ontology = Ontology.query.get(ontology_id)
            if not ontology:
                print(f"⚠️ Error: Ontology with ID {ontology_id} not found")
                return False
            
        print(f"📚 Ontology: {ontology.name} (domain_id: {ontology.domain_id})")
        
            # Create a world-like object with the required ontology_id field
            class DummyWorld:
                def __init__(self, ont_id):
                    self.ontology_id = ont_id
            
            dummy_world = DummyWorld(ontology_id)
            
            # Get entities using our direct entity service
            entity_service = OntologyEntityService.get_instance()
            entities = entity_service.get_entities_for_world(dummy_world)
        
        # Display entity counts
        if 'entities' in entities:
            print("\n📊 Entity Counts:")
            for entity_type, entity_list in entities['entities'].items():
                print(f"  - {entity_type.capitalize()}: {len(entity_list)}")
        else:
            print("⚠️ No 'entities' key in the response")
            return False
            
        # Display some examples of each entity type
        print("\n📝 Entity Examples:")
        for entity_type, entity_list in entities['entities'].items():
            print(f"\n  {entity_type.upper()}:")
            
            # Display up to 3 examples of each type
            for i, entity in enumerate(entity_list[:3]):
                print(f"    {i+1}. {entity.get('label', 'Unknown')}")
                if 'description' in entity and entity['description']:
                    wrapped_desc = textwrap.fill(
                        entity['description'], 
                        width=75, 
                        initial_indent="       ", 
                        subsequent_indent="       "
                    )
                    print(wrapped_desc)
                    
                # For roles, show capabilities
                if entity_type == 'roles' and 'capabilities' in entity and entity['capabilities']:
                    print("       Capabilities:")
                    for capability in entity['capabilities']:
                        print(f"        - {capability.get('label', 'Unknown')}")
                        
            # If there are more entities, show the count
            if len(entity_list) > 3:
                print(f"    ... and {len(entity_list) - 3} more")
                
        print("\n✅ Entity extraction completed successfully")
        return True
        
    except Exception as e:
        import traceback
        print(f"⚠️ Error checking ontology entities: {str(e)}")
        traceback.print_exc()
        return False
        
def document_improved_system():
    """
    Document the improvements made to the ontology entity extraction system.
    """
    print("\n" + "=" * 80)
    print("ONTOLOGY ENTITY EXTRACTION SYSTEM IMPROVEMENTS")
    print("=" * 80)
    
    print("""
📌 IMPROVEMENTS MADE:

1. Direct Database Access:
   - Created OntologyEntityService to extract entities directly from the database
   - Eliminated HTTP dependency on MCP server for entity retrieval
   - Improved reliability by removing network communication layer

2. Enhanced Entity Parsing:
   - Implemented intelligent namespace detection across multiple ontology formats
   - Added support for entities with both EntityType and specific type declarations
   - Properly extracts entity relationships like Role-Capability connections

3. Performance Optimization:
   - Added caching to improve performance for frequently accessed ontologies
   - Reduced processing overhead by eliminating serialization/deserialization

4. Unified Entity Access:
   - Both world detail page and ontology editor now use the same direct extraction
   - Ensured consistency between entity display in different parts of the application

5. Error Handling:
   - Added detailed logging for better debugging and troubleshooting
   - Implemented graceful failure modes with helpful error messages


📋 GUIDELINES FOR ONTOLOGY DEVELOPMENT:

When creating or modifying ontologies, follow these guidelines for best results:

1. Entity Definition:
   - Always define labels using rdfs:label
   - Include descriptions with rdfs:comment
   - Properly type entities with both general and specific types
     e.g., both <EntityType> and <Role> for role entities

2. Namespace Usage:
   - Use consistent namespaces for related entities
   - Prefer standard namespaces like:
     * http://proethica.org/ontology/engineering-ethics#
     * http://proethica.org/ontology/intermediate#

3. Entity Relationships:
   - Define role capabilities using hasCapability properties
   - Use standard relationship properties when available

4. Validation:
   - Always validate ontology syntax before saving
   - Check entity extraction results after making changes
""")

    print("\n" + "=" * 80 + "\n")
        
if __name__ == "__main__":
    document_improved_system()
    
    # Check the default ontology (ID 1)
    check_ontology_entities(1)
    
    # Check if there's an argument for a different ontology ID
    if len(sys.argv) > 1:
        try:
            other_id = int(sys.argv[1])
            if other_id != 1:
                check_ontology_entities(other_id)
        except ValueError:
            print(f"⚠️ Invalid ontology ID: {sys.argv[1]}")
            
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    
    print("""
The ontology entity extraction system has been significantly improved by:

1. Moving from HTTP-based MCP server calls to direct database access
2. Implementing intelligent entity extraction with proper namespace handling
3. Adding caching for improved performance
4. Ensuring consistency between the world detail page and ontology editor

These improvements make the system more reliable, faster, and easier to debug.
Entities from ontologies are now extracted directly from the database with
minimal dependencies, reducing the chance of failures.

To see how the updated system works:
1. View a world's details page at: http://localhost:3333/worlds/1
2. Check the ontology editor's entity view at: http://localhost:3333/ontology-editor/?ontology_id=1&view=entities
""")
