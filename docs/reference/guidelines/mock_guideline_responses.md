# Mock Guideline Response System

This document provides instructions for using the mock response system for guideline concept extraction. The system allows developers to test the concept extraction flow without making actual API calls to Claude, significantly speeding up development and testing.

## Overview

The mock response system:
- Replaces Claude API calls with pre-loaded concept data
- Speeds up development by eliminating the ~30-second wait for concept extraction
- Allows for rapid testing of the UI and concept saving functionality
- Uses standard JSON files for mock data configuration

## Enabling Mock Responses

There are two ways to enable mock responses:

### 1. Using the debug script

The simplest way is to use the provided debug script:

```bash
./debug_with_mock_guidelines.sh
```

This script:
- Sets the `USE_MOCK_GUIDELINE_RESPONSES` environment variable to `true`
- Detects your environment (Codespaces, WSL, or standard development)
- Checks and starts the PostgreSQL container if not already running
- Verifies database connectivity using pg_isready
- Provides colorized instructions for launching the servers
- Offers to start the MCP server directly from the script

### 2. Setting the environment variable manually

You can also set the environment variable manually before starting servers:

```bash
export USE_MOCK_GUIDELINE_RESPONSES=true
python mcp/run_enhanced_mcp_server_with_guidelines.py --port 5001
```

And in another terminal:

```bash
export USE_MOCK_GUIDELINE_RESPONSES=true
./debug_app.sh
```

## Prerequisites

The system requires:
- Docker and Docker Compose (for PostgreSQL with pgvector)
- Python with required dependencies installed
- Access to the project files

## Mock Data Configuration

The system looks for mock data in the following locations:

1. `guideline_concepts.json` in the project root directory
2. `test_concepts_output.json` in the project root directory (fallback)

If neither file is found, the system will generate default mock concepts.

### Mock Data Format

The mock data should follow this format:

```json
[
  {
    "id": 0,
    "label": "Public Safety",
    "description": "The paramount obligation of engineers to prioritize public safety",
    "category": "principle",
    "related_concepts": ["Ethical Responsibility", "Risk Management"],
    "text_references": ["Engineers shall hold paramount the safety of the public"]
  },
  {
    "id": 1,
    "label": "Professional Competence",
    "description": "The obligation to only perform work within one's area of competence",
    "category": "obligation",
    "related_concepts": ["Professional Development", "Technical Expertise"],
    "text_references": ["Engineers shall perform services only in areas of their competence"]
  }
]
```

Alternatively, with a wrapper object:

```json
{
  "concepts": [
    {
      "id": 0,
      "label": "Public Safety",
      "description": "The paramount obligation of engineers to prioritize public safety",
      "category": "principle",
      "related_concepts": ["Ethical Responsibility", "Risk Management"],
      "text_references": ["Engineers shall hold paramount the safety of the public"]
    }
  ]
}
```

## Implementation Details

The mock response system is implemented in:

- `mcp/modules/guideline_analysis_module.py`: The `_load_mock_concepts()` method loads mock data from JSON files
- `app/routes/worlds.py`: Contains improved JSON parsing and concept extraction routing
- `app/routes/worlds_direct_concepts.py`: Provides the direct concept extraction functionality

## Database Connection

The system uses PostgreSQL with the pgvector extension for storing ontology data:

- Runs in a Docker container via docker-compose
- Uses port 5433 (mapped from internal port 5432)
- Default credentials: postgres/PASS
- Database name: ai_ethical_dm
- Container name varies by environment:
  - Codespaces: postgres17-pgvector-codespace
  - WSL: postgres17-pgvector-wsl
  - Other: proethica-postgres

The debug script automatically detects the appropriate container name based on your environment and starts it if not running.

## JSON Parsing Enhancements

The system includes enhanced JSON parsing with these fallback strategies:

1. Standard JSON parsing
2. Fix missing quotes around property names
3. Convert single quotes to double quotes
4. Use Python's `ast.literal_eval` to parse Python-style dictionaries

These improvements make the form submission process more robust when saving concepts.

## Environment Variables Used

- `USE_MOCK_GUIDELINE_RESPONSES=true`: Enables the mock response system
- `MCP_SERVER_ALREADY_RUNNING=true`: Prevents starting duplicate MCP servers

## Stopping the Servers

When you're done testing, run:

```bash
# To find all python processes
ps aux | grep python

# To kill specific processes
kill <pid1> <pid2>
```

To stop the PostgreSQL Docker container:

```bash
docker-compose down
