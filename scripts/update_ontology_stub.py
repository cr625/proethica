#!/usr/bin/env python3
"""
Script to update the archived-stub ontology entry with meaningful text.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.ontology import Ontology

def update_ontology_stub():
    """Update the archived-stub ontology with meaningful text."""
    app = create_app()
    
    with app.app_context():
        # Find the archived-stub entry
        stub_ontology = Ontology.query.filter_by(name='archived-stub').first()
        
        if stub_ontology:
            # Update with meaningful text aligned with demo paper
            stub_ontology.name = 'ProEthica Core'
            stub_ontology.description = ('Nine-component ontological framework for ethical analysis '
                                        '(Roles, Principles, Obligations, States, Resources, '
                                        'Actions, Events, Capabilities, Constraints)')
            stub_ontology.base_uri = 'http://proethica.org/ontology/core'
            
            db.session.commit()
            print(f"Updated ontology: {stub_ontology.name}")
            print(f"Description: {stub_ontology.description}")
        else:
            # If no archived-stub exists, check if there's any stub entry
            any_stub = Ontology.query.filter(
                db.or_(
                    Ontology.description.like('%stub%'),
                    Ontology.description.like('%Real ontology management%')
                )
            ).first()
            
            if any_stub:
                print(f"Found stub entry with name: {any_stub.name}")
                any_stub.name = 'ProEthica Core'
                any_stub.description = ('Nine-component ontological framework for ethical analysis '
                                       '(Roles, Principles, Obligations, States, Resources, '
                                       'Actions, Events, Capabilities, Constraints)')
                any_stub.base_uri = 'http://proethica.org/ontology/core'
                
                db.session.commit()
                print(f"Updated ontology: {any_stub.name}")
                print(f"Description: {any_stub.description}")
            else:
                print("No stub ontology entries found.")
                
                # List all ontologies to see what's there
                all_ontologies = Ontology.query.all()
                if all_ontologies:
                    print("\nExisting ontologies:")
                    for ont in all_ontologies:
                        print(f"  - {ont.name}: {ont.description[:50]}...")
                else:
                    print("No ontologies found in database.")

if __name__ == '__main__':
    update_ontology_stub()
