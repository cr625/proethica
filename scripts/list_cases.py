#!/usr/bin/env python3
"""
List cases in the database
"""
import os
import sys

# Add the current directory to the path
sys.path.insert(0, os.path.abspath('.'))

try:
    # Import Flask app and create app context
    from app import create_app
    app = create_app()
    
    with app.app_context():
        # Import models
        from app.models.document import Document
        
        # Get cases
        cases = Document.query.filter_by(type='case').all()
        
        print(f"Found {len(cases)} cases in the database:")
        
        for case in cases:
            world_info = f", World ID: {case.world_id}" if case.world_id else ""
            print(f"ID: {case.id}, Title: {case.title}{world_info}")
            
        print("\nFirst 5 cases with their URLs:")
        for case in cases[:5]:
            print(f"- Case {case.id}: http://localhost:5000/cases/{case.id}")
        
except Exception as e:
    print(f"Error: {str(e)}")
