# MCP Server Integration with Ontology Agent

This document describes the detailed communication flow between the Model Context Protocol (MCP) server and the ontology agent interface in the ProEthica system.

## Architecture Overview

```
┌────────────────┐      ┌────────────────┐      ┌────────────────┐      ┌────────────────┐
│                │      │                │      │                │      │                │
│   User         │◄────►│  Ontology      │◄────►│  Enhanced      │◄────►│  MCP Server    │
│   Interface    │      │  Agent         │      │  MCP Client    │      │                │
│                │      │                │      │                │      │                │
└────────────────┘      └────────────────┘      └────────────────┘      └────────────────┘
```

## Components

### 1. Ontology Agent UI (`app/templates/ontology_agent_window.html`)

The frontend interface that provides:
- World and ontology selection
- Entity browsing with filtering by type
- In-place entity details expansion
- Conversation interface with Claude
- Guidelines display
- Collapsible panels for better screen utilization

### 2. Ontology Agent Backend (`app/routes/ontology_agent.py`)

Flask routes that handle:
- Initializing the ontology agent window
- Processing user messages
- Retrieving ontology entities
- Mapping worlds to ontologies
- Generating suggestions based on ontology content
- Managing conversation flow and state

### 3. Enhanced MCP Client (`app/services/enhanced_mcp_client.py`)

Interface layer that:
- Provides simplified access to MCP server capabilities
- Handles error conditions with graceful fallbacks
- Formats ontology data for context injection
- Implements singleton pattern for client management

### 4. MCP Server (`mcp/enhanced_ontology_mcp_server.py`)

Backend service that:
- Loads ontologies from database or files
- Exposes ontology tools via HTTP JSON-RPC 2.0 
- Processes ontology queries and requests
- Provides temporal reasoning capabilities (via `add_temporal_functionality.py`)

## Communication Flow

### 1. World/Ontology Selection

When a user selects a world or ontology:

1. **Frontend**: User selects a world from the dropdown
2. **Frontend → Backend**: 
   - AJAX request to `/agent/ontology/api/world-ontology?world_id={id}`
3. **Backend**:
   - Queries database for world's ontology information
   - Returns ontology name and ID
4. **Frontend**:
   - Displays ontology name and disables manual ontology selection
   - Makes AJAX request to load entities
   - Makes AJAX request to load guidelines

### 2. Entity Loading

To display ontology entities:

1. **Frontend → Backend**: 
   - AJAX request to `/agent/ontology/api/entities?world_id={id}`
2. **Backend → MCP Client**:
   - Calls `mcp_client.get_entities(ontology_source, entity_type)`
3. **MCP Client → MCP Server**:
   - Sends JSON-RPC request to `/jsonrpc` endpoint with `call_tool` method
   - Parameters include `ontology_source` and `entity_type`
4. **MCP Server**:
   - Loads ontology graph based on source ID
   - Extracts entities of specified type
   - Returns formatted entity data
5. **Backend → Frontend**:
   - Sends entity data as JSON response
6. **Frontend**:
   - Displays entities in left panel
   - Implements filtering by entity type
   - Enables entity selection and detail viewing

### 3. Entity Details

When a user clicks on an entity:

1. **Frontend**:
   - Marks selected entity
   - Expands in-place details view under the entity
   - Shows entity description, IRI link, and action buttons
2. **Frontend → Backend**: (optional for more details)
   - Could make additional API calls for more comprehensive entity information
3. **Backend → MCP Client**:
   - Would call `mcp_client.get_entity_details(ontology_source, entity_uri)`
4. **MCP Client → MCP Server**:
   - Would make JSON-RPC request for detailed entity information
5. **Frontend**:
   - Displays expanded entity details including:
     - Description
     - IRI link
     - "Ask About This Entity" button

### 4. Sending a Message

When the user sends a message about the ontology:

1. **Frontend → Backend**:
   - POST request to `/agent/ontology/api/message`
   - Includes message text, world_id, ontology_id
2. **Backend**:
   - Gets conversation from session
   - Updates metadata with world_id and ontology_id
   - Gets application context for Claude
3. **Backend → MCP Client**:
   - Calls `mcp_client.get_entities()` for various entity types
   - Calls `mcp_client.get_ontology_guidelines()`
   - Calls `mcp_client.search_entities()` based on user's message
