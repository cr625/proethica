# ProEthica Technical Overview

## System Architecture

ProEthica implements a layered architecture with clear separation of concerns:

```mermaid
graph TD
    UI[User Interface] --> Routes[Route Controllers]
    Routes --> Services[Service Layer]
    Services --> Models[Data Models]
    Models --> DB[(PostgreSQL Database)]
    
    Services --> LLM[LLM Service]
    Services --> Agents[Agent System]
    Services --> Embedding[Embedding Service]
    Services --> MCP[MCP Client]
    Services --> EntityMgr[Entity Manager]
    
    LLM --> Claude[Claude API]
    Agents --> AgentOrch[Agent Orchestrator]
    AgentOrch --> Guidelines[Guidelines Agent]
    Embedding --> Vector[(Vector Database)]
    MCP --> OntologyServer[Ontology MCP Server]
    EntityMgr --> Models
```

## Data Models

### Core Domain Models

```mermaid
classDiagram
    World "1" -- "*" Scenario
    World "1" -- "*" Document
    Scenario "1" -- "*" Character
    Scenario "1" -- "*" Resource
    Scenario "1" -- "*" Event
    Scenario "1" -- "*" Action
    Character "1" -- "*" Condition
    Event "*" -- "1" Action
    Document "1" -- "*" DocumentChunk
    
    class World {
        +id: Integer
        +name: String
        +description: Text
        +ontology_source: String
        +cases: JSON
        +rulesets: JSON
        +world_metadata: JSON
    }
    
    class Scenario {
        +id: Integer
        +name: String
        +description: Text
        +world_id: Integer
        +scenario_metadata: JSON
    }
    
    class Character {
        +id: Integer
        +scenario_id: Integer
        +name: String
        +role_id: Integer
        +attributes: JSON
    }
    
    class Event {
        +id: Integer
        +scenario_id: Integer
        +character_id: Integer
        +action_id: Integer
        +event_time: DateTime
        +description: Text
        +parameters: JSON
    }
    
    class Action {
        +id: Integer
        +name: String
        +description: Text
        +scenario_id: Integer
        +character_id: Integer
        +action_time: DateTime
        +parameters: JSON
        +is_decision: Boolean
        +options: JSON
        +selected_option: String
    }
    
    class Document {
        +id: Integer
        +title: Text
        +source: Text
        +document_type: Text
        +world_id: Integer
        +file_path: Text
        +content: Text
        +processing_status: String
        +processing_progress: Integer
    }
    
    class DocumentChunk {
        +id: Integer
        +document_id: Integer
        +chunk_index: Integer
        +chunk_text: Text
        +embedding: Vector
    }
```

## Key Processes

### 1. Simulation Flow

```mermaid
sequenceDiagram
    participant User
    participant SimController as Simulation Controller
    participant AgentOrch as Agent Orchestrator
    participant Guidelines as Guidelines Agent
    participant Claude as Claude API
    
    User->>SimController: Start Simulation
    SimController->>SimController: Initialize State
    SimController->>User: Welcome Message
    
    loop For Each Timeline Item
        User->>SimController: Advance Simulation
        SimController->>SimController: Get Current Item
        
        alt Is Decision Point
            SimController->>AgentOrch: Process Decision
            AgentOrch->>Guidelines: Analyze Decision
            Guidelines->>Claude: Query Guidelines
            Claude->>Guidelines: Guidelines Analysis
            Guidelines->>AgentOrch: Analysis Results
            AgentOrch->>Claude: Synthesize Results
            Claude->>AgentOrch: Final Evaluation
            AgentOrch->>SimController: Decision Evaluation
            SimController->>User: Present Decision Options
            User->>SimController: Select Option
            SimController->>SimController: Update State
            SimController->>User: Decision Outcome
        else Regular Event/Action
            SimController->>User: Present Event/Action
        end
    end
    
    SimController->>User: Simulation Complete
```

### 2. Document Processing Pipeline

```mermaid
flowchart TD
    Upload[Document Upload] --> Extract[Text Extraction]
    Extract --> Chunk[Text Chunking]
    Chunk --> Embed[Generate Embeddings]
    Embed --> Store[Store in Vector DB]
    Store --> Index[Index for Search]
    
    subgraph "Asynchronous Processing"
        Extract
        Chunk
        Embed
        Store
        Index
    end
    
    Index --> Search[Semantic Search]
    Search --> Retrieve[Retrieve Relevant Chunks]
    Retrieve --> Agent[Agent Analysis]
```

### 3. Agent Orchestration

```mermaid
flowchart LR
    Decision[Decision Point] --> Orchestrator[Agent Orchestrator]
    
    Orchestrator --> Guidelines[Guidelines Agent]
    Orchestrator --> Future1[Future Agent 1]
    Orchestrator --> Future2[Future Agent 2]
    
    Guidelines --> GuidelinesAnalysis[Guidelines Analysis]
    Future1 --> Analysis1[Analysis 1]
    Future2 --> Analysis2[Analysis 2]
    
    GuidelinesAnalysis --> Synthesis[Synthesis]
    Analysis1 --> Synthesis
    Analysis2 --> Synthesis
    
    Synthesis --> Evaluation[Final Evaluation]
```

## Technical Components

### 1. Simulation Controller

The `SimulationController` manages the simulation state and flow:

- **State Management**: Tracks current position in timeline, character states, and decisions
- **Timeline Processing**: Handles events and actions sequentially
- **Decision Handling**: Processes decision points with agent evaluation
- **Claude Integration**: Uses Claude for natural language generation
- **State Persistence**: Stores simulation state for resumption

### 2. Agent Orchestrator

The `AgentOrchestrator` coordinates specialized agents:

