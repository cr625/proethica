#!/usr/bin/env python3
"""
Script to list all worlds in the database.
"""

import sys
import os

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import World

def list_worlds():
    """List all worlds in the database."""
    app = create_app()
    with app.app_context():
        worlds = World.query.all()
        print("Available Worlds:")
        for w in worlds:
            print(f"ID: {w.id}, Name: {w.name}")

if __name__ == "__main__":
    list_worlds()
