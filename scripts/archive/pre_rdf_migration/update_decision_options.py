#!/usr/bin/env python3
"""
Script to update decision options for specific actions in the database.

This script updates the options field in the actions table with scenario-specific
decision options.
"""

import sys
import os
import json
import logging
from datetime import datetime

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db, create_app
from app.models.event import Action, Event

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_decision_options():
    """Update decision options for specific actions in the database."""
    # Get all actions that are decision points
    decision_actions = Action.query.filter_by(is_decision=True).all()
    logger.info(f"Found {len(decision_actions)} decision actions")
    
    # Specific options for action ID 17 (Report or Not decision)
    action_17 = Action.query.get(17)
    if action_17:
        logger.info(f"Updating options for action {action_17.id}: {action_17.name}")
        action_17.options = [
            {
                'id': 1,
                'description': 'Report the deficiency immediately, prioritizing safety and professional integrity'
            },
            {
                'id': 2,
                'description': 'Conduct additional tests to confirm the deficiency before reporting'
            },
            {
                'id': 3,
                'description': 'Address the issue internally without formal reporting to avoid delays'
            },
            {
                'id': 4,
                'description': 'Consult with senior engineers before making a decision'
            }
        ]
        logger.info(f"Updated options for action {action_17.id}")
    else:
        logger.warning("Action 17 not found")
    
    # Specific options for action ID 18 (another decision if it exists)
    action_18 = Action.query.get(18)
    if action_18 and action_18.is_decision:
        logger.info(f"Updating options for action {action_18.id}: {action_18.name}")
        action_18.options = [
            {
                'id': 1,
                'description': 'Prioritize ethical considerations and professional standards'
            },
            {
                'id': 2,
                'description': 'Balance ethical concerns with practical project constraints'
            },
            {
                'id': 3,
                'description': 'Focus on meeting project deadlines and budget requirements'
            },
            {
                'id': 4,
                'description': 'Seek guidance from professional engineering ethics resources'
            }
        ]
        logger.info(f"Updated options for action {action_18.id}")
    
    # Commit changes
    db.session.commit()
    logger.info("Changes committed to database")

def main():
    """Main function."""
    app = create_app()
    with app.app_context():
        update_decision_options()

if __name__ == '__main__':
    main()
