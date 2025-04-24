#!/usr/bin/env python3
"""
Script to debug the ontology editor routes.
"""

import sys
import os
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from flask import url_for

def debug_ontology_routes():
    """Debug ontology editor routes."""
    app = create_app()
    
    with app.test_request_context():
        rules = []
        for rule in app.url_map.iter_rules():
            methods = ', '.join([method for method in rule.methods if method not in ('HEAD', 'OPTIONS')])
            endpoint = rule.endpoint
            route = {
                'endpoint': endpoint,
                'methods': methods,
                'url': str(rule),
                'defaults': rule.defaults
            }
            rules.append(route)
        
        # Sort rules by URL
        rules = sorted(rules, key=lambda x: x['url'])
        
        # Filter for ontology routes
        ontology_rules = [rule for rule in rules if 'ontology' in rule['url'].lower()]
        
        # Print ontology editor routes
        print("Ontology Editor Routes:")
        for rule in ontology_rules:
            print(f"URL: {rule['url']}")
            print(f"  Endpoint: {rule['endpoint']}")
            print(f"  Methods: {rule['methods']}")
            print(f"  Defaults: {rule['defaults']}")
            print()

if __name__ == "__main__":
    debug_ontology_routes()
