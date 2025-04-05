#!/usr/bin/env python3
"""
Script to list all decision actions in the database.
"""

import sys
import os
import logging

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db, create_app
from app.models.event import Action

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def list_decision_actions():
    """List all decision actions in the database."""
    # Get all actions that are decision points
    decision_actions = Action.query.filter_by(is_decision=True).all()
    logger.info(f"Found {len(decision_actions)} decision actions")
    
    for action in decision_actions:
        logger.info(f"ID: {action.id}, Name: {action.name}, Options: {action.options}")

def main():
    """Main function."""
    app = create_app()
    with app.app_context():
        list_decision_actions()

if __name__ == '__main__':
    main()
