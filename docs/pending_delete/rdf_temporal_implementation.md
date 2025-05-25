# RDF Triple and Temporal Implementation

This document details the RDF triple-based data structure and temporal representation implementation in ProEthica.

## Overview

ProEthica uses a unified RDF triple-based data structure for storing entity data and relationships, with enhanced temporal capabilities that allow representation of entity states and relationships over time. This approach enables:

- Unified graph-based representation of all entity types
- Temporal reasoning about ethical scenarios and decisions
- Complex relationship traversal across different entity types
- Semantic queries about ethical principles and cases
- Integration with standard RDF tools and formats

## RDF Triple-Based Data Structure

### Implementation

Transitioned to using RDF triples to store entity details (characters, actions, events, resources) as instances of classes in domain-specific ontologies:

1. **Unified Entity Triples Table**:
   - Polymorphic entity references using entity_type and entity_id fields
   - Support for all entity types in a single table
   - Proper indexing for efficient querying
   - Maintained pgvector integration for semantic similarity search

2. **Ontological Relationships and Namespaces**:
   - PROETHICA: Base ontology
   - ENG_ETHICS: Engineering ethics concepts
   - NSPE/IEEE: Specific engineering ethics codes
   - Additional namespaces for actions, events, and resources

3. **Entity Triple Structure**:
   - **Subject**: The entity (e.g., a character, event, action, or resource)
   - **Predicate**: The relationship or property (e.g., hasRole, participatesIn)
   - **Object**: The target entity or literal value
   - **Graph**: Optional named graph for contextual organization

4. **EntityTripleService**:
   - Comprehensive service for working with entity triples
   - Methods to convert different entity types to triples
   - SPARQL-like query functionality
   - Entity synchronization capabilities

## Temporal Enhancement

### Implementation Details

The RDF triple-based data structure has been enhanced with rich temporal components to better represent timeline entities (events, actions, and decisions):

1. **Additional Temporal Fields**:
   - `valid_from` and `valid_to`: Time period during which the triple is valid
   - `temporal_confidence`: Confidence level in temporal information (0.0-1.0)
   - `temporal_context`: Additional context about the temporal situation (JSONB)
   - `timeline_order`: Explicit ordering value for timeline items
   - `timeline_group`: For grouping related temporal items

2. **Optimized Indexes** for faster temporal queries:
   - Composite index on `(scenario_id, temporal_start)`
   - Index on `(temporal_relation_type, temporal_relation_to)`
   - Index on timeline ordering and grouping

3. **SQL Functions** for temporal operations:
   - `recalculate_timeline_order`: Automatically orders timeline items
   - `infer_temporal_relationships`: Creates temporal relationships based on timestamps
   - Database trigger to maintain timeline ordering

### Ontology Enhancements

The intermediate ontology has been extended with temporal concepts:

1. **Enhanced Decision Temporal Concepts**:
   - `DecisionSequence`: Series of related decisions
   - `DecisionOption`: Explicitly models decision alternatives
   - `DecisionConsequence`: Models outcomes of decisions
   - `DecisionBranchingPoint`: Points where multiple futures are possible

2. **Timeline Segmentation Concepts**:
   - `TimelinePhase`: Distinct stages in a scenario
   - `TimelineEpisode`: Self-contained episodes with beginning, middle, and end
   - `TimelineMarker`: Significant points marking transitions

3. **Temporal Pattern Concepts**:
   - `TemporalPattern`: Recurring patterns across time
   - `TemporalCycle`: Cyclical patterns that repeat
   - `ConditionalTemporalStructure`: Temporal structures based on conditions

4. **Enhanced Temporal Relations**:
   - Causal relations: `causedBy`, `enabledBy`, `preventedBy`
   - Qualified temporal relations: `precededByWithGap`
   - Probabilistic relations: `hasProbability`

## Temporal Context Service

The `TemporalContextService` provides methods for working with temporal aspects of entities:

1. **Timeline Operations**:
   - `group_timeline_items`: Groups timeline items by character, temporal gaps, or event type
   - `infer_temporal_relationships`: Automatically creates temporal relationships
   - `recalculate_timeline_order`: Updates the explicit ordering of items

2. **Context Generation**:
   - `get_enhanced_temporal_context_for_claude`: Provides richer context for Claude
   - Organizes timeline items into coherent groups
   - Includes temporal relationship information
   - Adds confidence levels for relationships

## Integration with LangChain/LangGraph

The enhanced temporal representation can be leveraged in:

1. **LangChain Custom Tools**:
   - Query timeline events within specific timeframes
   - Find causal relationships between events
   - Explore decision alternatives and their consequences

2. **LangGraph Flows**:
   - Create temporal reasoning nodes
   - Implement temporal constraint validation
   - Analyze decision sequences

3. **Claude Prompting**:
   - Structure temporal context in prompts
   - Highlight causal relationships
   - Provide organized timeline segments

## Example of Enhanced Temporal Context

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

## Benefits

1. **Unified Knowledge Graph**: All entity types represented in a unified graph structure
2. **Temporal Reasoning**: System can represent and query the state of entities at any point in time
3. **RDF Integration**: Data can be exchanged with external RDF/SPARQL systems
4. **Powerful Queries**: Complex graph queries across different entity types
5. **Future Extensibility**: Foundation for inference rules and reasoning in future phases
6. **Improved Simulation**: Better representation of scenario timelines and character states
7. **Contextual Awareness**: Reasoning about what was known at different times
8. **Causal Analysis**: Understanding how events and decisions influence each other

## Implementation Files

### Database & Models
- `scripts/enhance_entity_triples_temporal.sql`: Added fields and functions for temporal representation
- `app/models/entity_triple.py`: EntityTriple model enhanced with temporal fields
- `scripts/add_temporal_fields_to_triples.py`: Script to add temporal capabilities

### Services
- `app/services/entity_triple_service.py`: Comprehensive entity triple service
- `app/services/temporal_context_service.py`: Service for timeline and temporal operations
- `app/services/rdf_serialization_service.py`: RDF import/export service

### Setup and Testing
- `scripts/setup_temporal_enhancements.sh`: Complete installation script
- `scripts/verify_temporal_fields.py`: Verification script
- `scripts/test_temporal_functionality.py`: Test script for temporal features
- `scripts/test_entity_triple_service.py`: Test script for EntityTripleService
- `scripts/test_rdf_serialization.py`: Test script for RDF serialization

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
