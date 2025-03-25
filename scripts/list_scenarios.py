#!/usr/bin/env python3
"""
Script to list all scenarios in the database.
"""

import sys
import os

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import Scenario

def list_scenarios():
    """List all scenarios in the database."""
    app = create_app()
    with app.app_context():
        scenarios = Scenario.query.all()
        print("Available Scenarios:")
        for s in scenarios:
            print(f"ID: {s.id}, Name: {s.name}")

if __name__ == "__main__":
    list_scenarios()
