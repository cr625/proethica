#!/usr/bin/env python3
from app import create_app
from app.models.ontology import Ontology

app = create_app()
with app.app_context():
    # Check if ontology with ID 1 exists
    ontology_by_id = Ontology.query.get(1)
    if ontology_by_id:
        print(f"Ontology ID 1: {ontology_by_id.name}")
        print(f"Domain ID: {ontology_by_id.domain_id}")
        print(f"Content length: {len(ontology_by_id.content) if ontology_by_id.content else 'None'}")
    else:
        print("Ontology with ID 1 not found")
    
    # Check if ontology with domain_id 'engineering-ethics-nspe-extended' exists
    ontology_by_domain = Ontology.query.filter_by(domain_id='engineering-ethics-nspe-extended').first()
    if ontology_by_domain:
        print(f"\nFound ontology by domain_id: {ontology_by_domain.name}")
        print(f"Ontology ID: {ontology_by_domain.id}")
        print(f"Content length: {len(ontology_by_domain.content) if ontology_by_domain.content else 'None'}")
    else:
        print("\nOntology with domain_id 'engineering-ethics-nspe-extended' not found")
