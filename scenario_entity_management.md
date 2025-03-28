# Scenario Entity Management Guide

This guide explains how to add and manage entities (characters, resources, conditions, events, actions) in scenarios for the AI Ethical Decision-Making Simulator.

## Entity Types Overview

The system contains several key entity types that make up scenarios:

1. **Characters**: Individuals or entities involved in the scenario (e.g., attorneys, engineers, medics)
2. **Resources**: Objects, documents, or assets that can be used (e.g., medical supplies, legal documents)
3. **Conditions**: States or situations affecting characters (e.g., injuries, conflicts of interest)
4. **Events**: Things that happen in the scenario that characters may respond to
5. **Actions**: Things that characters do, including decision points with multiple options

## Database Models

The core models that define these entities include:

- `Character`: Represents individuals in scenarios
- `Resource`: Represents assets and items in scenarios
- `Condition`: Represents states affecting characters
- `Event`: Represents occurrences in the scenario timeline
- `Action`: Represents character actions, including decision points

Each entity type has associated "type" models that define the categories available in each world:

- `Role`: Defines character roles (linked to characters)
- `ResourceType`: Defines types of resources (linked to resources)
- `ConditionType`: Defines types of conditions (linked to conditions)

## Adding Characters to Scenarios

Characters represent individuals involved in ethical dilemmas. Here's how to add them:

```python
from app import create_app, db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.condition import Condition
from app.models.condition_type import ConditionType
from app.models.role import Role

app = create_app()
with app.app_context():
    # Get the scenario
    scenario = Scenario.query.get(scenario_id)
    
    # Find or create a role
    role = Role.query.filter_by(name='Attorney', world_id=scenario.world_id).first()
    if not role:
        role = Role(
            name='Attorney',
            description='Legal professional licensed to practice law',
            world_id=scenario.world_id,
            ontology_uri='http://example.org/legal-ethics#Attorney',
            tier=2  # Mid-level
        )
        db.session.add(role)
        db.session.flush()
    
    # Create the character
    character = Character(
        name='Jane Smith',
        scenario_id=scenario.id,
        role_id=role.id,
        role='Attorney',  # Legacy field for backward compatibility
        attributes={}  # Optional JSON attributes
    )
    db.session.add(character)
    db.session.flush()
    
    # Add a condition to the character (optional)
    condition_type = ConditionType.query.filter_by(name='Conflict of Interest', world_id=scenario.world_id).first()
    if condition_type:
        condition = Condition(
            character_id=character.id,
            name='Conflict of Interest',  # Legacy field for backward compatibility
            condition_type_id=condition_type.id,
            description='Potential conflict with past client',
            severity=7  # Scale typically 1-10
        )
        db.session.add(condition)
    
    # Commit changes
    db.session.commit()
```

## Adding Resources to Scenarios

Resources represent objects, documents, time, or other assets that characters can use:

```python
from app import create_app, db
from app.models.scenario import Scenario
from app.models.resource import Resource
from app.models.resource_type import ResourceType

app = create_app()
with app.app_context():
    # Get the scenario
    scenario = Scenario.query.get(scenario_id)
    
    # Find or create a resource type
    resource_type = ResourceType.query.filter_by(name='Case File', world_id=scenario.world_id).first()
    if not resource_type:
        resource_type = ResourceType(
            name='Case File',
            description='A file containing case information',
            world_id=scenario.world_id,
            category='Legal',
            ontology_uri='http://example.org/legal-ethics#CaseFile'
        )
        db.session.add(resource_type)
        db.session.flush()
    
    # Create the resource
    resource = Resource(
        name='Smith v. Jones Case File',
        scenario_id=scenario.id,
        resource_type_id=resource_type.id,
        type='Case File',  # Legacy field for backward compatibility
        quantity=1,
        description='Legal documents for the Smith v. Jones lawsuit'
    )
    db.session.add(resource)
    
    # Commit changes
    db.session.commit()
```

## Adding Timeline Items (Events and Actions)

Timeline items represent the sequence of events and actions in a scenario:

