#!/usr/bin/env python3
"""
Template script for populating scenario tables with characters, resources, conditions, and timeline items.
This script demonstrates how to add entities to a scenario in a repeatable way.

Usage:
1. Modify the scenario_data dictionary to define your scenario entities
2. Run the script: python populate_scenario_template.py
"""

import sys
import os

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from utilities.entity_manager import create_ethical_scenario

def populate_scenario(scenario_id=None, world_name=None):
    """
    Populate a scenario with characters, resources, conditions, and timeline items.
    
    Args:
        scenario_id: ID of existing scenario to modify, or None to create a new scenario
        world_name: Name of the world to use when creating a new scenario
    
    Returns:
        ID of the created or modified scenario
    """
    if scenario_id:
        # Not implemented yet - future enhancement
        print("Modifying existing scenarios is not implemented yet. Creating a new scenario instead.")
        scenario_id = None
    
    if not world_name:
        print("Error: world_name is required when creating a new scenario")
        return None
    
    # Create a new scenario with all entities
    try:
        scenario_id = create_ethical_scenario(
            world_name=world_name,
            scenario_name=scenario_data["name"],
            scenario_description=scenario_data["description"],
            characters=scenario_data["characters"],
            resources=scenario_data["resources"],
            timeline=scenario_data["timeline"]
        )
        print(f"Successfully populated scenario with ID: {scenario_id}")
        return scenario_id
    except Exception as e:
        print(f"Error creating scenario: {e}")
        return None


# Define your scenario data here
scenario_data = {
    "name": "Bridge Safety Dilemma",
    "description": "A structural engineer discovers potential safety issues in a bridge design that has already been approved for construction.",
    
    "characters": {
        "engineer": {
            "name": "Alex Chen",
            "role": "Structural Engineer", 
            "tier": 2,
            "attributes": {
                "years_experience": 8, 
                "specialty": "bridge design"
            },
            "conditions": [
                {
                    "type": "Safety Risk",
                    "category": "Safety",
                    "description": "Concerned about potential structural failure",
                    "severity": 8
                }
            ]
        },
        "manager": {
            "name": "Taylor Santos",
            "role": "Project Manager",
            "tier": 3,
            "attributes": {
                "deadline_focused": True
            },
            "conditions": [
                {
                    "type": "Time Pressure",
                    "category": "Operational",
                    "description": "Under pressure to meet construction deadline",
                    "severity": 9
                }
            ]
        },
        "client_rep": {
            "name": "Morgan Williams",
            "role": "Client Representative",
            "tier": 1,
            "attributes": {
                "budget_conscious": True
            }
        }
    },
    
    "resources": [
        {
            "name": "Bridge Design Specifications",
            "type": "Design Document",
            "category": "Document",
            "quantity": 1,
            "description": "Technical specifications for the bridge design"
        },
        {
            "name": "Construction Budget",
            "type": "Construction Budget",
            "category": "Financial",
            "quantity": 1,
            "description": "$5M allocated for bridge construction"
        },
        {
            "name": "Safety Regulations",
            "type": "Regulatory Document",
            "category": "Document",
            "quantity": 1,
            "description": "Current safety regulations for bridge construction"
        }
    ],
    
    "timeline": {
        "events": [
            {
                "description": "Alex discovers potential structural weakness in the bridge design during final review",
                "character": "engineer",
                "days": 0,
                "hours": 0,
                "minutes": 0,
                "parameters": {
                    "location": "Engineering office", 
                    "severity": "high"
                }
            },
            {
                "description": "Taylor reminds the team about the approaching construction deadline",
                "character": "manager",
                "days": 1,
                "hours": 0,
                "minutes": 0,
                "parameters": {
                    "urgency": "high"
                }
            },
            {
                "description": "Client representative calls to check on project status",
                "character": "client_rep",
                "days": 2,
                "hours": 10,
                "minutes": 0,
                "parameters": {
                    "tone": "concerned"
                }
            }
        ],
        "actions": [
            {
                "name": "Analysis of Design",
                "description": "Alex performs detailed analysis of the design to confirm concerns",
                "character": "engineer",
                "days": 0,
                "hours": 8,
                "minutes": 0,
                "type": "Analysis",
                "is_decision": False
            },
            {
                "name": "Meeting with Manager",
                "description": "Alex discusses concerns with Taylor",
                "character": "engineer",
                "days": 1,
                "hours": 14,
                "minutes": 0,
                "type": "Meeting",
                "parameters": {
                    "reception": "skeptical"
                },
                "is_decision": False
            },
            {
                "name": "Ethical Decision",
                "description": "Alex must decide whether to report the safety concern",
                "character": "engineer",
                "days": 3,
                "hours": 9,
                "minutes": 0,
                "type": "EthicalDecision",
                "is_decision": True,
                "options": [
                    "Report safety concerns and recommend redesign",
                    "Suggest minor modifications within timeline",
                    "Request more time for analysis",
                    "Proceed with current design and monitor closely"
                ]
            }
        ]
    }
}


if __name__ == "__main__":
    # To create a new scenario:
    # populate_scenario(world_name="Engineering Ethics")
    
    # To modify an existing scenario:
    # populate_scenario(scenario_id=1)
    
    # By default, create a new scenario in Engineering Ethics world
    populate_scenario(world_name="Engineering Ethics")
