#!/usr/bin/env python3
"""
Test script to view guideline section associations.
This script starts a Flask development server for quickly testing the guideline section viewer.
"""

import os
import sys

# Set environment variables before importing app
os.environ['FLASK_APP'] = 'app'
os.environ['FLASK_ENV'] = 'development'
os.environ['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
os.environ['DATABASE_URL'] = "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"

from app import create_app

if __name__ == '__main__':
    # Create and configure the Flask app
    app = create_app('config')
    
    # Document ID to view (default to 251 - Competence in Design Services)
    document_id = 251
    if len(sys.argv) > 1:
        try:
            document_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid document ID: {sys.argv[1]}. Using default ID 251.")
    
    print(f"Starting Flask server to view guideline sections for document ID {document_id}")
    print(f"Once the server is running, navigate to: http://localhost:5000/test/guideline_sections/{document_id}")
    
    # Start the Flask development server
    app.run(host='0.0.0.0', port=5000, debug=True)
