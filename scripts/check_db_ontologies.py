#!/usr/bin/env python3
"""
Simple script to check what ontologies are stored in the database.
"""
import os
import sys
import json
from datetime import datetime

# Add the project directory to the Python path
sys.path.insert(0, '/home/chris/onto/proethica')

def check_database_ontologies():
    """Check and display ontologies from the database."""
    
    # Initialize the Flask app with database models
    from app import create_app
    from app.models.ontology import Ontology
    from app.models.ontology_import import OntologyImport
    
    print("=" * 60)
    print("DATABASE ONTOLOGY CHECKER")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Override database configuration to use the environment-specific config
    os.environ['DATABASE_URL'] = 'postgresql://postgres:postgres@localhost:5433/ai_ethical_dm'
    os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:postgres@localhost:5433/ai_ethical_dm'
    
    # Use enhanced configuration
    app = create_app(config_module='config')
    
    with app.app_context():
        try:
            # Query all ontologies
            ontologies = Ontology.query.all()
            
            print(f"Found {len(ontologies)} ontologies in database:")
            print("-" * 40)
            
            for i, ontology in enumerate(ontologies, 1):
                print(f"{i}. {ontology.name}")
                print(f"   ID: {ontology.id}")
                print(f"   Domain ID: {ontology.domain_id}")
                print(f"   Description: {ontology.description or 'None'}")
                print(f"   Base URI: {ontology.base_uri or 'None'}")
                print(f"   Is Base: {ontology.is_base}")
                print(f"   Is Editable: {ontology.is_editable}")
                print(f"   Created: {ontology.created_at}")
                print(f"   Updated: {ontology.updated_at}")
                
                # Check content length
                if ontology.content:
                    content_lines = ontology.content.split('\n')
                    print(f"   Content: {len(content_lines)} lines")
                    
                    # Show first few lines to identify the ontology
                    print("   First few lines:")
                    for line in content_lines[:5]:
                        if line.strip():
                            print(f"      {line.strip()}")
                else:
                    print("   Content: None")
                
                # Check imports
                imports = ontology.get_imported_ontologies()
                if imports:
                    print(f"   Imports: {', '.join([imp.name for imp in imports])}")
                else:
                    print("   Imports: None")
                
                # Check associated worlds
                if ontology.worlds:
                    world_names = [world.name for world in ontology.worlds]
                    print(f"   Associated Worlds: {', '.join(world_names)}")
                else:
                    print("   Associated Worlds: None")
                
                print()
            
            # Check ontology imports table
            print("ONTOLOGY IMPORTS:")
            print("-" * 40)
            imports = OntologyImport.query.all()
            if imports:
                for imp in imports:
                    print(f"- {imp.importing_ontology.name} imports {imp.imported_ontology.name}")
            else:
                print("No ontology imports found")
            
            print()
            
        except Exception as e:
            print(f"Error querying database: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    check_database_ontologies()