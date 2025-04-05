#!/usr/bin/env python3
"""
Script to check and fix decision options in the database.

This script checks the options field in the actions table and ensures they are
in the correct format for the simulation controller.
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

def check_and_fix_decision_options():
    """Check and fix decision options in the database."""
    # Get all actions that are decision points
    decision_actions = Action.query.filter_by(is_decision=True).all()
    logger.info(f"Found {len(decision_actions)} decision actions")
    
    fixed_count = 0
    for action in decision_actions:
        logger.info(f"Checking action {action.id}: {action.name}")
        
        # Check if options is None or not in the expected format
        if action.options is None:
            logger.info(f"Action {action.id} has no options, setting default options")
            action.options = [
                {
                    'id': 1,
                    'description': 'Option 1: Take the ethical high ground'
                },
                {
                    'id': 2,
                    'description': 'Option 2: Compromise for practical reasons'
                },
                {
                    'id': 3,
                    'description': 'Option 3: Prioritize efficiency over other considerations'
                }
            ]
            fixed_count += 1
        elif not isinstance(action.options, list):
            logger.info(f"Action {action.id} has options in wrong format: {type(action.options)}")
            try:
                # Try to convert to list if it's a string
                if isinstance(action.options, str):
                    options = json.loads(action.options)
                    if isinstance(options, list):
                        action.options = options
                        fixed_count += 1
                    else:
                        logger.warning(f"Could not convert options to list for action {action.id}")
                else:
                    logger.warning(f"Options for action {action.id} is not a string or list")
            except Exception as e:
                logger.error(f"Error converting options for action {action.id}: {str(e)}")
        else:
            # Check if each option has id and description
            valid_options = True
            for i, option in enumerate(action.options):
                if not isinstance(option, dict) or 'id' not in option or 'description' not in option:
                    valid_options = False
                    logger.info(f"Option {i} for action {action.id} is missing id or description: {option}")
                    break
            
            if not valid_options:
                logger.info(f"Fixing options for action {action.id}")
                action.options = [
                    {
                        'id': 1,
                        'description': 'Option 1: Take the ethical high ground'
                    },
                    {
                        'id': 2,
                        'description': 'Option 2: Compromise for practical reasons'
                    },
                    {
                        'id': 3,
                        'description': 'Option 3: Prioritize efficiency over other considerations'
                    }
                ]
                fixed_count += 1
    
    # Commit changes if any were made
    if fixed_count > 0:
        logger.info(f"Fixed {fixed_count} actions, committing changes")
        db.session.commit()
    else:
        logger.info("No actions needed fixing")

def main():
    """Main function."""
    app = create_app()
    with app.app_context():
        check_and_fix_decision_options()

if __name__ == '__main__':
    main()
