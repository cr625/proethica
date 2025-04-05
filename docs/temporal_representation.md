# Temporal Representation in ProEthica

This document describes the BFO-based temporal representation system implemented in ProEthica for timeline entities (events, actions, and decisions).

## Overview

ProEthica now uses a sophisticated temporal representation system based on the Basic Formal Ontology (BFO) to represent timeline entities with precise temporal properties. This enhancement enables:

1. **Temporal Queries**: Search for events that occurred within specific timeframes
2. **Timeline Sequencing**: Generate ordered timelines for scenarios
3. **Temporal Reasoning**: Infer causal relationships and consequences based on temporal ordering
4. **Context Generation**: Create rich temporal context for Claude to understand event sequences

## BFO Temporal Concepts

The system leverages BFO's temporal region concepts:

- **Zero-dimensional Temporal Regions** (BFO_0000148): Represent instantaneous events or decision points
- **One-dimensional Temporal Regions** (BFO_0000038): Represent intervals with duration, like actions that take time to complete
- **Temporal Boundaries** (BFO_0000011): Represent the start or end of temporal regions

Temporal relationships between entities use BFO-aligned properties:

- **temporallyPrecedes**: Entity A occurs before Entity B
- **temporallyFollows**: Entity A occurs after Entity B
- **temporallyCoincidesWith**: Entities occur at the same time
- **temporallyOverlaps**: Temporal regions have an overlapping period
- **temporallyNecessitates**: An event creates the need for a decision
- **hasTemporalConsequence**: Relates a decision to resulting events

## Database Schema

The `EntityTriple` model has been enhanced with temporal fields:

```python
# BFO-based temporal fields
temporal_region_type = db.Column(String(255))  # BFO_0000038 (1D) or BFO_0000148 (0D)
temporal_start = db.Column(DateTime)           # Start time for intervals, time point for instants
temporal_end = db.Column(DateTime)             # End time for intervals, None for instants
temporal_relation_type = db.Column(String(50)) # precedes, follows, etc.
temporal_relation_to = db.Column(Integer)      # Related triple
temporal_granularity = db.Column(String(50))   # seconds, minutes, days, etc.
```

## Services

### TemporalContextService

A new service provides methods for working with temporal aspects of entities:

```python
from app.services.temporal_context_service import TemporalContextService

# Initialize
temporal_service = TemporalContextService()

# Find events in a timeframe
events = temporal_service.find_triples_in_timeframe(
    start_time=datetime(2025, 4, 1),
    end_time=datetime(2025, 4, 5),
    entity_type='event',
    scenario_id=1
)

# Find events in temporal sequence
sequence = temporal_service.find_temporal_sequence(scenario_id=1)

# Build a timeline
timeline = temporal_service.build_timeline(scenario_id=1)

# Generate context for Claude
context = temporal_service.get_temporal_context_for_claude(scenario_id=1)
```

### Enhanced EntityTripleService

The `EntityTripleService` has been updated to automatically add temporal data to entity triples:

```python
# When creating events
event_triples = entity_triple_service.event_to_triples(event)

# When creating actions
action_triples = entity_triple_service.action_to_triples(action)

# When creating decisions (special case of actions)
decision_triples = entity_triple_service.action_to_triples(decision)
```

## MCP Server Integration

The HTTP ontology MCP server has been enhanced with temporal endpoints:

- `/api/timeline/<scenario_id>`: Get a complete timeline for a scenario
- `/api/temporal_context/<scenario_id>`: Get temporal context formatted for Claude
- `/api/events_in_timeframe`: Find events within a specific timeframe
- `/api/temporal_sequence/<scenario_id>`: Get events in temporal order
- `/api/temporal_relation/<triple_id>`: Get related triples by temporal relation
- `/api/create_temporal_relation`: Create a temporal relation between triples

## Usage Examples

### Creating a Timeline

```python
# Create events with temporal data
event1 = Event(
    scenario_id=1,
    character_id=1,
    event_time=datetime(2025, 4, 1, 9, 0, 0),
    description="Project kickoff meeting"
)
db.session.add(event1)

# Create actions with temporal data
action1 = Action(
    scenario_id=1,
    character_id=1,
    action_time=datetime(2025, 4, 1, 14, 0, 0),
    name="Safety inspection",
    description="Engineer performs safety inspection of the building"
)
db.session.add(action1)

# Create a decision with temporal data
decision1 = Action(
    scenario_id=1,
    character_id=1,
    action_time=datetime(2025, 4, 2, 10, 0, 0),
    name="Report safety violations",
    description="Engineer decides whether to report safety violations",
    is_decision=True,
    options={
        "report": {
            "description": "Report violations to authorities",
            "ethical_principles": ["integrity", "public_safety"]
        },
        "inform_client": {
            "description": "Inform client only",
            "ethical_principles": ["confidentiality", "client_service"]
        }
    },
    selected_option="report"
)
db.session.add(decision1)
db.session.commit()

# Convert to triples with temporal data
triple_service = EntityTripleService()
temporal_service = TemporalContextService()

event_triples = triple_service.event_to_triples(event1)
action_triples = triple_service.action_to_triples(action1)
decision_triples = triple_service.action_to_triples(decision1)

# Add duration to action (it takes 2 hours)
temporal_service.enhance_action_with_temporal_data(
    action_id=action1.id,
    action_time=action1.action_time,
    duration_minutes=120,
    is_decision=False
)

# Create temporal relationships
temporal_service.create_temporal_relation(
    event_triples[0].id,
    action_triples[0].id,
    "precedes"
)

temporal_service.create_temporal_relation(
    action_triples[0].id,
    decision_triples[0].id,
    "precedes"
)
```

### Querying Timeline Data

```python
# Get all events in the morning of April 1st
morning_events = temporal_service.find_triples_in_timeframe(
    start_time=datetime(2025, 4, 1, 8, 0, 0),
    end_time=datetime(2025, 4, 1, 12, 0, 0),
    entity_type='event',
    scenario_id=1
)

# Get the complete timeline for a scenario
timeline = temporal_service.build_timeline(scenario_id=1)

# Get the temporal context for Claude
context = temporal_service.get_temporal_context_for_claude(scenario_id=1)
```

## Integration with LangChain/LangGraph

When using the MCP server with Claude, you can now include temporal context:

```python
# Example pseudocode for Claude integration
async def get_ethical_analysis(scenario_id):
    # Get the timeline data
    timeline_data = await fetch('/api/timeline/' + scenario_id)
    
    # Get the temporal context for Claude
    temporal_context = await fetch('/api/temporal_context/' + scenario_id)
    
    # Create a prompt with temporal context
    prompt = f"""
    Scenario: {scenario.description}
    
    Timeline:
    {temporal_context}
    
    Analyze the ethical implications of the engineer's decisions in this scenario,
    considering the temporal sequence of events and the consequences that followed.
    """
    
    # Send to Claude
    response = await claude.complete(prompt)
    return response
```

## Setup and Testing

To set up and test the temporal enhancements:

```bash
# Run the setup script
./scripts/setup_temporal_enhancements.sh

# Test temporal functionality
python scripts/test_temporal_functionality.py

# Restart the MCP server to enable temporal endpoints
./scripts/restart_mcp_server.sh
