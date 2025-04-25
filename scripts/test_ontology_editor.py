#!/usr/bin/env python3
"""
Script to test the ontology editor functionality.
Starts the application and provides instructions for testing.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app

if __name__ == "__main__":
    print("\n=== Ontology Editor Testing ===")
    print("\nStarting the application for testing the ontology editor...")
    print("Once the server is running, open http://localhost:3333/ontology-editor/?ontology_id=1&view=full in your browser.")
    print("\nTest the following functionality:")
    print("1. Check if the 'Validate' button appears correctly (not cropped)")
    print("2. Click the 'Validate' button to ensure validation works properly")
    print("3. If the ontology is valid, you should see a success message")
    print("4. If there are any syntax errors, they should be displayed clearly")
    print("\nPress Ctrl+C to stop the server when done testing.\n")
    
    app = create_app()
    app.run(host='0.0.0.0', port=3333, debug=True)
