# Adding Resources to Scenarios

This document outlines the process for adding resources to existing scenarios in the AI Ethical Decision-Making Simulator. It uses the "Conflict of Interest" scenario in the "Legal Ethics World (New Jersey)" as an example.

## Overview

Resources are essential components of scenarios in the simulator. They represent objects, documents, time, or other assets that characters can use or interact with during the scenario. Well-designed resources add depth and realism to ethical dilemmas.

## Prerequisites

Before adding resources to a scenario, you should:

1. Identify the scenario you want to modify
2. Understand the ethical context and dilemma presented in the scenario
3. Determine what resources would be relevant to the scenario and characters
4. Consider how these resources might influence ethical decision-making

## Example: Adding Resources to "Conflict of Interest" Scenario

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

### Step 2: Explore Available Resource Types

Next, we examined the available resource types in the ontology:

```python
from app import create_app
from app.services.mcp_client import MCPClient
from app.models.world import World

app = create_app()
with app.app_context():
    world = World.query.get(3)
    if world and world.ontology_source:
        mcp_client = MCPClient()
        # Get resource types from ontology
        entities = mcp_client.get_world_entities(world.ontology_source, entity_type='resources')
        if entities and 'entities' in entities and 'resources' in entities['entities']:
            resources = entities['entities']['resources']
            print(f'Found {len(resources)} resource types in the ontology:')
            for resource in resources:
                print(f'- {resource.get("label")} (ID: {resource.get("id")})')
                print(f'  Description: {resource.get("description")}')
```

This showed us the available resource types (Legal Document, Case File, Evidence, etc.) that we could use.

### Step 3: Plan the Resources

For the "Conflict of Interest" scenario, we planned the following resources:

1. **Case File: Horizon Technologies Inc.**
   - Type: Case File
   - Description: Ongoing corporate legal work for Horizon Technologies Inc.
   - Quantity: 1

2. **Case File: Sarah Chen Whistleblower Claim**
   - Type: Case File
   - Description: Potential whistleblower case against Horizon Technologies
   - Quantity: 1

3. **Legal Research: Conflict of Interest Rules**
   - Type: Legal Research
   - Description: Research on ethical obligations regarding conflicts
   - Quantity: 1

4. **Legal Brief: Whistleblower Protections**
   - Type: Legal Brief
   - Description: Draft legal arguments for Sarah's case
   - Quantity: 1

5. **Documentary Evidence: Horizon Technologies Financial Records**
   - Type: Documentary Evidence
   - Description: Financial records relevant to both cases
   - Quantity: 5

6. **Court Time: Upcoming Hearing**
   - Type: Court Time
   - Description: Limited court time that might create scheduling conflicts
   - Quantity: 1

### Step 4: Add the Resources

We added each resource using Python code that interacts with the database:

```python
from app import create_app, db
from app.models.scenario import Scenario
from app.models.resource import Resource
from app.models.resource_type import ResourceType

app = create_app()
with app.app_context():
    # Get the scenario
    scenario = Scenario.query.get(3)
    
    # Example: Adding a Case File resource
    # First, check if a resource type exists for Case File
    case_file_uri = 'http://example.org/nj-legal-ethics#CaseFile'
    resource_type = ResourceType.query.filter_by(ontology_uri=case_file_uri, world_id=scenario.world_id).first()
    if not resource_type:
        # Create the resource type
        resource_type = ResourceType(
            name='Case File',
            description='A file containing case information',
            world_id=scenario.world_id,
            ontology_uri=case_file_uri,
            category='Legal'
        )
        db.session.add(resource_type)
        db.session.flush()
    
    # Create the resource
    resource = Resource(
        name='Horizon Technologies Inc. Case File',
        scenario_id=scenario.id,
        resource_type_id=resource_type.id,
        type='Case File',  # For backward compatibility
        quantity=1,
        description='Ongoing corporate legal work for Horizon Technologies Inc., including contracts, compliance matters, and intellectual property protection.'
    )
    db.session.add(resource)
    
    # Commit the changes
    db.session.commit()
```

We repeated this process for each resource, adjusting the name, type, quantity, and description as needed.

### Step 5: Verify the Resources

Finally, we verified that all resources were added correctly:

```python
from app import create_app
from app.models.scenario import Scenario

app = create_app()
with app.app_context():
    # Get the scenario
    scenario = Scenario.query.get(3)
    
    print(f'Scenario: {scenario.name}')
    print(f'Number of resources: {len(scenario.resources)}')
    
    for resource in scenario.resources:
        print(f'\n- {resource.name} (Type: {resource.type}, Quantity: {resource.quantity})')
        print(f'  Description: {resource.description}')
```

## Resource Design Considerations

When designing resources for ethical scenarios, consider the following:

1. **Relevance to Ethical Dilemma**: Resources should be directly relevant to the ethical dilemma presented in the scenario. For example, in a conflict of interest scenario, include resources that highlight the competing interests.

2. **Character Connections**: Design resources that connect to specific characters in the scenario. This creates a more integrated and realistic simulation.

3. **Scarcity and Limitations**: Consider including resources with limited quantities to create realistic constraints that influence decision-making.

4. **Ethical Implications**: Resources should have clear ethical implications. For example, documents that contain sensitive information or evidence that could be used in multiple ways.

5. **Narrative Support**: Ensure that resources collectively support the narrative of the scenario and provide context for the ethical decisions that need to be made.

## Resource Types for Legal Ethics Scenarios

In legal ethics scenarios, consider including these types of resources:

1. **Case Files**: Representing ongoing legal work for specific clients
2. **Legal Documents**: Contracts, agreements, filings, etc.
3. **Evidence**: Documentary evidence, physical evidence, testimony
4. **Legal Research**: Research on relevant laws, regulations, and precedents
5. **Court Time**: Representing scheduled hearings or trials
6. **Legal Briefs**: Written legal arguments prepared for cases

## Conclusion

Adding well-designed resources to scenarios enhances the educational value of the AI Ethical Decision-Making Simulator by creating realistic constraints and considerations that influence ethical decision-making. The "Conflict of Interest" scenario example demonstrates how to create a set of resources that collectively represent different aspects of a complex ethical situation in legal practice.
