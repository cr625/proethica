# Adding Characters to Scenarios

This document outlines the process for adding characters to existing scenarios in the AI Ethical Decision-Making Simulator. It uses the "Conflict of Interest" scenario in the "Legal Ethics World (New Jersey)" as an example.

## Overview

Characters are essential components of scenarios in the simulator. They represent individuals or entities involved in ethical dilemmas and can have specific roles and conditions that affect the scenario dynamics.

## Prerequisites

Before adding characters to a scenario, you should:

1. Identify the scenario you want to modify
2. Understand the ethical context and dilemma presented in the scenario
3. Determine what roles and perspectives should be represented
4. Consider what conditions (if any) characters should have

## Example: Adding Characters to "Conflict of Interest" Scenario

### Step 1: Identify the Scenario

First, we identified the "Conflict of Interest" scenario in the "Legal Ethics World (New Jersey)":

```python
from app import create_app
from app.models.scenario import Scenario

app = create_app()
with app.app_context():
    # List all scenarios
    scenarios = Scenario.query.all()
    for s in scenarios:
        print(f'- {s.name} (ID: {s.id}, World ID: {s.world_id})')
```

This showed us that the "Conflict of Interest" scenario had ID 3 and World ID 3.

### Step 2: Explore Available Roles and Conditions

Next, we examined the available roles and condition types in the ontology:

```python
from app import create_app
from app.services.mcp_client import MCPClient
from app.models.world import World

app = create_app()
with app.app_context():
    world = World.query.get(3)
    if world and world.ontology_source:
        mcp_client = MCPClient()
        # Get roles from ontology
        entities = mcp_client.get_world_entities(world.ontology_source, entity_type='roles')
        if entities and 'entities' in entities and 'roles' in entities['entities']:
            roles = entities['entities']['roles']
            print(f'Found {len(roles)} roles in the ontology:')
            for role in roles:
                print(f'- {role.get("label")} (ID: {role.get("id")})')
                
        # Get condition types from ontology
        entities = mcp_client.get_world_entities(world.ontology_source, entity_type='conditions')
        if entities and 'entities' in entities and 'conditions' in entities['entities']:
            conditions = entities['entities']['conditions']
            print(f'Found {len(conditions)} condition types in the ontology:')
            for condition in conditions:
                print(f'- {condition.get("label")} (ID: {condition.get("id")})')
```

This showed us the available roles (Attorney, Partner, Associate Attorney, Client, etc.) and condition types (Conflict of Interest, Confidentiality Issue, etc.) that we could use.

### Step 3: Plan the Characters

For the "Conflict of Interest" scenario, we planned the following characters:

1. **Primary Attorney**: A partner at a law firm who is facing the conflict of interest dilemma
   - Name: Michael Reynolds
   - Role: Partner
   - Condition: Conflict of Interest (severity 8)

2. **Current Client A**: A corporate client that the attorney has been representing for years
   - Name: Horizon Technologies Inc.
   - Role: Corporate Client
   - Condition: None initially

3. **Current Client B**: A new individual client whose interests conflict with Client A
   - Name: Sarah Chen
   - Role: Individual Client
   - Condition: None initially

4. **Junior Associate**: Working under the partner on both cases
   - Name: Jason Martinez
   - Role: Associate Attorney
   - Condition: Conflict of Interest (severity 6)

5. **Managing Partner**: Responsible for firm ethics compliance
   - Name: Eleanor Washington
   - Role: Managing Partner
   - Condition: None initially

### Step 4: Add the Characters

We added each character using Python code that interacts with the database:

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
    scenario = Scenario.query.get(3)
    
    # Example: Adding Michael Reynolds (Partner)
    # First, check if a role exists for Partner
    partner_role_uri = 'http://example.org/nj-legal-ethics#Partner'
    partner_role = Role.query.filter_by(ontology_uri=partner_role_uri, world_id=scenario.world_id).first()
    if not partner_role:
        # Create the role
        partner_role = Role(
            name='Partner',
            description='Attorney with ownership stake in a law firm',
            world_id=scenario.world_id,
            ontology_uri=partner_role_uri,
            tier=3  # Senior level
        )
        db.session.add(partner_role)
        db.session.flush()
    
    # Create the character
    michael = Character(
        name='Michael Reynolds',
        scenario_id=scenario.id,
        role_id=partner_role.id,
        role='Partner',
        attributes={}
    )
    db.session.add(michael)
    db.session.flush()
    
    # Add Conflict of Interest condition
    conflict_condition_uri = 'http://example.org/nj-legal-ethics#ConflictOfInterest'
    conflict_condition_type = ConditionType.query.filter_by(ontology_uri=conflict_condition_uri, world_id=scenario.world_id).first()
    if not conflict_condition_type:
        # Create the condition type
        conflict_condition_type = ConditionType(
            name='Conflict of Interest',
            description='A condition where an attorney\'s interests conflict with client interests',
            world_id=scenario.world_id,
            ontology_uri=conflict_condition_uri,
            category='http://www.w3.org/2002/07/owl#Class'
        )
        db.session.add(conflict_condition_type)
        db.session.flush()
    
    # Create the condition
    michael_condition = Condition(
        character_id=michael.id,
        name='Conflict of Interest',
        description='Representing clients with competing interests',
        severity=8,
        condition_type_id=conflict_condition_type.id
    )
    db.session.add(michael_condition)
    
    # Commit the changes
    db.session.commit()
```

We repeated this process for each character, adjusting the role, name, and conditions as needed.

### Step 5: Verify the Characters

Finally, we verified that all characters were added correctly:

```python
from app import create_app
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.condition import Condition

app = create_app()
with app.app_context():
    # Get the scenario
    scenario = Scenario.query.get(3)
    
    print(f'Scenario: {scenario.name}')
    
    for character in scenario.characters:
        print(f'\n- {character.name} (Role: {character.role})')
        conditions = Condition.query.filter_by(character_id=character.id).all()
        if conditions:
            print('  Conditions:')
            for condition in conditions:
                print(f'  - {condition.name} (Severity: {condition.severity})')
                print(f'    Description: {condition.description}')
        else:
            print('  No conditions')
```

## Character Design Considerations

When designing characters for ethical scenarios, consider the following:

1. **Diverse Perspectives**: Include characters with different roles, backgrounds, and viewpoints to create a rich ethical landscape.

2. **Realistic Conflicts**: Ensure that the characters' interests, responsibilities, and conditions create realistic ethical tensions.

3. **Ethical Complexity**: Design characters whose interactions highlight the complexity of ethical decision-making in the domain.

4. **Role-Appropriate Conditions**: Assign conditions that make sense for each character's role and position in the scenario.

5. **Narrative Coherence**: Ensure that the characters collectively tell a coherent story about the ethical dilemma.

## Conclusion

Adding well-designed characters to scenarios enhances the educational value of the AI Ethical Decision-Making Simulator by creating realistic ethical dilemmas that users can explore. The "Conflict of Interest" scenario example demonstrates how to create a set of characters that collectively represent different aspects of a complex ethical situation in legal practice.
