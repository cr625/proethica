#!/usr/bin/env python3
"""
Script to check ontologies and versions in the database.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion

def check_ontologies():
    """Check ontologies and versions in the database."""
    app = create_app()
    
    with app.app_context():
        # Check ontologies
        print('Ontologies in DB:')
        ontologies = Ontology.query.all()
        
        for o in ontologies:
            print(f'  ID={o.id}, Name={o.name}, Domain={o.domain_id}')
            print(f'    Content Length: {len(o.content) if o.content else 0} characters')
        
        # Check versions
        print('\nVersions in DB:')
        versions = OntologyVersion.query.all()
        
        for v in versions:
            print(f'  ID={v.id}, Ontology ID={v.ontology_id}, Version={v.version_number}')
            print(f'    Message: {v.commit_message}')
            print(f'    Content Length: {len(v.content) if v.content else 0} characters')

if __name__ == "__main__":
    check_ontologies()
