#!/usr/bin/env python3
"""
Script to verify that the ontology version loading fix works properly
by checking API endpoints directly.
"""
import os
import sys
import requests
from pprint import pprint

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion

def verify_version_endpoint(ontology_id, version_number):
    """
    Verify that the API endpoint for loading a specific version works.
    
    Args:
        ontology_id (int): The ID of the ontology
        version_number (int): The version number to check
    """
    print(f"Verifying API endpoint for ontology {ontology_id}, version {version_number}...")
    
    # Check if the server is running
    base_url = "http://localhost:3333"
    try:
        response = requests.get(f"{base_url}/ontology-editor/api", timeout=2)
        if response.status_code != 200:
            print(f"Warning: Server returned status code {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the server. Is it running?")
        print(f"Please start the server and then try to access: {base_url}/ontology-editor/")
        return False
    except requests.exceptions.Timeout:
        print("Error: Connection to server timed out. Is the server running?")
        return False
    
    # Now try to access the specific version endpoint
    url = f"{base_url}/ontology-editor/api/versions/{ontology_id}/{version_number}"
    print(f"Testing URL: {url}")
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"✅ Success! Endpoint returned status code {response.status_code}")
            data = response.json()
            print(f"Version details:")
            print(f"  - ID: {data.get('id')}")
            print(f"  - Ontology ID: {data.get('ontology_id')}")
            print(f"  - Version Number: {data.get('version_number')}")
            print(f"  - Created at: {data.get('created_at')}")
            print(f"  - Commit message: {data.get('commit_message')}")
            print(f"  - Content length: {len(data.get('content', ''))} characters")
            
            # Verify the version data matches what we expect
            if data.get('ontology_id') != ontology_id or data.get('version_number') != version_number:
                print(f"❌ Warning: Version data mismatch!")
                print(f"  Expected: ontology_id={ontology_id}, version_number={version_number}")
                print(f"  Received: ontology_id={data.get('ontology_id')}, version_number={data.get('version_number')}")
            else:
                print(f"✅ Version data matches expected values")
                
            return True
        else:
            print(f"❌ Error: Endpoint returned status code {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def verify_database_versions(ontology_id):
    """
    Verify versions in the database for the specified ontology.
    
    Args:
        ontology_id (int): The ID of the ontology to check
    """
    print(f"\nVerifying database versions for ontology {ontology_id}...")
    
    app = create_app()
    with app.app_context():
        # Check if the ontology exists
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            print(f"❌ Error: Ontology {ontology_id} not found in database")
            return False
        
        print(f"Found ontology: {ontology.name} (domain_id: {ontology.domain_id})")
        
        # Get all versions
        versions = OntologyVersion.query.filter_by(ontology_id=ontology_id).order_by(OntologyVersion.version_number).all()
        if not versions:
            print(f"❌ No versions found for ontology {ontology_id}")
            return False
        
        print(f"Found {len(versions)} versions:")
        for version in versions:
            print(f"  - Version {version.version_number} (ID: {version.id}, Created: {version.created_at})")
            if version.commit_message:
                print(f"    Commit: {version.commit_message}")
        
        return versions

def run_verification():
    """
    Run comprehensive verification of the version loading fix.
    """
    ontology_id = 1  # Engineering Ethics ontology
    
    # Step 1: Check database versions
    versions = verify_database_versions(ontology_id)
    if not versions:
        return False
    
    # Step 2: Verify API endpoints for a few versions
    print("\nVerifying API endpoints for selected versions...")
    
    # Try the first, middle, and last version for good coverage
    test_versions = [
        versions[0].version_number,                     # First version
        versions[len(versions)//2].version_number,      # Middle version
        versions[-1].version_number                     # Last version
    ]
    
    success = True
    for version_number in test_versions:
        print("\n" + "="*50)
        version_success = verify_version_endpoint(ontology_id, version_number)
        success = success and version_success
    
    # Final summary
    print("\n" + "="*50)
    if success:
        print("\n✅ All version endpoints verified successfully!")
        print("The fix appears to be working correctly.")
        print("\nFinal verification steps:")
        print("1. Open the ontology editor in your browser: http://localhost:3333/ontology-editor/")
        print("2. Load the Engineering Ethics ontology (ID 1)")
        print("3. Click on different version numbers in the Versions column")
        print("4. Verify that each version loads correctly without errors")
        print("5. Check the browser console (F12) to confirm no JavaScript errors")
    else:
        print("\n❌ Some verification tests failed. Please check the errors above.")
    
    return success

if __name__ == "__main__":
    print("Verifying ontology version loading fix...")
    run_verification()
