# Temporal Representation for Timeline Entities

This document outlines the approach for representing timeline entities (events, actions, decisions) using the RDF triple model with temporal components, allowing for effective integration with LangChain/LangGraph via the MCP server.

## Current State

- Timeline entities are currently stored as events, actions, and decision-type actions
- Entity information is represented as triples in the `entity_triples` table
- The table already includes temporal fields based on BFO ontology concepts:
  - `temporal_region_type`: BFO_0000038 (1D temporal region) or BFO_0000148 (0D temporal region)
  - `temporal_start`: Start time for intervals, time point for instants
  - `temporal_end`: End time for intervals, null for instants
  - `temporal_relation_type`: Type of relation (precedes, follows, etc.)
  - `temporal_relation_to`: Related triple ID
  - `temporal_granularity`: Granularity of time measurement (seconds, minutes, etc.)
- A `TemporalContextService` enables operations on these temporal aspects
- The MCP server exposes timeline and temporal data through REST endpoints

## Enhancements Required

### 1. Database Changes

The current `entity_triples` table structure is well-designed for temporal representation, but we should add:

1. **Improved indexing** for temporal queries:
   - Create a composite index on `(scenario_id, temporal_start)` for faster timeline generation
   - Create an index on `(temporal_relation_type, temporal_relation_to)` for relation queries

2. **Additional metadata fields**:
   - Add `temporal_confidence` (float): Confidence level in the temporal information (0.0-1.0)
   - Add `temporal_context` (jsonb): Additional context about the temporal situation

3. **Timeline ordering**:
   - Add `timeline_order` (integer): Explicit ordering value for timeline items when exact timestamps aren't available
   - Add `timeline_group` (string): For grouping related temporal items

### 2. Ontology Changes

The intermediate ontology needs enrichment to better support temporal reasoning for decisions:

1. **Enhanced decision temporal concepts**:
   - Add `DecisionSequence` class for representing a series of related decisions
   - Add `DecisionOption` class to explicitly model decision alternatives
   - Add `DecisionConsequence` class to model outcomes of decisions

2. **Temporal relation properties**:
   - Add more specific causal-temporal relations like `causedBy`, `enabledBy`, `preventedBy`
   - Add qualified temporal relations with context, like `precededByWithGap`

3. **Timeline segmentation concepts**:
   - Add concepts for timeline phases, episodes, and segments
   - Support temporal aggregation of events into meaningful units

4. **Temporal patterns**:
   - Model recurring patterns, cycles, and temporal rules
   - Support conditional temporal structures (if X happens, then Y happens after Z time)

## Implementation Strategy

### Phase 1: Database Enhancements

1. Create a migration script to add new fields and indexes to the `entity_triples` table
2. Update the `EntityTriple` model to include new fields
3. Enhance `TemporalContextService` with methods to leverage the new fields
4. Add indexing function to calculate `timeline_order` for existing triples

### Phase 2: Ontology Extension

1. Extend the intermediate ontology with new temporal classes and properties
2. Add domain-specific temporal concepts for decisions and actions
3. Create mapping functions to translate between database and ontology representations
4. Implement validation rules for temporal consistency

### Phase 3: MCP Server Integration

1. Enhance MCP server with additional temporal endpoints
2. Create specialized endpoints for decision sequence analysis
3. Implement LangChain/LangGraph compatible output formats
4. Add temporal reasoning capabilities to the MCP server

### Phase 4: LangChain/LangGraph Integration

1. Create LangChain custom tools for temporal queries
2. Build LangGraph components for temporal reasoning
3. Implement temporal constraints and validation in flows
4. Create prompt templates that leverage temporal context

## Benefits

This enhanced approach will provide:

1. **Improved temporal reasoning**: Better understanding of the sequence and timing of events
2. **Richer decision modeling**: More detailed representation of decision options and consequences
3. **Contextual awareness**: Ability to reason about what was known at different points in time
4. **Causal analysis**: Understanding of how events and decisions influence each other
5. **Scenario exploration**: Support for "what if" analysis based on temporal modifications

## Example Usage with Claude

With these enhancements, we can provide Claude with rich temporal context like:

```
TIMELINE:
- At t1, Character A observed situation X (EVENT)
- At t2, Character A had to decide between options Y and Z (DECISION)
  - Option Y would lead to consequence Y1 after time Δt1
  - Option Z would lead to consequence Z1 after time Δt2
- At t3, Character A selected option Y (ACTION)
- At t4, Consequence Y1 occurred (EVENT)

TEMPORAL RELATIONSHIPS:
- Decision at t2 was necessitated by observation at t1
- Action at t3 was part of decision at t2
- Consequence at t4 was caused by action at t3
```

This structured temporal context will enable Claude to provide more accurate and contextually appropriate responses based on what information was available at different points in time.
