"""
This script fixes the model import order issue in the application.
It ensures that the Guideline model is imported and initialized before being
referenced by the World model to avoid SQLAlchemy initialization errors.
"""

import os
import sys

# Add the parent directory to the path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the models in the correct order
from app.models.entity_triple import EntityTriple
from app.models.guideline import Guideline
from app.models.world import World

print("Models imported in the correct order.")
print(f"Guideline model: {Guideline}")
print(f"World model: {World}")
print(f"EntityTriple model: {EntityTriple}")
print("\nTo use these models properly, make sure they are imported in the correct order in your application.")
print("You can add explicit imports in app/__init__.py after the db initialization.")
