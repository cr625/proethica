#!/usr/bin/env python3
"""
Script to update decision options for all actions in the database.

This script updates the options field in the actions table with scenario-specific
decision options for all decision actions.
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
    """Update decision options for all actions in the database."""
    # Get all actions that are decision points
    decision_actions = Action.query.filter_by(is_decision=True).all()
    logger.info(f"Found {len(decision_actions)} decision actions")
    
    # Update options for action ID 13 (Consult with Managing Partner)
    action_13 = Action.query.get(13)
    if action_13:
        logger.info(f"Updating options for action {action_13.id}: {action_13.name}")
        action_13.options = [
            {
                'id': 1,
                'description': 'Recommend declining the case due to ethical concerns about representing a client with a history of environmental violations'
            },
            {
                'id': 2,
                'description': 'Suggest accepting the case but establishing clear ethical boundaries and expectations with the client'
            },
            {
                'id': 3,
                'description': 'Propose accepting the case and focusing solely on the legal merits without addressing past ethical concerns'
            },
            {
                'id': 4,
                'description': 'Recommend further investigation into the client\'s environmental practices before making a decision'
            }
        ]
        logger.info(f"Updated options for action {action_13.id}")
    else:
        logger.warning("Action 13 not found")
    
    # Update options for action ID 14 (Make Final Decision on Representation)
    action_14 = Action.query.get(14)
    if action_14:
        logger.info(f"Updating options for action {action_14.id}: {action_14.name}")
        action_14.options = [
            {
                'id': 1,
                'description': 'Decline the case, citing the firm\'s commitment to environmental ethics and potential conflicts with existing clients'
            },
            {
                'id': 2,
                'description': 'Accept the case conditionally, requiring the client to commit to improved environmental practices'
            },
            {
                'id': 3,
                'description': 'Accept the case without conditions, focusing on providing the best legal representation regardless of past issues'
            },
            {
                'id': 4,
                'description': 'Refer the client to another firm better suited to handle their legal needs'
            }
        ]
        logger.info(f"Updated options for action {action_14.id}")
    else:
        logger.warning("Action 14 not found")
    
    # Update options for action ID 20 (Allocate Limited Medical Resources)
    action_20 = Action.query.get(20)
    if action_20:
        logger.info(f"Updating options for action {action_20.id}: {action_20.name}")
        action_20.options = [
            {
                'id': 1,
                'description': 'Allocate resources based on medical need and likelihood of survival, regardless of military rank or status'
            },
            {
                'id': 2,
                'description': 'Prioritize treatment for higher-ranking officers and specialists with critical skills'
            },
            {
                'id': 3,
                'description': 'Distribute resources equally among all wounded, even if it means some may not receive optimal care'
            },
            {
                'id': 4,
                'description': 'Focus resources on those who can return to duty quickest to maintain operational effectiveness'
            }
        ]
        logger.info(f"Updated options for action {action_20.id}")
    else:
        logger.warning("Action 20 not found")
    
    # Update options for action ID 21 (Determine MEDEVAC Evacuation Priority)
    action_21 = Action.query.get(21)
    if action_21:
        logger.info(f"Updating options for action {action_21.id}: {action_21.name}")
        action_21.options = [
            {
                'id': 1,
                'description': 'Evacuate based on medical triage principles: most severely wounded with chance of survival first'
            },
            {
                'id': 2,
                'description': 'Prioritize evacuation of high-value personnel (commanding officers, intelligence specialists, etc.)'
            },
            {
                'id': 3,
                'description': 'Evacuate those with the best chance of full recovery and return to duty first'
            },
            {
                'id': 4,
                'description': 'Implement a first-come, first-served evacuation order to avoid complex ethical decisions in the field'
            }
        ]
        logger.info(f"Updated options for action {action_21.id}")
    else:
        logger.warning("Action 21 not found")
    
    # Update options for action ID 17 (Decide Whether to Report Design Deficiency)
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
    
    # Update options for action ID 18 (Decide How to Address Design Deficiency)
    action_18 = Action.query.get(18)
    if action_18:
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
    else:
        logger.warning("Action 18 not found")
    
    # Commit changes
    db.session.commit()
    logger.info("Changes committed to database")

def main():
    """Main function."""
    app = create_app()
    with app.app_context():
        update_decision_options()

if __name__ == '__main__':