- **Task Distribution**: Assigns analysis tasks to appropriate agents
- **Result Collection**: Gathers analyses from multiple agents
- **Synthesis**: Combines agent outputs into comprehensive evaluation
- **Status Tracking**: Provides progress updates during processing

### 3. Embedding Service

The `EmbeddingService` handles document processing:

- **Text Extraction**: Processes various document formats
- **Chunking**: Splits documents into manageable segments
- **Embedding Generation**: Creates vector representations
- **Similarity Search**: Finds relevant document chunks
- **PGVector Integration**: Uses PostgreSQL vector extension

### 4. Entity Manager

The `EntityManager` utility provides a centralized system for managing scenario entities:

- **Character Management**: Creates and updates characters with roles and conditions
- **Resource Management**: Handles resource creation with appropriate types
- **Timeline Creation**: Builds events and actions with proper relationships
- **Scenario Creation**: Creates complete scenarios from structured data
- **Ontology Integration**: Populates entity types from ontology files

The Entity Manager simplifies entity creation through high-level functions:

```python
# Creating a new scenario with all entities
scenario_id = create_ethical_scenario(
    world_name="Engineering Ethics",
    scenario_name="Bridge Safety Dilemma",
    scenario_description="A structural engineer discovers potential safety issues...",
    characters={...},
    resources=[...],
    timeline={...}
)

# Creating or updating individual entities
character = create_or_update_character(scenario_id, "Jane Smith", "Attorney", ...)
resource = create_or_update_resource(scenario_id, "Legal Brief", "Document", ...)
event = create_timeline_event(scenario_id, "Client meeting", ...)
action = create_timeline_action(scenario_id, "Ethical Decision", ..., is_decision=True)
```

The utility also includes a consolidated script (`scripts/populate_entities.py`) for command-line operations:

```bash
# Populate entity types from ontology
python scripts/populate_entities.py --world "Engineering Ethics" --ontology

# Add test timeline items to a scenario
python scripts/populate_entities.py --scenario 1 --test-timeline
```

### 5. MCP Integration

The Model Context Protocol integration provides:

- **Ontology Access**: Retrieves domain-specific entity definitions
- **External Tool Integration**: Connects to specialized tools
- **Extensibility**: Allows adding new capabilities

## Database Schema

```mermaid
erDiagram
    WORLDS {
        int id PK
        string name
        text description
        string ontology_source
        json cases
        json rulesets
        json world_metadata
    }
    
    SCENARIOS {
        int id PK
        string name
        text description
        int world_id FK
        json scenario_metadata
    }
    
    CHARACTERS {
        int id PK
        int scenario_id FK
        string name
        int role_id FK
        json attributes
    }
    
    EVENTS {
        int id PK
        int scenario_id FK
        int character_id FK
        int action_id FK
        datetime event_time
        text description
        json parameters
    }
    
    ACTIONS {
        int id PK
        string name
        text description
        int scenario_id FK
        int character_id FK
        datetime action_time
        json parameters
        boolean is_decision
        json options
        string selected_option
    }
    
    DOCUMENTS {
        int id PK
        text title
        text source
        text document_type
        int world_id FK
        text file_path
        text content
        string processing_status
        int processing_progress
    }
    
    DOCUMENT_CHUNKS {
        int id PK
        int document_id FK
        int chunk_index
        text chunk_text
        vector embedding
    }
    
    WORLDS ||--o{ SCENARIOS : contains
    WORLDS ||--o{ DOCUMENTS : contains
    SCENARIOS ||--o{ CHARACTERS : contains
    SCENARIOS ||--o{ EVENTS : contains
    SCENARIOS ||--o{ ACTIONS : contains
    CHARACTERS ||--o{ EVENTS : participates
    ACTIONS ||--o{ EVENTS : triggers
    DOCUMENTS ||--o{ DOCUMENT_CHUNKS : split_into
```

## API Endpoints

### World Management
- `GET /worlds` - List all worlds
- `GET /worlds/<id>` - Get world details
- `POST /worlds` - Create a new world
- `PUT /worlds/<id>` - Update a world
- `DELETE /worlds/<id>` - Delete a world

### Scenario Management
- `GET /scenarios` - List all scenarios
- `GET /scenarios/<id>` - Get scenario details
- `POST /scenarios` - Create a new scenario
- `PUT /scenarios/<id>` - Update a scenario
- `DELETE /scenarios/<id>` - Delete a scenario

### Simulation
- `POST /simulation/start/<scenario_id>` - Start a simulation
- `POST /simulation/advance/<session_id>` - Advance to next step
- `POST /simulation/decide/<session_id>` - Make a decision
- `GET /simulation/state/<session_id>` - Get simulation state

### Document Management
- `POST /documents/upload` - Upload a document
- `GET /documents/<id>` - Get document details
- `GET /documents/search` - Search documents

## Technology Stack

- **Backend Framework**: Flask
- **Database**: PostgreSQL with pgvector extension
- **ORM**: SQLAlchemy
- **Authentication**: Flask-Login
- **LLM Integration**: Anthropic Claude API
- **Agent Framework**: LangChain, LangGraph
- **Vector Embeddings**: all-MiniLM-L6-v2 (384-dimensional)
- **Extension Protocol**: Model Context Protocol (MCP)
- **Document Processing**: Various libraries for text extraction
- **Frontend**: Bootstrap, JavaScript

## Deployment Architecture

```mermaid
flowchart TD
    Client[Web Browser] <--> WebServer[Web Server]
    WebServer <--> App[Flask Application]
    App <--> DB[(PostgreSQL)]
    App <--> Claude[Claude API]
    App <--> MCP[MCP Server]
    App <--> Zotero[Zotero API]
    
    subgraph "Server Environment"
        WebServer
        App
        DB
        MCP
    end
```
