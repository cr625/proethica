#!/usr/bin/env python3
"""
Create database tables for case deconstruction system.
"""

import os
import sys

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db

def create_deconstruction_tables():
    """Create the case deconstruction database tables."""
    app = create_app('config')
    
    with app.app_context():
        try:
            # Import the models to register them
            from app.models.document import Document  # Import Document first
            from app.models.scenario import Scenario  # Import Scenario for foreign key
            from app.models.deconstructed_case import DeconstructedCase, ScenarioTemplate
            
            # Create the tables
            db.create_all()
            
            print("✅ Case deconstruction tables created successfully!")
            print("   - deconstructed_cases")
            print("   - scenario_templates")
            print()
            print("🚀 Ready to start Phase 1 case deconstruction!")
            
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
            raise

if __name__ == '__main__':
    create_deconstruction_tables()