#!/usr/bin/env python3
"""
Import Professional Ethics Codes Ontologies into OntServe
"""

import os
import sys
import requests
import json
from pathlib import Path

# Set environment variables
os.environ.setdefault('ONTSERVE_DB_URL', 'postgresql://ontserve_user:ontserve_development_password@localhost:5432/ontserve')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def import_ontology_via_api(ontology_file: str, name: str, description: str) -> bool:
    """Import ontology via OntServe API."""
    try:
        # Read the ontology file
        with open(ontology_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Prepare API request
        url = 'http://localhost:5003/api/ontologies'
        
        # First, try to import via file upload simulation
        data = {
            'name': name,
            'description': description,
            'content': content,
            'format': 'turtle'
        }
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code in [200, 201]:
            print(f"✅ Successfully imported {name}")
            return True
        else:
            print(f"❌ Failed to import {name}: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error importing {name}: {e}")
        return False

def import_ontology_via_direct_db(ontology_file: str, name: str, description: str) -> bool:
    """Import ontology directly via database using OntServe integration."""
    try:
        # Read the ontology file
        with open(ontology_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Connect to OntServe database
        import psycopg2
        from datetime import datetime
        
        conn = psycopg2.connect(os.environ['ONTSERVE_DB_URL'])
        cur = conn.cursor()
        
        # Check if ontology already exists
        cur.execute("SELECT id FROM ontologies WHERE name = %s", (name,))
        existing = cur.fetchone()
        
        if existing:
            print(f"⚠️  Ontology {name} already exists, updating...")
            ontology_id = existing[0]
            
            # Update existing ontology version
            cur.execute("""
                UPDATE ontology_versions 
                SET content = %s
                WHERE ontology_id = %s AND is_current = true
            """, (content, ontology_id))
            
        else:
            # Create new ontology
            cur.execute("""
                INSERT INTO ontologies (name, base_uri, description, created_at)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (
                name,
                f"http://proethica.org/ontology/{name.lower().replace(' ', '_').replace('-', '_')}#",
                description,
                datetime.utcnow()
            ))
            ontology_id = cur.fetchone()[0]
            
            # Create initial version
            cur.execute("""
                INSERT INTO ontology_versions (
                    ontology_id, version_number, version_tag, content, 
                    is_current, is_draft, workflow_status, 
                    created_by, change_summary, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                ontology_id, 1, 'initial', content,
                True, False, 'published',
                'import_script', f'Initial import of {name}',
                datetime.utcnow()
            ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ Successfully imported {name} into database")
        return True
        
    except Exception as e:
        print(f"❌ Error importing {name} via database: {e}")
        return False

def main():
    """Import all professional ethics ontologies."""
    print("🚀 Importing Professional Ethics Codes into OntServe")
    print("=" * 60)
    
    # Define ontologies to import
    ontologies = [
        {
            'file': 'ontologies/asce_code_of_ethics.ttl',
            'name': 'ASCE Code of Ethics',
            'description': 'American Society of Civil Engineers Code of Ethics for civil engineers'
        },
        {
            'file': 'ontologies/ieee_code_of_ethics.ttl', 
            'name': 'IEEE Code of Ethics',
            'description': 'Institute of Electrical and Electronics Engineers Code of Ethics'
        },
        {
            'file': 'ontologies/asme_code_of_ethics.ttl',
            'name': 'ASME Code of Ethics', 
            'description': 'American Society of Mechanical Engineers Code of Ethics'
        }
    ]
    
    success_count = 0
    total_count = len(ontologies)
    
    for ont in ontologies:
        print(f"\n📋 Importing {ont['name']}...")
        
        # Check if file exists
        file_path = Path(__file__).parent.parent / ont['file']
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            continue
        
        # Try API import first, fallback to direct database
        success = import_ontology_via_api(str(file_path), ont['name'], ont['description'])
        
        if not success:
            print(f"   Trying direct database import...")
            success = import_ontology_via_direct_db(str(file_path), ont['name'], ont['description'])
        
        if success:
            success_count += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Import Summary: {success_count}/{total_count} ontologies imported successfully")
    
    if success_count == total_count:
        print("🎉 All ontologies imported successfully!")
        print("\n🔗 View imported ontologies at: http://localhost:5003/ontologies")
        
        # Show integration status
        print("\n📈 Integration Status:")
        print("✅ Ethics codes imported into OntServe (visible in web interface)")
        print("✅ Professional engineering standards now available")
        print("✅ Ready for enrichment and annotation enhancement")
        
    else:
        print(f"⚠️  {total_count - success_count} ontologies failed to import")
        print("Check the error messages above for details")

if __name__ == "__main__":
    main()