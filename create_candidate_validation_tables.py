#!/usr/bin/env python3
"""
Create tables for candidate role class validation system
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from app.models import db
from app.models.candidate_role_class import CandidateRoleClass, CandidateRoleIndividual

def create_validation_tables():
    """Create the candidate validation tables"""
    print("Creating candidate validation tables...")

    with create_app().app_context():
        try:
            # Create tables
            db.create_all()
            print("✓ Successfully created candidate_role_classes table")
            print("✓ Successfully created candidate_role_individuals table")

            # Verify tables exist
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()

            if 'candidate_role_classes' in tables:
                print("✓ Table 'candidate_role_classes' confirmed")
            else:
                print("✗ Table 'candidate_role_classes' not found")

            if 'candidate_role_individuals' in tables:
                print("✓ Table 'candidate_role_individuals' confirmed")
            else:
                print("✗ Table 'candidate_role_individuals' not found")

            print("\n=== Database Schema Created Successfully ===")

        except Exception as e:
            print(f"✗ Error creating tables: {e}")
            return False

    return True

if __name__ == "__main__":
    success = create_validation_tables()
    if success:
        print("\nCandidate validation system is ready!")
    else:
        print("\nFailed to set up validation system")
        sys.exit(1)