```python
from app import create_app, db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.event import Event, Action
from datetime import datetime, timedelta

app = create_app()
with app.app_context():
    # Get the scenario and a character
    scenario = Scenario.query.get(scenario_id)
    character = Character.query.filter_by(name='Jane Smith', scenario_id=scenario.id).first()
    
    # Base time for the timeline
    base_time = datetime.now()
    
    # Add an event
    event = Event(
        scenario_id=scenario.id,
        character_id=character.id,
        event_time=base_time,
        description="Client reveals potentially illegal activity during meeting",
        parameters={
            'location': "Law office conference room",
            'duration': "60 minutes"
        }
    )
    db.session.add(event)
    
    # Add a simple action
    action = Action(
        name="Research legal precedents",
        description="Jane researches relevant case law and precedents",
        scenario_id=scenario.id,
        character_id=character.id,
        action_time=base_time + timedelta(hours=2),
        action_type="http://example.org/legal-ethics#ResearchLaw",
        parameters={
            'research_type': "case law",
            'topic': "attorney-client privilege"
        },
        is_decision=False
    )
    db.session.add(action)
    
    # Add a decision point (action with multiple options)
    decision = Action(
        name="Advise client on disclosure",
        description="Jane must decide how to advise her client regarding disclosure of potentially illegal activity",
        scenario_id=scenario.id,
        character_id=character.id,
        action_time=base_time + timedelta(hours=5),
        action_type="http://example.org/legal-ethics#ProvideAdvice",
        parameters={
            'decision_type': "ethics",
            'risk_level': "high"
        },
        is_decision=True,
        options=[
            "Advise immediate full disclosure to authorities",
            "Recommend partial disclosure with client protections",
            "Suggest internal remediation without disclosure",
            "Withdraw from representation"
        ]
    )
    db.session.add(decision)
    
    # Commit changes
    db.session.commit()
```

## Populating Entity Types from Ontologies

The system can populate roles, resource types, and condition types from ontologies:

```python
from app import create_app, db
from app.models.world import World
from app.models.role import Role
from app.models.resource_type import ResourceType
from app.models.condition_type import ConditionType
from rdflib import Graph, Namespace, RDF, RDFS

app = create_app()
with app.app_context():
    # Get the world
    world = World.query.filter_by(name="Legal Ethics World").first()
    
    # Load the ontology
    g = Graph()
    ontology_path = world.ontology_source  # e.g., "mcp/ontology/legal_ethics.ttl"
    g.parse(ontology_path, format="turtle")
    
    # Define namespaces
    LEG = Namespace("http://example.org/legal-ethics#")
    
    # Populate roles from ontology
    for s in g.subjects(RDF.type, LEG.CharacterType):
        # Get the role name, label, description, etc.
        role_name = str(s).split('#')[-1]
        label = next(g.objects(s, RDFS.label), None)
        description = next(g.objects(s, RDFS.comment), None)
        
        # Create or update the role
        role = Role.query.filter_by(name=str(label), world_id=world.id).first()
        if not role:
            role = Role(
                name=str(label),
                description=str(description) if description else None,
                world_id=world.id,
                ontology_uri=str(s)
            )
            db.session.add(role)
    
    # Commit changes
    db.session.commit()
```

## Predefined Entity Type Population Scripts

The system includes scripts to populate entity types for different worlds:

### Condition Types

```python
# Example from scripts/populate_condition_types.py
law_practice_conditions = [
    {
        "name": "Conflict of Interest",
        "description": "Situation where professional judgment may be compromised.",
        "category": "Ethical",
        "severity_range": {"min": 1, "max": 10},
        "ontology_uri": "http://proethica.org/ontology/nj-legal-ethics#ConflictOfInterest"
    },
    # More condition types...
]

# Create condition types in the database
for condition_data in law_practice_conditions:
    condition_type = ConditionType(
        name=condition_data["name"],
        description=condition_data["description"],
        world_id=law_world.id,
        category=condition_data["category"],
        severity_range=condition_data["severity_range"],
        ontology_uri=condition_data["ontology_uri"]
    )
    db.session.add(condition_type)
```

### Resource Types

