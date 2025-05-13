"""
Script to add a test guideline to a world in ProEthica.
This uploads our test guideline to the Engineering World (ID 1).

Usage:
    python add_test_guideline.py
"""

import requests
import os
import sys
from pathlib import Path

def main():
    # Configuration
    world_id = 1  # Engineering World ID
    server_url = "http://localhost:3333"  # Default local server
    guideline_path = "test_guideline.txt"
    
    # Check if the guideline file exists
    if not Path(guideline_path).exists():
        print(f"Error: Guideline file not found at {guideline_path}")
        sys.exit(1)
    
    # Read the guideline content
    try:
        with open(guideline_path, 'r', encoding='utf-8') as file:
            guideline_content = file.read()
    except Exception as e:
        print(f"Error reading guideline file: {str(e)}")
        sys.exit(1)
    
    # Prepare data for text-based upload
    data = {
        'input_type': 'text',
        'guidelines_title': 'Engineering Ethics Guidelines',
        'guidelines_text': guideline_content
    }
    
    # Upload the guideline
    try:
        print(f"Uploading guideline to world ID {world_id}...")
        response = requests.post(
            f"{server_url}/worlds/{world_id}/guidelines/add",
            data=data
        )
        
        if response.status_code == 200:
            print("Success! Guidelines uploaded successfully.")
            print("You can view them at:")
            print(f"{server_url}/worlds/{world_id}/guidelines")
        else:
            print(f"Error uploading guidelines. Status code: {response.status_code}")
            print(f"Response: {response.text[:500]}...")  # Print first 500 chars of response
            
    except Exception as e:
        print(f"Error connecting to server: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
