#!/usr/bin/env python3
"""
Script to run the migration to convert decisions to actions.
"""
import os
import sys
from flask import Flask
from flask_migrate import Migrate, upgrade

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import db

def run_migration():
    """Run the migration to convert decisions to actions."""
    # Create a minimal Flask app to work with the database
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or "postgresql://postgres:PASS@localhost/ai_ethical_dm"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize the app with the database and migrations
    db.init_app(app)
    migrate = Migrate(app, db)
    
    # Import all models to ensure they're registered with SQLAlchemy
    from app.models.user import User
    from app.models.world import World
    from app.models.scenario import Scenario
    from app.models.character import Character
    from app.models.role import Role
    from app.models.resource import Resource
    from app.models.resource_type import ResourceType
    from app.models.condition import Condition
    from app.models.condition_type import ConditionType
    from app.models.event import Event, Action
    from app.models.decision import Decision
    from app.models.evaluation import Evaluation
    
    with app.app_context():
        # Run the migration
        upgrade(revision='migrate_decisions_to_actions')
        
        print("Migration completed successfully!")

if __name__ == '__main__':
    run_migration()
