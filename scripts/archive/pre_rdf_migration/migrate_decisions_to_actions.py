#!/usr/bin/env python3
"""
Script to migrate decisions to actions by:
1. Adding new fields to the actions table
2. Migrating data from the decisions table to the actions table
3. Updating the evaluations table to reference actions instead of decisions
"""
import os
import sys
from flask import Flask
from flask_migrate import Migrate
from alembic.config import Config
from alembic import command
import json
from datetime import datetime

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import db

def migrate_decisions_to_actions():
    """Migrate decisions to actions."""
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
        # Get the path to the migrations directory
        migrations_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migrations')
        
        # Set up the alembic config
        config = Config(os.path.join(migrations_dir, 'alembic.ini'))
        config.set_main_option('script_location', migrations_dir)
        
        # Generate a new migration
        command.revision(config, message='migrate_decisions_to_actions', autogenerate=True)
        
        # Apply the migration to the database
        command.upgrade(config, 'head')
        
        print("Migration generated and applied successfully!")
        
        # Now migrate the data from decisions to actions
        decisions = Decision.query.all()
        print(f"Found {len(decisions)} decisions to migrate")
        
        for decision in decisions:
            # Create a new action from the decision
            action = Action(
                name=f"Decision: {decision.description[:50]}...",
                description=decision.description,
                scenario_id=decision.scenario_id,
                action_time=decision.decision_time,
                parameters={},
                is_decision=True,
                options=decision.options,
                selected_option=decision.selected_option
            )
            db.session.add(action)
            db.session.flush()  # Get the ID without committing
            
            # Update evaluations to reference the new action
            for evaluation in decision.evaluations:
                evaluation.action_id = action.id
            
        # Commit all changes
        db.session.commit()
        
        print("Data migration completed successfully!")

if __name__ == '__main__':
    migrate_decisions_to_actions()
