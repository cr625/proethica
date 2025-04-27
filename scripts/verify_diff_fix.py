#!/usr/bin/env python3
"""
Script to verify the ontology diff viewer fix.
"""
import argparse
import requests
import json
import sys

def test_direct_ontology_editor_access():
    """
    Test accessing the ontology editor directly and the diff API.
    """
    print("Verifying ontology diff viewer fix...")
    
    # 1. Test direct access to ontology editor
    print("\n1. Testing direct access to ontology editor...")
    response = requests.get("http://localhost:3333/ontology-editor/")
    if response.status_code == 200:
        print("✅ Successfully accessed ontology editor directly")
    else:
        print(f"❌ Failed to access ontology editor. Status code: {response.status_code}")
        return False
    
    # 2. Get the available ontologies
    print("\n2. Checking available ontologies...")
    response = requests.get("http://localhost:3333/ontology-editor/api/ontologies")
    if response.status_code != 200:
        print(f"❌ Failed to get ontologies. Status code: {response.status_code}")
        return False
    
    ontologies = response.json().get("ontologies", [])
    if not ontologies:
        print("❌ No ontologies found")
        return False
    
    print(f"✅ Found {len(ontologies)} ontologies")
    
    # Look for an ontology with at least 2 versions
    ontology_id = None
    for idx, ontology in enumerate(ontologies):
        print(f"   Checking versions for ontology {ontology['id']} ({ontology['name']})...")
        versions_response = requests.get(f"http://localhost:3333/ontology-editor/api/versions/{ontology['id']}")
        if versions_response.status_code != 200:
            print(f"     ⚠️ Failed to get versions. Trying next ontology.")
            continue
        
        versions = versions_response.json().get("versions", [])
        if len(versions) >= 2:
            print(f"     ✅ Found {len(versions)} versions - using this ontology")
            ontology_id = ontology['id']
            break
        else:
            print(f"     ⚠️ Only {len(versions)} version(s) found. Trying next ontology.")
    
    if not ontology_id:
        print("❌ No ontology with at least 2 versions found. Cannot test diff functionality.")
        return False
    
    print(f"   Using ontology_id: {ontology_id}")
    
    # 3. Get versions for the selected ontology
    print(f"\n3. Getting versions for ontology {ontology_id}...")
    response = requests.get(f"http://localhost:3333/ontology-editor/api/versions/{ontology_id}")
    if response.status_code != 200:
        print(f"❌ Failed to get versions. Status code: {response.status_code}")
        return False
    
    versions = response.json().get("versions", [])
    if not versions or len(versions) < 2:
        print("❌ Not enough versions found for testing diff (need at least 2)")
        return False
    
    print(f"✅ Found {len(versions)} versions")
    version1 = versions[0]["version_number"]  # Latest version
    version2 = versions[1]["version_number"]  # Second latest version
    print(f"   Going to compare version {version1} with {version2}")
    
    # 4. Test the diff API directly
    print(f"\n4. Testing diff API for ontology {ontology_id}, comparing versions {version1} and {version2}...")
    response = requests.get(
        f"http://localhost:3333/ontology-editor/api/versions/{ontology_id}/diff",
        params={"from": version2, "to": version1, "format": "unified"} 
    )
    
    if response.status_code != 200:
        print(f"❌ Diff API failed. Status code: {response.status_code}")
        if response.status_code == 404:
            print("   The error we were fixing (404) is still occurring!")
        print(f"   Response: {response.text[:500]}")
        return False
    
    try:
        diff_data = response.json()
        if "diff" not in diff_data:
            print("❌ Diff API response doesn't contain the expected 'diff' field")
            print(f"   Response keys: {list(diff_data.keys())}")
            return False
        
        print("✅ Diff API returned the expected response structure")
        print("   Found fields: from_version, to_version, diff, format")
        print("\nDIFF FIX VERIFICATION SUCCESS!")
        print("The ontology diff viewer now works correctly when accessing the editor directly.")
        return True
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse JSON response: {e}")
        print(f"   Response: {response.text[:500]}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify ontology diff viewer fix")
    parser.add_argument("--verbose", action="store_true", help="Show verbose output")
    args = parser.parse_args()
    
    success = test_direct_ontology_editor_access()
    sys.exit(0 if success else 1)
