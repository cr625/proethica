# Ontology Agent Data Flow Diagram

This document provides a visual representation of how data flows between components in the ontology agent system.

## Component Architecture

```mermaid
graph TB
    subgraph "Frontend"
        UI[User Interface]
        EntityPanel[Entity Panel]
        ChatPanel[Chat Panel]
        GuidelinesPanel[Guidelines Panel]
    end
    
    subgraph "Backend"
        OntologyAgent[Ontology Agent Routes]
        EnhancedClient[Enhanced MCP Client]
    end
    
    subgraph "Services"
        MCPServer[Enhanced Ontology MCP Server]
        ClaudeService[Claude Service]
        Database[(PostgreSQL Database)]
    end
    
    UI --> |"1. Select World/Ontology"| OntologyAgent
    OntologyAgent --> |"2. Get world's ontology"| Database
    OntologyAgent --> |"3. Load entities"| EnhancedClient
    EnhancedClient --> |"4. JSON-RPC request"| MCPServer
    MCPServer --> |"5. Load ontology"| Database
    MCPServer --> |"6. Return entity data"| EnhancedClient
    EnhancedClient --> |"7. Format entity data"| OntologyAgent
    OntologyAgent --> |"8. Return JSON response"| EntityPanel
    
    UI --> |"9. Send message"| OntologyAgent
    OntologyAgent --> |"10. Get context"| EnhancedClient
    EnhancedClient --> |"11. Multiple queries"| MCPServer
    MCPServer --> |"12. Return ontology data"| EnhancedClient
    EnhancedClient --> |"13. Format context"| OntologyAgent
    OntologyAgent --> |"14. Send with context"| ClaudeService
    ClaudeService --> |"15. Response"| OntologyAgent
    OntologyAgent --> |"16. Return message"| ChatPanel
    
    OntologyAgent --> |"17. Get guidelines"| EnhancedClient
    EnhancedClient --> |"18. Request guidelines"| MCPServer
    MCPServer --> |"19. Return guidelines"| EnhancedClient
    EnhancedClient --> |"20. Format guidelines"| OntologyAgent
    OntologyAgent --> |"21. Return guidelines"| GuidelinesPanel
```

## Key Sequence Flows

### World Selection and Entity Loading

```mermaid
sequenceDiagram
    participant User
    participant UI as Frontend UI
    participant Agent as Ontology Agent
    participant Client as MCP Client
    participant Server as MCP Server
    participant DB as Database
    
    User->>UI: Select world
    UI->>Agent: worldChanged() event
    Agent->>DB: Query world's ontology
    DB->>Agent: Return ontology info
    Agent->>UI: Show world's ontology
    
    UI->>Agent: Request entities
    Agent->>Client: get_entities(ontology_source)
    Client->>Server: JSON-RPC call_tool request
    Server->>DB: Load ontology graph
    DB->>Server: Return ontology data
    Server->>Client: Return entity data
    Client->>Agent: Formatted entity data
    Agent->>UI: JSON response with entities
    UI->>User: Display filtered entities
```

### Entity Interaction and Message Flow

```mermaid
sequenceDiagram
    participant User
    participant UI as Frontend UI
    participant Agent as Ontology Agent
    participant Client as MCP Client
    participant Server as MCP Server
    participant Claude as Claude Service
    
    User->>UI: Click entity
    UI->>User: Show expanded entity details
    
    User->>UI: Send message about entity
    UI->>Agent: POST /api/message
    Agent->>Client: get_entities() for context
    Client->>Server: JSON-RPC request
    Server->>Client: Return entity data
    
    Agent->>Client: search_entities(query)
    Client->>Server: JSON-RPC request
    Server->>Client: Return search results
    
    Agent->>Client: get_ontology_guidelines()
    Client->>Server: JSON-RPC request
    Server->>Client: Return guidelines
    
    Client->>Agent: All ontology context data
    Agent->>Claude: Send message with context
    Claude->>Agent: Response with ontology knowledge
    Agent->>UI: Return Claude's response
    UI->>User: Display message in conversation
```

## Ontology Entity Structure

```mermaid
classDiagram
    class Role {
        +uri: string
        +label: string
        +description: string
        +hasCapability: Capability[]
    }
    
    class Capability {
        +uri: string
        +label: string
        +description: string
    }
    
    class Condition {
        +uri: string
        +label: string
        +description: string
        +severity: number
    }
    
    class Resource {
        +uri: string
        +label: string
        +description: string
    }
    
    class Event {
        +uri: string
        +label: string
        +description: string
    }
    
    class Action {
        +uri: string
        +label: string
        +description: string
    }
    
    Role --> "0..*" Capability : hasCapability
    Role --> "0..*" Condition : hasCondition
    Action --> "0..*" Resource : usesResource
    Event --> "0..*" Role : involves
```

## Error Handling Flow

```mermaid
sequenceDiagram
    participant UI as Frontend UI
    participant Agent as Ontology Agent
    participant Client as MCP Client
    participant Server as MCP Server
    
    UI->>Agent: Request entities
    Agent->>Client: get_entities()
    Client->>Server: JSON-RPC request
    
    alt Server unreachable
        Server--xClient: Connection error
        Client->>Client: Create mock data
        Client->>Agent: Return mock entities
        Agent->>UI: Return entities with warning
    else Server error
        Server->>Client: Error response
        Client->>Client: Log error
        Client->>Agent: Return error with fallback
        Agent->>UI: Display error message
    else Success
        Server->>Client: Return entity data
        Client->>Agent: Return formatted data
        Agent->>UI: Display entities
    end
    
    UI->>UI: Handle response appropriately
```

## Temporal Functionality Flow

```mermaid
sequenceDiagram
    participant User
    participant UI as Frontend UI
    participant Agent as Ontology Agent
    participant Client as MCP Client
    participant Server as MCP Server
    participant Temporal as Temporal Context Service
    
    User->>UI: Ask about event timeline
    UI->>Agent: Send message
    Agent->>Client: Normal context collection
    
    Agent->>Client: Could integrate temporal queries
    Client->>Server: Request to /api/timeline/{scenario_id}
    Server->>Temporal: Build timeline
    Temporal->>Server: Return timeline data
    Server->>Client: Return timeline context
    
    Client->>Agent: Timeline + standard context
    Agent->>UI: Enhanced temporal response
    UI->>User: Display response with timeline context