4. **MCP Client → MCP Server**:
   - Makes multiple JSON-RPC requests to gather ontology data
5. **Backend**:
   - Formats ontology context for Claude
   - Adds specific guidance for the ontology agent
   - Sends to Claude with enhanced context
6. **Backend → Frontend**:
   - Returns Claude's response
7. **Frontend**:
   - Displays message in conversation
   - Generates new prompt suggestions
   - Scrolls to bottom of conversation

### 5. Generating Suggestions

For interactive prompt suggestions:

1. **Frontend → Backend**:
   - POST request to `/agent/ontology/api/suggestions`
   - Includes world_id and ontology_id
2. **Backend → MCP Client**:
   - Calls `mcp_client.get_entities()` to understand available entities
   - Calls `mcp_client.get_ontology_guidelines()` to check for guidelines
3. **Backend → Frontend**:
   - Returns context-aware prompt suggestions based on ontology content
4. **Frontend**:
   - Displays clickable prompt suggestions that user can select

## Error Handling and Fallbacks

The system implements robust error handling throughout the communication flow:

1. **MCP Client Fallbacks**:
   - If MCP server is unreachable, generates mock data for entities
   - Formats error messages in a user-friendly way
   - Implements timeout handling to prevent UI blocking
   - Preserves essential functionality even during failures

2. **Frontend Error Handling**:
   - Shows loading indicators during AJAX requests
   - Displays appropriate messages for no entities or connection issues
   - Prevents UI locks during processing
   - Handles unreliable network conditions gracefully

3. **Backend Protection**:
   - Validates all input parameters
   - Handles exceptions during MCP communication
   - Provides meaningful error responses to the frontend
   - Logs errors for troubleshooting

## Temporal Functionality Integration

The temporal functionality added by `add_temporal_functionality.py` extends the MCP server to provide time-based reasoning:

1. **Timeline Access**:
   - Claude can request timeline data for ethical scenarios
   - The ontology agent can include temporal context in its responses
   - Users can ask questions about the sequence of events

2. **Timeframe Analysis**:
   - Enables filtering entities and events by time periods
   - Supports questions about what happened during specific timeframes
   - Allows temporal comparison between different scenario phases

3. **Temporal Relations**:
   - Helps Claude understand causal relationships based on temporal ordering
   - Supports reasoning about precedence and consequence
   - Models "before," "after," and "during" relationships between events

## Implementation Notes

1. **Singleton Pattern**:
   - Both `EnhancedMCPClient` and the base `MCPClient` use singleton patterns
   - This ensures consistent server connections throughout the application
   - Prevents duplicate connections and resource waste

2. **JSON-RPC 2.0 Protocol**:
   - The MCP client communicates with the MCP server using JSON-RPC 2.0
   - Requests include a method name, parameters, and a request ID
   - Responses contain either a result or an error object

3. **Context Formatting**:
   - The MCP client includes methods to format ontology data for LLM context
   - `format_entity_for_context()` converts entity details into readable text
   - `format_relationships_for_context()` explains entity connections
   - `format_guidelines_for_context()` structures guideline information

4. **Modal UI Design**:
   - The ontology agent UI implements a three-panel design:
     - Left: Entity browser with filtering
     - Center: Conversation with Claude
     - Right: Guidelines display
   - Panels can be collapsed to optimize screen space

## Future Enhancements

1. **Real-time Entity Graph Visualization**:
   - Add interactive graph visualization for ontology relationships
   - Show connections between selected entity and related entities
   - Support zooming and exploration of the ontology structure

2. **Enhanced Entity Search**:
   - Implement more sophisticated entity search and filtering
   - Add natural language queries for finding specific entity types
   - Support semantic similarity search for related concepts

3. **Collaborative Ontology Exploration**:
   - Enable saving and sharing of ontology exploration sessions
   - Allow annotating entities with user comments
   - Support collaborative learning about ontology structures

4. **Query Builder Interface**:
   - Provide a visual SPARQL query builder
   - Allow saving common queries for reuse
   - Support importing/exporting SPARQL queries

5. **Context Window Optimization**:
   - Implement smarter selection of which ontology data to include in context
   - Use embedding-based relevance scoring to prioritize entities
   - Support multi-turn memory of which ontology sections have been discussed
