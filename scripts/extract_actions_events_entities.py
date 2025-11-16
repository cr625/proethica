#!/usr/bin/env python3
"""
Extract Action and Event Entities from Updated TTL

This script triggers entity extraction from the updated proethica-intermediate.ttl
file to populate the ontology_entities table with our new Action and Event subclasses.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

# Add OntServe to path
ontserve_root = project_root.parent / 'OntServe'
sys.path.insert(0, str(ontserve_root))

def extract_entities_from_ontology():
    """Extract entities from the updated proethica-intermediate ontology using API."""
    print("=== Extracting Action/Event Entities from Updated TTL ===")
    
    try:
        import requests
        
        # Check if OntServe web interface is running on port 5003
        print("Checking OntServe web interface...")
        try:
            health_response = requests.get('http://localhost:5003/health', timeout=5)
            if health_response.status_code == 200:
                print("✅ OntServe web interface is running")
            else:
                print("❌ OntServe web interface not responding properly")
                return False
        except requests.exceptions.ConnectionError:
            print("❌ OntServe web interface not running on port 5003")
            print("Please start it with: cd /home/chris/onto/OntServe && python web/app.py")
            return False
        
        # Trigger entity extraction via API
        print("Triggering entity extraction for proethica-intermediate...")
        
        api_url = 'http://localhost:5003/editor/api/extract-entities/proethica-intermediate'
        
        response = requests.post(api_url, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ Entity extraction triggered successfully!")
                print(f"Extraction result: {result}")
            else:
                print(f"❌ Entity extraction failed: {result.get('error', 'Unknown error')}")
                return False
        else:
            print(f"❌ API call failed: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        # Wait a moment for extraction to complete
        import time
        print("Waiting for extraction to complete...")
        time.sleep(3)
        
        # Now check database directly for Action/Event entities
        print("\nChecking database for Action/Event entities...")
        
        # Set up database environment for direct query
        os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5432/ontserve'
        os.environ['FLASK_CONFIG'] = 'development'
        
        from web.models import db, Ontology, OntologyVersion, OntologyEntity
        from flask import Flask
        from web.config import Config
        
        # Create minimal Flask app for database access
        app = Flask(__name__)
        app.config.from_object(Config)
        
        # Initialize database
        from web.models import init_db
        init_db(app)
        
        with app.app_context():
            # Check Action entities
            action_query = """
                SELECT COUNT(*) as count, array_agg(DISTINCT label ORDER BY label) as labels
                FROM ontology_entities e
                JOIN ontologies o ON e.ontology_id = o.id
                WHERE o.name = 'proethica-intermediate'
                AND e.entity_type = 'class'
                AND (e.label ILIKE '%Action%' OR e.uri ILIKE '%Action%')
            """
            
            event_query = """
                SELECT COUNT(*) as count, array_agg(DISTINCT label ORDER BY label) as labels  
                FROM ontology_entities e
                JOIN ontologies o ON e.ontology_id = o.id
                WHERE o.name = 'proethica-intermediate'
                AND e.entity_type = 'class'
                AND (e.label ILIKE '%Event%' OR e.uri ILIKE '%Event%')
            """
            
            action_result = db.session.execute(action_query).fetchone()
            event_result = db.session.execute(event_query).fetchone()
            
            print(f"Action entities in database: {action_result[0]}")
            if action_result[1]:
                print("Action labels:")
                for label in action_result[1][:15]:  # Show first 15
                    print(f"  - {label}")
            
            print(f"\nEvent entities in database: {event_result[0]}")
            if event_result[1]:
                print("Event labels:")
                for label in event_result[1][:15]:  # Show first 15
                    print(f"  - {label}")
            
            # Success if we have more than just the base classes
            total_entities = action_result[0] + event_result[0]
            if total_entities > 2:  # More than just base Action and Event classes
                print(f"\n✅ Found {total_entities} Action/Event entities!")
                return True
            else:
                print(f"\n⚠️ Only found {total_entities} entities (expected more subclasses)")
                return False
            
    except Exception as e:
        print(f"❌ Entity extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = extract_entities_from_ontology()
    
    if success:
        print("\n✅ Entity extraction complete!")
        print("Now test MCP integration again:")
        print("python scripts/test_actions_events_mcp.py")
    else:
        print("\n❌ Entity extraction failed!")
    
    sys.exit(0 if success else 1)
