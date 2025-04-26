"""
Script to check the results of our parent class selection fix.
This will visit the entity editor page and check which parent classes are 
actually selected in the drop-downs.
"""
import sys
import os
import requests
import json

def check_debug_endpoint():
    """Check the debug endpoint to see what parent classes are being selected."""
    print("Checking parent class selection via debug endpoint...")
    
    try:
        # Access our debug endpoint
        response = requests.get('http://localhost:5050/debug/1')
        data = response.json()
        
        if not response.ok:
            print(f"Error accessing debug endpoint: {response.status_code}")
            return
        
        # Print the debug information for each role
        print("\n=== ROLE PARENT CLASS INFORMATION ===")
        for role in data['debug_info']:
            print(f"\nRole: {role['label']}")
            print(f"ID: {role['id']}")
            print(f"Parent class: {role['parent_class']}")
            
            # Find any matching parent classes
            matches = [m for m in role['potential_matches'] if m['is_match']]
            if matches:
                print(f"Matched parent: {matches[0]['parent_label']}")
            else:
                print("No matching parent found in dropdown options!")
                
        # Count how many have successful matches
        match_count = sum(1 for role in data['debug_info'] 
                         if any(m['is_match'] for m in role['potential_matches']))
        total_roles = len(data['debug_info'])
        
        print(f"\nRoles with correct parent class matches: {match_count}/{total_roles}")
        
        # Check if we fixed the specific issue with Structural Engineer Role
        structural_role = next((r for r in data['debug_info'] 
                              if r['label'] == 'Structural Engineer Role'), None)
        if structural_role:
            matches = [m for m in structural_role['potential_matches'] if m['is_match']]
            if matches:
                print(f"\nStructural Engineer Role correctly matched to: {matches[0]['parent_label']}")
            else:
                print("\nStructural Engineer Role has no matching parent!")
                
        # Check if Confidential Consultant Role is correctly matched to Consulting Engineer Role
        conf_consultant = next((r for r in data['debug_info'] 
                               if r['label'] == 'Confidential Consultant Role'), None)
        if conf_consultant:
            matches = [m for m in conf_consultant['potential_matches'] if m['is_match']]
            if matches:
                print(f"\nConfidential Consultant Role correctly matched to: {matches[0]['parent_label']}")
                
                # Verify this matches what we expect
                if matches[0]['parent_label'] == 'Consulting Engineer Role':
                    print("✓ This is the correct parent class!")
                else:
                    print("✗ This is NOT the expected parent class!")
            else:
                print("\nConfidential Consultant Role has no matching parent!")
                
    except Exception as e:
        print(f"Error checking debug endpoint: {str(e)}")

if __name__ == '__main__':
    check_debug_endpoint()
