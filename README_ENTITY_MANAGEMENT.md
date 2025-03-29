# ProEthica Entity Management Guide

This guide explains how to use the entity management system for populating scenario tables with characters, resources, conditions, and timeline items. It also includes instructions for running the ProEthica application.

## Running the ProEthica Application

There are three main ways to run the application:

### 1. Basic Development Run

```bash
python run.py
```

This starts the application with the Flask development server.

### 2. Server Restart Script

```bash
./restart_server.sh
```

This kills any existing instances and restarts the server.

### 3. Full Production Setup (Recommended)

```bash
./run_proethica_with_agents.sh
```

This is the most comprehensive option that sets up the MCP server and uses Gunicorn.

For full details on running the application, see [HOW_TO_RUN.md](HOW_TO_RUN.md).

## Entity Management System

The entity management system provides a streamlined way to create and populate scenarios with characters, resources, conditions, and timeline items.

### Key Components

1. **Entity Manager Utility**: Located at `utilities/entity_manager.py`
2. **Consolidated Scripts**: Located at `scripts/populate_entities.py`
3. **Scenario Template Script**: Located at `populate_scenario_template.py`
4. **Documentation**: Located at `scenario_entity_management.md`

### Quick Start Guide

#### 1. Creating a Complete Scenario

The easiest way to create a scenario is to use the template script:

1. Edit the `scenario_data` dictionary in `populate_scenario_template.py` to define your scenario
2. Run the script:

```bash
python populate_scenario_template.py
```

This will create a new scenario with all defined characters, resources, and timeline items.

#### 2. Populating Entity Types

To populate entity types (roles, condition types, resource types) from an ontology:

```bash
python scripts/populate_entities.py --world "Engineering Ethics" --ontology
```

To populate predefined entity types:

```bash
python scripts/populate_entities.py --world "Engineering Ethics" --predefined
```

#### 3. Adding Test Timeline Items

To add test events and actions to an existing scenario:

```bash
python scripts/populate_entities.py --scenario 1 --test-timeline
```

### Programmatic Usage

You can also use the entity manager functions directly in your Python code:

```python
from utilities.entity_manager import create_ethical_scenario

# Create a complete scenario
scenario_id = create_ethical_scenario(
    world_name="Engineering Ethics",
    scenario_name="Bridge Safety Dilemma",
    scenario_description="A structural engineer discovers potential safety issues...",
    characters={
        "engineer": {
            "name": "Alex Chen",
            "role": "Structural Engineer",
            "attributes": {"years_experience": 8},
            "conditions": [
                {"type": "Safety Risk", "description": "Concerned about failure", "severity": 8}
            ]
        },
        # More characters...
    },
    resources=[
        {
            "name": "Bridge Design Specifications",
            "type": "Design Document",
            "description": "Technical specifications for the bridge design"
        },
        # More resources...
    ],
    timeline={
        "events": [
            {
                "description": "Alex discovers structural weakness",
                "character": "engineer",
                "days": 0,
                "parameters": {"location": "Engineering office"}
            },
            # More events...
        ],
        "actions": [
            {
                "name": "Ethical Decision",
                "description": "Alex must decide whether to report the concern",
                "character": "engineer",
                "days": 3,
                "is_decision": True,
                "options": [
                    "Report safety concerns",
                    "Suggest minor modifications",
                    # More options...
                ]
            },
            # More actions...
        ]
    }
)
```

Or work with individual entities:

```python
from utilities.entity_manager import (
    create_or_update_character,
    create_or_update_resource,
    create_timeline_event,
    create_timeline_action
)

# Create a character
character = create_or_update_character(
    scenario_id=1,
    name="Jane Smith",
    role_name="Attorney",
    attributes={"specialty": "corporate law"},
    conditions=[
        {"type": "Conflict of Interest", "description": "Past association with client", "severity": 7}
    ]
)

# Create a resource
resource = create_or_update_resource(
    scenario_id=1,
    name="Legal Brief",
    resource_type_name="Legal Document",
    description="Arguments for motion to dismiss",
    quantity=1
)

# Create a timeline event
event = create_timeline_event(
    scenario_id=1,
    description="Client meeting",
    character_id=character.id,
    parameters={"location": "Law office"}
)

# Create a timeline action with decision point
action = create_timeline_action(
    scenario_id=1,
    name="Advise Client",
    description="Determine how to advise the client",
    character_id=character.id,
    is_decision=True,
    options=[
        "Full disclosure",
        "Partial disclosure",
        "No disclosure"
    ]
)
```

### Scenario Data Structure

The scenario data uses a specific format:

```python
scenario_data = {
    "name": "Scenario Name",
    "description": "Detailed description...",
    
    "characters": {
        "character_key": {
            "name": "Character Name",
            "role": "Role Name",
            "tier": 2,  # Optional
            "attributes": {
                "attribute1": "value1",
                "attribute2": "value2"
            },
            "conditions": [
                {
                    "type": "Condition Type Name",
                    "category": "Category",  # Optional
                    "description": "Condition description",
                    "severity": 7  # Scale 1-10
                }
            ]
        }
    },
    
    "resources": [
        {
            "name": "Resource Name",
            "type": "Resource Type Name",
            "category": "Category",  # Optional
            "quantity": 1,  # Optional, defaults to 1
            "description": "Resource description"
        }
    ],
    
    "timeline": {
        "events": [
            {
                "description": "Event description",
                "character": "character_key",  # References a key in the characters dict
                "days": 0,  # Days from start
                "hours": 0,  # Hours from start of day
                "minutes": 0,  # Minutes
                "parameters": {
                    "param1": "value1"
                }
            }
        ],
        "actions": [
            {
                "name": "Action Name",
                "description": "Action description",
                "character": "character_key",
                "days": 1,
                "hours": 8,
                "minutes": 30,
                "type": "ActionType",  # Optional
                "parameters": {
                    "param1": "value1"
                },
                "is_decision": false,  # Set to true for decision points
                "options": [  # Required if is_decision is true
                    "Option 1",
                    "Option 2"
                ]
            }
        ]
    }
}
```

## Additional Documentation

For more detailed information, refer to:

- [Scenario Entity Management Guide](scenario_entity_management.md) - Comprehensive guide to entity management
- [ProEthica Application Guide](ProEthica_Application_Guide.md) - Complete guide to using the application
- [ProEthica Technical Overview](ProEthica_Technical_Overview.md) - Technical details of the application architecture

## Workflow Example

A typical workflow for creating and populating a scenario might look like this:

1. Run the application:
   ```bash
   python run.py
   ```

2. Create a new world through the web interface

3. Populate entity types for the world:
   ```bash
   python scripts/populate_entities.py --world "Your World Name" --predefined
   ```

4. Create a scenario using the template script:
   ```bash
   # Edit populate_scenario_template.py first to define your scenario
   python populate_scenario_template.py
   ```

5. Run a simulation with the created scenario through the web interface
