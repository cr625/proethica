# Temporal Representation for Timeline Entities

## Overview

We've enhanced the timeline entities (events, actions, and decisions) representation in the system to leverage RDF triples with rich temporal components. This will provide better integration with LangChain/LangGraph and enable Claude to understand the temporal relationships and sequences of events.

## Implementation Details

### Database Changes

We've enhanced the `entity_triples` table with:

1. **Additional temporal fields**:
   - `temporal_confidence`: Confidence level in temporal information (0.0-1.0)
   - `temporal_context`: Additional context about the temporal situation (JSONB)
   - `timeline_order`: Explicit ordering value for timeline items
   - `timeline_group`: For grouping related temporal items

2. **Optimized indexes** for faster temporal queries:
   - Composite index on `(scenario_id, temporal_start)`
   - Index on `(temporal_relation_type, temporal_relation_to)`
   - Index on timeline ordering and grouping

3. **SQL functions** for temporal operations:
   - `recalculate_timeline_order`: Automatically orders timeline items
   - `infer_temporal_relationships`: Creates temporal relationships based on timestamps
   - Database trigger to maintain timeline ordering

### Ontology Enhancements

The intermediate ontology has been extended with:

1. **Enhanced decision temporal concepts**:
   - `DecisionSequence`: Series of related decisions
   - `DecisionOption`: Explicitly models decision alternatives
   - `DecisionConsequence`: Models outcomes of decisions
   - `DecisionBranchingPoint`: Points where multiple futures are possible

2. **Timeline segmentation concepts**:
   - `TimelinePhase`: Distinct stages in a scenario
   - `TimelineEpisode`: Self-contained episodes with beginning, middle, and end
   - `TimelineMarker`: Significant points marking transitions

3. **Temporal pattern concepts**:
   - `TemporalPattern`: Recurring patterns across time
   - `TemporalCycle`: Cyclical patterns that repeat
   - `ConditionalTemporalStructure`: Temporal structures based on conditions

4. **Enhanced temporal relations**:
   - Causal relations: `causedBy`, `enabledBy`, `preventedBy`
   - Qualified temporal relations: `precededByWithGap`
   - Probabilistic relations: `hasProbability`

### Service Enhancements

1. **Enhanced temporal context service**:
   - `group_timeline_items`: Groups timeline items by character, temporal gaps, or event type
   - `infer_temporal_relationships`: Automatically creates temporal relationships
   - `recalculate_timeline_order`: Updates the explicit ordering of items
   - `get_enhanced_temporal_context_for_claude`: Provides richer context for Claude

2. **MCP server enhancements**:
   - New endpoints for temporal operations
   - Timeline generation with organized segments
   - Temporal relation inference and querying
   - Enhanced context format for Claude integration

## Integration with LangChain/LangGraph

The enhanced temporal representation can be leveraged in:

1. **LangChain custom tools**:
   - Query timeline events within specific timeframes
   - Find causal relationships between events
   - Explore decision alternatives and their consequences

2. **LangGraph flows**:
   - Create temporal reasoning nodes
   - Implement temporal constraint validation
   - Analyze decision sequences

3. **Claude prompting**:
   - Structure temporal context in prompts
   - Highlight causal relationships
   - Provide organized timeline segments

## Enhanced Temporal Context Example for Claude

```
TIMELINE:
- At t1 [2025-04-03 14:30:00], Engineer A observed structural damage in bridge section 3 (EVENT)
- At t2 [2025-04-03 15:45:00], Engineer A had to decide between immediate closure or limited traffic (DECISION)
  - Option 1 (immediate closure): Would ensure safety but cause major traffic disruption
  - Option 2 (limited traffic): Would allow emergency vehicles but risk further damage
- At t3 [2025-04-03 16:00:00], Engineer A selected immediate closure (ACTION)
- At t4 [2025-04-03 17:30:00], Traffic was redirected to alternate routes (EVENT)

TEMPORAL RELATIONSHIPS:
- Observation at t1 necessitated the decision at t2 (confidence: 0.95)
- Decision at t2 directly led to the action at t3 (confidence: 1.0)
- Action at t3 caused the traffic redirection at t4 (confidence: 0.9)

TIMELINE ORGANIZATION:
Group: Initial Assessment
  - EVENT [2025-04-03 14:30:00]: Engineer A observed structural damage
  - DECISION [2025-04-03 15:45:00]: Engineer A had to decide on bridge access

Group: Response Implementation
  - ACTION [2025-04-03 16:00:00]: Engineer A selected immediate closure
  - EVENT [2025-04-03 17:30:00]: Traffic was redirected to alternate routes
```

## Files Changed

1. Database:
   - `scripts/enhance_entity_triples_temporal.sql`: Added fields and functions

2. Python Models:
   - `app/models/entity_triple.py`: Enhanced with new temporal fields

3. Ontology:
   - `mcp/ontology/proethica-intermediate.ttl`: Added temporal concepts

4. Services:
   - `app/services/temporal_context_service_enhancements.py`: New temporal methods

5. Documentation:
   - `docs/temporal_representation.md`: Technical documentation
   - `scripts/test_temporal_functionality.py`: Test script for the enhancements

## Setup Instructions

Run the setup script to apply all changes:

```bash
./scripts/setup_temporal_enhancements.sh
```

This will:
1. Back up the database
2. Apply database migrations
3. Verify model changes
4. Enhance the services
5. Restart the MCP server
6. Create a test script

## Testing

Test the implementation with:

```bash
python scripts/test_temporal_functionality.py
```

This will verify:
1. EntityTriple model fields
2. TemporalContextService methods
3. Database functions
4. Ontology concepts
