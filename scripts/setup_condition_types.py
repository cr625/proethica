"""
Script to set up condition types for the application.
This script will:
1. Run the migration to create the condition_types table
2. Populate the condition_types table with initial data
"""

import sys
import os
import subprocess
from datetime import datetime

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import World, ConditionType
from scripts.populate_condition_types import populate_condition_types

def run_migration():
    """Run the migration to create the condition_types table."""
    print("Running migration to create condition_types table...")
    try:
        # Run the migration command
        result = subprocess.run(
            ["flask", "db", "upgrade", "add_condition_types_table"],
            capture_output=True,
            text=True,
            check=True
        )
        print("Migration output:")
        print(result.stdout)
        if result.stderr:
            print("Migration errors:")
            print(result.stderr)
        print("Migration completed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Migration failed with error code {e.returncode}:")
        print(e.stdout)
        print(e.stderr)
        return False

def setup_condition_types():
    """Set up condition types for the application."""
    # Run the migration
    if not run_migration():
        print("Migration failed. Aborting setup.")
        return False
    
    # Populate the condition_types table
    print("Populating condition_types table...")
    try:
        populate_condition_types()
        print("Condition types populated successfully.")
        return True
    except Exception as e:
        print(f"Error populating condition types: {str(e)}")
        return False

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        # Check if condition_types table exists and has data
        try:
            count = ConditionType.query.count()
            if count > 0:
                print(f"Condition types table already exists with {count} records.")
                response = input("Do you want to continue anyway? (y/n): ")
                if response.lower() != 'y':
                    print("Setup aborted.")
                    sys.exit(0)
        except Exception:
            # Table doesn't exist yet, which is fine
            pass
        
        # Run the setup
        if setup_condition_types():
            print("Condition types setup completed successfully.")
        else:
            print("Condition types setup failed.")
            sys.exit(1)
