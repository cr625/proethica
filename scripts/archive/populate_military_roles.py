#!/usr/bin/env python3
"""
Script to populate the roles table with military medical triage roles from the OWL ontology.
"""
import os
import sys
import rdflib
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS

def populate_military_roles():
    """Populate the roles table with military medical triage roles."""
    # Add the parent directory to the path so we can import the app
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    try:
        from app import create_app, db
        from app.models import World, Role
        print("Imported modules successfully")
    except Exception as e:
        print(f"Error importing modules: {e}")
        return

    app = create_app()
    with app.app_context():
        # Check if the roles table exists
        try:
            db.session.execute("SELECT 1 FROM roles LIMIT 1")
            print("Roles table exists")
        except Exception as e:
            print(f"Error checking roles table: {e}")
            print("Running database migrations...")
            try:
                from flask_migrate import upgrade
                upgrade()
                print("Migrations complete")
            except Exception as e:
                print(f"Error running migrations: {e}")
                return
        
        # Find or create the Military Medical Triage world
        world = World.query.filter_by(name="Military Medical Triage").first()
        if not world:
            print("Creating Military Medical Triage world...")
            world = World(
                name="Military Medical Triage",
                description="A world representing military medical triage scenarios",
                ontology_source="mcp/ontology/tccc.ttl"
            )
            db.session.add(world)
            db.session.commit()
            print(f"Created world with ID {world.id}")
        else:
            print(f"Found existing world with ID {world.id}")
        
        # Load the OWL ontology
        g = Graph()
        ontology_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                     "mcp/ontology/military_medical_triage_roles.ttl")
        g.parse(ontology_path, format="turtle")
        
        # Define namespaces
        MMTR = Namespace("http://proethica.org/ontology/military-medical-triage-roles#")
        
        # Query for role instances
        roles_query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX mmtr: <http://proethica.org/ontology/military-medical-triage-roles#>
        
        SELECT ?role ?label ?tier ?description
        WHERE {
            ?role rdf:type ?roleClass .
            ?roleClass rdfs:subClassOf mmtr:Role .
            ?role rdfs:label ?label .
            OPTIONAL { ?role mmtr:tier ?tier . }
            OPTIONAL { ?roleClass mmtr:description ?description . }
        }
        """
        
        # Execute the query
        results = g.query(roles_query)
        
        # Process the results
        for row in results:
            role_uri = str(row.role)
            label = str(row.label)
            tier = int(row.tier) if row.tier else None
            description = str(row.description) if row.description else None
            
            # Check if the role already exists
            existing_role = Role.query.filter_by(
                name=label,
                world_id=world.id
            ).first()
            
            if existing_role:
                print(f"Role '{label}' already exists, updating...")
                existing_role.description = description
                existing_role.tier = tier
                existing_role.ontology_uri = role_uri
            else:
                print(f"Creating role '{label}'...")
                role = Role(
                    name=label,
                    description=description,
                    world_id=world.id,
                    tier=tier,
                    ontology_uri=role_uri
                )
                db.session.add(role)
            
        # Commit the changes
        db.session.commit()
        print("Roles populated successfully!")

if __name__ == "__main__":
    populate_military_roles()
