# Adding Timeline Items to Scenarios

This document outlines the process for adding timeline items (actions and events) to existing scenarios in the AI Ethical Decision-Making Simulator. It uses the "Conflict of Interest" scenario in the "Legal Ethics World (New Jersey)" as an example.

## Overview

Timeline items are essential components of scenarios in the simulator. They represent the sequence of events and actions that tell the story of the ethical dilemma and provide opportunities for decision-making. A well-designed timeline creates a narrative flow that helps users understand the ethical issues at stake.

## Prerequisites

Before adding timeline items to a scenario, you should:

1. Identify the scenario you want to modify
2. Understand the ethical context and dilemma presented in the scenario
3. Ensure that characters and resources have already been added to the scenario
4. Plan a chronological sequence of events and actions that tell a coherent story

## Types of Timeline Items

There are two main types of timeline items:

1. **Events**: Things that happen in the scenario that characters may respond to. Events provide context and create situations that require ethical decision-making.

2. **Actions**: Things that characters do in response to events or other actions. Actions can be simple actions or decision points with multiple options.

## Example: Adding Timeline Items to "Conflict of Interest" Scenario

### Step 1: Identify the Scenario and Characters

First, we identified the "Conflict of Interest" scenario and the characters we previously added:

```python
from app import create_app
from app.models.scenario import Scenario
from app.models.character import Character

app = create_app()
with app.app_context():
    # Get the scenario
    scenario = Scenario.query.get(3)
    
    # Get characters
    characters = {}
    for character in scenario.characters:
        characters[character.name] = character
```

### Step 2: Explore Available Action and Event Types

Next, we examined the available action and event types in the ontology:

```python
from app import create_app
from app.services.mcp_client import MCPClient
from app.models.world import World

app = create_app()
with app.app_context():
    world = World.query.get(3)
    if world and world.ontology_source:
        mcp_client = MCPClient()
        # Get action types from ontology
        entities = mcp_client.get_world_entities(world.ontology_source, entity_type='actions')
        if entities and 'entities' in entities and 'actions' in entities['entities']:
            actions = entities['entities']['actions']
            print(f'Found {len(actions)} action types in the ontology:')
            for action in actions:
                print(f'- {action.get("label")} (ID: {action.get("id")})')
                
        # Get event types from ontology
        entities = mcp_client.get_world_entities(world.ontology_source, entity_type='events')
        if entities and 'entities' in entities and 'events' in entities['entities']:
            events = entities['entities']['events']
            print(f'Found {len(events)} event types in the ontology:')
            for event in events:
                print(f'- {event.get("label")} (ID: {event.get("id")})')
```

This showed us the available action types (File Motion, Provide Advice, Disclose Conflict, etc.) and event types (Client Meeting, Ethical Dilemma, etc.) that we could use.

### Step 3: Plan the Timeline

For the "Conflict of Interest" scenario, we planned the following timeline:

1. **Initial Client Interview** (Event)
   - Character: Sarah Chen
   - Description: Sarah explains her whistleblower case
   - Event Type: Client Interview

2. **Provide Advice** (Action)
   - Character: Michael Reynolds
   - Description: Michael provides initial legal advice
   - Action Type: Provide Advice

3. **Client Disclosure** (Event)
   - Character: Sarah Chen
   - Description: Sarah provides detailed information
   - Event Type: Client Disclosure

4. **Draft Document** (Action)
   - Character: Jason Martinez
   - Description: Jason drafts a legal brief
   - Action Type: Draft Document

5. **Ethical Dilemma** (Event)
   - Character: Jason Martinez
   - Description: Jason realizes the conflict of interest
   - Event Type: Ethical Dilemma

6. **Disclose Conflict** (Action)
   - Character: Jason Martinez
   - Description: Jason discloses the conflict to Michael
   - Action Type: Disclose Conflict

7. **Seek Ethics Opinion** (Action/Decision)
   - Character: Michael Reynolds
   - Description: Michael consults with Eleanor
   - Action Type: Seek Ethics Opinion
   - Decision Options: Multiple ways to handle the conflict

8. **Client Meeting** (Event)
   - Character: Michael Reynolds
   - Description: Michael meets with Horizon Technologies
   - Event Type: Client Meeting

9. **Withdraw From Case** (Action/Decision)
   - Character: Michael Reynolds
   - Description: Final decision on representation
   - Action Type: Withdraw From Case
   - Decision Options: Multiple ways to resolve the conflict

### Step 4: Add the Timeline Items

We added each timeline item using Python code that interacts with the database:

```python
from app import create_app, db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.event import Event, Action
from datetime import datetime, timedelta

app = create_app()
with app.app_context():
    # Get the scenario
    scenario = Scenario.query.get(3)
    
    # Get characters
    characters = {}
    for character in scenario.characters:
        characters[character.name] = character
    
    # Base date for the timeline
    base_date = datetime.now() - timedelta(days=14)
    
    # Example: Adding an event
    event = Event(
        scenario_id=scenario.id,
        character_id=characters["Sarah Chen"].id,
        event_time=base_date,
        description="Initial client interview with Sarah Chen...",
        parameters={
            'location': "Law firm conference room",
            'duration': "90 minutes"
        }
    )
    db.session.add(event)
    
    # Example: Adding an action
    action = Action(
        name="Initial Legal Advice to Sarah Chen",
        description="Michael Reynolds provides preliminary legal advice...",
        scenario_id=scenario.id,
        character_id=characters["Michael Reynolds"].id,
        action_time=base_date + timedelta(hours=2),
        action_type="http://example.org/nj-legal-ethics#ProvideAdvice",
        parameters={
            'advice_type': "preliminary",
            'legal_areas': ["securities law", "whistleblower protection"]
        },
        is_decision=False
    )
    db.session.add(action)
    
    # Example: Adding a decision point (special type of action)
    decision = Action(
        name="Consult with Managing Partner",
        description="Michael Reynolds consults with Eleanor Washington...",
        scenario_id=scenario.id,
        character_id=characters["Michael Reynolds"].id,
        action_time=base_date + timedelta(days=5),
        action_type="http://example.org/nj-legal-ethics#SeekEthicsOpinion",
        parameters={
            'consultation_type': "internal",
            'ethical_issue': "concurrent client conflict"
        },
        is_decision=True,
        options=[
            "Attempt to get conflict waivers from both clients",
            "Withdraw from representing Sarah Chen",
            "Withdraw from representing Horizon Technologies",
            "Refer Sarah Chen to another law firm"
        ]
    )
    db.session.add(decision)
    
    # Commit the changes
    db.session.commit()
```

### Step 5: Verify the Timeline

Finally, we verified that all timeline items were added correctly:

```python
from app import create_app
from app.models.scenario import Scenario
from app.models.event import Event, Action

app = create_app()
with app.app_context():
    # Get the scenario
    scenario = Scenario.query.get(3)
    
    # Get actions
    actions = Action.query.filter_by(scenario_id=scenario.id).all()
    print(f'Number of actions: {len(actions)}')
    
    for action in sorted(actions, key=lambda x: x.action_time):
        print(f'- Action: {action.name}')
        print(f'  Time: {action.action_time.strftime("%Y-%m-%d %H:%M")}')
        if action.is_decision:
            print(f'  Decision with options: {action.options}')
    
    # Get events
    events = Event.query.filter_by(scenario_id=scenario.id).all()
    print(f'Number of events: {len(events)}')
    
    for event in sorted(events, key=lambda x: x.event_time):
        print(f'- Event at {event.event_time.strftime("%Y-%m-%d %H:%M")}')
        print(f'  Description: {event.description[:100]}...')
```

## Timeline Design Considerations

When designing timeline items for ethical scenarios, consider the following:

1. **Chronological Flow**: Arrange events and actions in a logical chronological sequence that tells a coherent story.

2. **Character Involvement**: Ensure that all key characters have meaningful roles in the timeline.

3. **Resource Integration**: Reference resources that were previously added to the scenario to create a more integrated simulation.

4. **Decision Points**: Include decision points at critical junctures where ethical choices must be made.

5. **Ethical Progression**: Design the timeline to progressively reveal the ethical dilemma and its complexities.

6. **Multiple Perspectives**: Include events and actions that show different perspectives on the ethical issue.

7. **Realistic Timing**: Use realistic time intervals between events and actions.

## Action Types for Legal Ethics Scenarios

In legal ethics scenarios, consider including these types of actions:

1. **Client Representation**: Provide Advice, Draft Document, File Motion
2. **Ethical Actions**: Disclose Conflict, Withdraw From Case, Seek Ethics Opinion
3. **Court Actions**: Present Evidence, Examine Witness, Make Objection
4. **Decision Points**: Key moments where ethical choices must be made

## Event Types for Legal Ethics Scenarios

In legal ethics scenarios, consider including these types of events:

1. **Client Interactions**: Client Meeting, Client Interview, Client Disclosure
2. **Court Events**: Hearing, Trial, Deposition
3. **Ethical Events**: Ethical Dilemma, Ethics Complaint, Disciplinary Review

## Conclusion

Adding well-designed timeline items to scenarios enhances the educational value of the AI Ethical Decision-Making Simulator by creating a narrative flow that helps users understand the ethical dilemma and make informed decisions. The "Conflict of Interest" scenario example demonstrates how to create a sequence of events and actions that collectively tell a compelling story about a complex ethical situation in legal practice.
