"""
Script to run the migration to add guidelines, cases, and rulesets to worlds table.
"""
import os
import sys
from flask import Flask
from flask_migrate import Migrate, upgrade

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db

app = create_app()
migrate = Migrate(app, db)

with app.app_context():
    # Run the migration
    upgrade(revision='add_guidelines_cases_rulesets')
    print("Migration completed successfully!")
