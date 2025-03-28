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
from datetime import datetime, timedelta

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.world import World
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.resource import Resource
from app.models.condition import Condition
from app.models.condition_type import ConditionType
from app.models.resource_type import ResourceType
from app.models.role import Role
from app.models.event import Event, Action

def populate_scenario(scenario_id=None, world_name=None):
    """
    Populate a scenario with characters, resources, conditions, and timeline items.
    
    Args:
        scenario_id: ID of existing scenario to modify, or None to create a new scenario
        world_name: Name of the world to use when creating a new scenario
    
    Returns:
        ID of the created or modified scenario
    """
    app = create_app()
    
    with app.app_context():
        # STEP 1: Get or create the scenario
        scenario = None
        if scenario_id:
            # Get existing scenario
            scenario = Scenario.query.get(scenario_id)
            if not scenario:
                print(f"Error: Scenario with ID {scenario_id} not found")
                return None
            print(f"Modifying existing scenario: {scenario.name} (ID: {scenario.id})")
        else:
            # Create new scenario in the specified world
            if not world_name:
                print("Error: world_name is required when creating a new scenario")
                return None
                
            world = World.query.filter_by(name=world_name).first()
            if not world:
                print(f"Error: World '{world_name}' not found")
                return None
                
            # Create a new scenario
            scenario = Scenario(
                name=scenario_data["name"],
                description=scenario_data["description"],
                world_id=world.id
            )
            db.session.add(scenario)
            db.session.commit()
            print(f"Created new scenario: {scenario.name} (ID: {scenario.id})")
        
        # STEP 2: Add characters
        characters = {}
        for char_key, char_data in scenario_data["characters"].items():
            # Find the role
            role = Role.query.filter_by(name=char_data["role"], world_id=scenario.world_id).first()
            if not role:
                print(f"Warning: Role '{char_data['role']}' not found. Creating a placeholder role.")
                role = Role(
                    name=char_data["role"],
                    description=f"Placeholder role for {char_data['role']}",
                    world_id=scenario.world_id,
                    tier=char_data.get("tier", 1)
                )
                db.session.add(role)
                db.session.flush()
            
            # Create the character
            character = Character(
                name=char_data["name"],
                scenario_id=scenario.id,
                role_id=role.id,
                role=char_data["role"],  # Legacy field
                attributes=char_data.get("attributes", {})
            )
            db.session.add(character)
            db.session.flush()
            characters[char_key] = character
            
            # Add conditions to the character
            for condition_data in char_data.get("conditions", []):
                # Find the condition type
                condition_type = ConditionType.query.filter_by(
                    name=condition_data["type"], 
                    world_id=scenario.world_id
                ).first()
                
                if not condition_type:
                    print(f"Warning: Condition type '{condition_data['type']}' not found. Creating a placeholder.")
                    condition_type = ConditionType(
                        name=condition_data["type"],
                        description=f"Placeholder condition type for {condition_data['type']}",
                        world_id=scenario.world_id,
                        category=condition_data.get("category", "General")
                    )
                    db.session.add(condition_type)
                    db.session.flush()
                
                # Create the condition
                condition = Condition(
                    character_id=character.id,
                    name=condition_data["type"],  # Legacy field
                    condition_type_id=condition_type.id,
                    description=condition_data["description"],
                    severity=condition_data.get("severity", 5)
                )
                db.session.add(condition)
            
        db.session.commit()
        print(f"Added {len(characters)} characters with their conditions")
        
        # STEP 3: Add resources
        for resource_data in scenario_data["resources"]:
            # Find the resource type
            resource_type = ResourceType.query.filter_by(
                name=resource_data["type"], 
                world_id=scenario.world_id
            ).first()
            
            if not resource_type:
                print(f"Warning: Resource type '{resource_data['type']}' not found. Creating a placeholder.")
                resource_type = ResourceType(
                    name=resource_data["type"],
                    description=f"Placeholder resource type for {resource_data['type']}",
                    world_id=scenario.world_id,
                    category=resource_data.get("category", "General")
                )
                db.session.add(resource_type)
                db.session.flush()
            
            # Create the resource
            resource = Resource(
                name=resource_data["name"],
                scenario_id=scenario.id,
                resource_type_id=resource_type.id,
                type=resource_data["type"],  # Legacy field
                quantity=resource_data.get("quantity", 1),
                description=resource_data["description"]
            )
            db.session.add(resource)
        
        db.session.commit()
        print(f"Added {len(scenario_data['resources'])} resources")
        
        # STEP 4: Add timeline items (events and actions)
        # Base time for the timeline
        base_time = datetime.now() - timedelta(days=7)  # Start a week ago
        
        # Process events
        for event_data in scenario_data["timeline"]["events"]:
            # Find the referenced character if specified
            character_id = None
            if "character" in event_data:
                character_key = event_data["character"]
                if character_key in characters:
                    character_id = characters[character_key].id
                else:
                    print(f"Warning: Character key '{character_key}' not found for event")
            
            # Calculate event time
            days = event_data.get("days", 0)
            hours = event_data.get("hours", 0)
            minutes = event_data.get("minutes", 0)
            event_time = base_time + timedelta(days=days, hours=hours, minutes=minutes)
            
            # Create the event
            event = Event(
                scenario_id=scenario.id,
                character_id=character_id,
                event_time=event_time,
                description=event_data["description"],
                parameters=event_data.get("parameters", {})
            )
            db.session.add(event)
        
        # Process actions
        for action_data in scenario_data["timeline"]["actions"]:
            # Find the referenced character if specified
            character_id = None
            if "character" in action_data:
                character_key = action_data["character"]
                if character_key in characters:
                    character_id = characters[character_key].id
                else:
                    print(f"Warning: Character key '{character_key}' not found for action")
            
            # Calculate action time
            days = action_data.get("days", 0)
            hours = action_data.get("hours", 0)
            minutes = action_data.get("minutes", 0)
            action_time = base_time + timedelta(days=days, hours=hours, minutes=minutes)
            
            # Create the action
            action = Action(
                name=action_data["name"],
                description=action_data["description"],
                scenario_id=scenario.id,
                character_id=character_id,
                action_time=action_time,
                action_type=action_data.get("type", "GenericAction"),
                parameters=action_data.get("parameters", {}),
                is_decision=action_data.get("is_decision", False),
                options=action_data.get("options", []) if action_data.get("is_decision", False) else []
            )
            db.session.add(action)
        
        db.session.commit()
        
        timeline_count = len(scenario_data["timeline"]["events"]) + len(scenario_data["timeline"]["actions"])
        print(f"Added {timeline_count} timeline items")
        
        print(f"Successfully populated scenario: {scenario.name} (ID: {scenario.id})")
        return scenario.id


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