```python
# Example from scripts/create_basic_resource_types
resource_types = [
    {
        'name': 'Case File',
        'description': 'Legal documents for a specific case',
        'category': 'Legal',
        'world_id': world_id,
        'ontology_uri': 'http://example.org/legal-ethics#CaseFile'
    },
    # More resource types...
]

# Create resource types in the database
for rt_data in resource_types:
    resource_type = ResourceType(**rt_data)
    db.session.add(resource_type)
```

## Best Practices for Entity Management

1. **Entity Relationships**: Ensure that all entities are properly linked (characters to roles, resources to resource types, etc.)

2. **Ontology Consistency**: When creating entities manually, ensure that they align with the world's ontology

3. **Ethical Complexity**: Design characters, resources, and conditions that create meaningful ethical dilemmas

4. **Narrative Coherence**: Ensure that timeline items (events and actions) tell a coherent story about the ethical dilemma

5. **Decision Points**: Include meaningful decision points with realistic ethical options

6. **Entity Balance**: Include a balanced mix of characters, resources, and conditions to create a rich scenario

7. **Reuse Types**: Leverage existing role, resource, and condition types rather than creating new ones when possible

## Example: Complete Scenario Setup Script

Here's a complete example of setting up a simple ethical scenario:

```python
from app import create_app, db
from app.models.world import World
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.resource import Resource
from app.models.condition import Condition
from app.models.event import Event, Action
from app.models.role import Role
from app.models.resource_type import ResourceType
from app.models.condition_type import ConditionType
from datetime import datetime, timedelta

def create_engineering_safety_scenario():
    """Create a scenario about an engineering safety dilemma."""
    app = create_app()
    with app.app_context():
        # 1. Get or create the world
        world = World.query.filter_by(name="Engineering Ethics").first()
        if not world:
            world = World(
                name="Engineering Ethics",
                description="World focused on ethical dilemmas in engineering practice",
                ontology_source="mcp/ontology/engineering_ethics.ttl"
            )
            db.session.add(world)
            db.session.commit()
        
        # 2. Create the scenario
        scenario = Scenario(
            name="Bridge Safety Concern",
            description="A structural engineer discovers potential safety issues in a bridge design that has already been approved for construction.",
            world_id=world.id
        )
        db.session.add(scenario)
        db.session.commit()
        
        # 3. Create roles
        roles = {
            "structural_engineer": Role(
                name="Structural Engineer",
                description="Engineer specializing in structural analysis and design",
                world_id=world.id,
                tier=2,
                ontology_uri="http://example.org/engineering-ethics#StructuralEngineer"
            ),
            "project_manager": Role(
                name="Project Manager",
                description="Professional responsible for project planning and execution",
                world_id=world.id,
                tier=3,
                ontology_uri="http://example.org/engineering-ethics#ProjectManager"
            ),
            "client": Role(
                name="Client",
                description="Organization commissioning the engineering project",
                world_id=world.id,
                tier=1,
                ontology_uri="http://example.org/engineering-ethics#Client"
            )
        }
        
        for role in roles.values():
            db.session.add(role)
        db.session.commit()
        
        # 4. Create condition types
        condition_types = {
            "time_pressure": ConditionType(
                name="Time Pressure",
                description="Urgent deadline affecting decision-making",
                world_id=world.id,
                category="Operational",
                severity_range={"min": 1, "max": 10},
                ontology_uri="http://example.org/engineering-ethics#TimePressure"
            ),
            "safety_risk": ConditionType(
                name="Safety Risk",
                description="Potential for harm to users or the public",
                world_id=world.id,
                category="Safety",
                severity_range={"min": 1, "max": 10},
                ontology_uri="http://example.org/engineering-ethics#SafetyRisk"
            )
        }
        
        for condition_type in condition_types.values():
            db.session.add(condition_type)
        db.session.commit()
        
        # 5. Create resource types
        resource_types = {
            "design_document": ResourceType(
                name="Design Document",
                description="Technical documents detailing engineering designs",
                world_id=world.id,
                category="Document",
                ontology_uri="http://example.org/engineering-ethics#DesignDocument"
            ),
            "construction_budget": ResourceType(
                name="Construction Budget",
                description="Financial resources allocated for construction",
                world_id=world.id,
                category="Financial",
                ontology_uri="http://example.org/engineering-ethics#ConstructionBudget"
            )
        }
        
        for resource_type in resource_types.values():
            db.session.add(resource_type)
        db.session.commit()
        
        # 6. Create characters
        characters = {
            "engineer": Character(
                name="Alex Chen",
                scenario_id=scenario.id,
                role_id=roles["structural_engineer"].id,
                role="Structural Engineer",
                attributes={"years_experience": 8, "specialty": "bridge design"}
            ),
            "manager": Character(
                name="Taylor Santos",
                scenario_id=scenario.id,
                role_id=roles["project_manager"].id,
                role="Project Manager",
                attributes={"deadline_focused": True}
            ),
            "client_rep": Character(
                name="Morgan Williams",
                scenario_id=scenario.id,
                role_id=roles["client"].id,
                role="Client Representative",
                attributes={"budget_conscious": True}
            )
        }
        
        for character in characters.values():
            db.session.add(character)
        db.session.commit()
        
        # 7. Add conditions to characters
        conditions = [
            Condition(
                character_id=characters["engineer"].id,
                name="Safety Risk",
                condition_type_id=condition_types["safety_risk"].id,
                description="Concerned about potential structural failure",
                severity=8
            ),
            Condition(
                character_id=characters["manager"].id,
                name="Time Pressure",
                condition_type_id=condition_types["time_pressure"].id,
                description="Under pressure to meet construction deadline",
                severity=9
            )
        ]
        
        for condition in conditions:
            db.session.add(condition)
        db.session.commit()
        
        # 8. Create resources
        resources = [
            Resource(
                name="Bridge Design Specifications",
                scenario_id=scenario.id,
                resource_type_id=resource_types["design_document"].id,
                type="Design Document",
                quantity=1,
                description="Technical specifications for the bridge design"
            ),
            Resource(
                name="Construction Budget",
                scenario_id=scenario.id,
                resource_type_id=resource_types["construction_budget"].id,
                type="Construction Budget",
                quantity=1,
                description="$5M allocated for bridge construction"
            )
        ]
        
        for resource in resources:
            db.session.add(resource)
        db.session.commit()
        
        # 9. Create timeline (events and actions)
        base_time = datetime.now() - timedelta(days=7)
        
        timeline_items = [
            Event(
                scenario_id=scenario.id,
                character_id=characters["engineer"].id,
                event_time=base_time,
                description="Alex discovers potential structural weakness in the bridge design during final review",
                parameters={"location": "Engineering office", "severity": "high"}
            ),
            Action(
                name="Analysis of Design",
                description="Alex performs detailed analysis of the design to confirm concerns",
                scenario_id=scenario.id,
                character_id=characters["engineer"].id,
                action_time=base_time + timedelta(hours=8),
                action_type="Analysis",
                parameters={},
                is_decision=False
            ),
            Event(
                scenario_id=scenario.id,
                character_id=characters["manager"].id,
                event_time=base_time + timedelta(days=1),
                description="Taylor reminds the team about the approaching construction deadline",
                parameters={"urgency": "high"}
            ),
            Action(
                name="Ethical Decision",
                description="Alex must decide whether to report the safety concern",
                scenario_id=scenario.id,
                character_id=characters["engineer"].id,
                action_time=base_time + timedelta(days=1, hours=4),
                action_type="EthicalDecision",
                parameters={},
                is_decision=True,
                options=[
                    "Report safety concerns and recommend redesign",
                    "Suggest minor modifications within timeline",
                    "Request more time for analysis",
                    "Proceed with current design and monitor closely"
                ]
            )
        ]
        
        for item in timeline_items:
            db.session.add(item)
        db.session.commit()
        
        print(f"Created scenario: {scenario.name} (ID: {scenario.id})")
        return scenario.id

if __name__ == "__main__":
    create_engineering_safety_scenario()
```

This comprehensive guide should help you understand how to add and manage entities in scenarios for the AI Ethical Decision-Making Simulator.
