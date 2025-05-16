# Debugging Guideline Concept Extraction

This document provides instructions for debugging the Guideline Concept Extraction feature, which uses Claude's native tool calling capabilities to dynamically query the ontology during concept extraction.

## Prerequisites

- VSCode with Python extension installed
- Docker installed and running
- PostgreSQL client tools (`psql`) installed
- Python 3.10+ installed

## Best Approaches for Debugging

### Option 1: Debug Flask App with Background MCP (Recommended)

This approach is ideal for using the VSCode debugger on the Flask application while ensuring the MCP server runs in the background:

1. In VSCode, go to the Debug panel (Ctrl+Shift+D or Cmd+Shift+D)
2. Select "Debug Flask App with Background MCP" from the dropdown
3. Click the Play button or press F5

This will:
1. Start the MCP server in the background (saving output to mcp_server.log)
2. Launch the Flask app with the debugger attached
3. Allow you to set breakpoints and step through Flask app code

### Option 2: Separate Debug Sessions

If you specifically need to debug both components:

1. First, set breakpoints in the MCP server code
2. Use the Debug panel to launch "Debug MCP Server"
3. In a separate debug session, select "Debug Flask App Only"

### Option 3: Using Tasks for Quick Testing

For rapid testing without needing to debug:

1. Open the Command Palette (Ctrl+Shift+P or Cmd+Shift+P)
2. Type "Tasks: Run Task" and select it
3. Choose one of the following:
   - **Start MCP Server**: Starts only the MCP server in a new terminal
   - **Start Flask App**: Starts only the Flask app in a new terminal
   - **Start Full System**: Runs both in sequence (MCP server first, then Flask app)

## Database Setup

Before debugging, you may need to set up the PostgreSQL database with pgvector support:

1. Open the Command Palette (Ctrl+Shift+P or Cmd+Shift+P)
2. Type "Tasks: Run Task" and select it
3. Choose "Setup Database and Apply Fixes"

This task will:
- Stop and remove any existing postgres17-pgvector-codespace container
- Create a fresh container with pgvector support
- Create the database and enable the vector extension
- Ensure all required schema elements are present, including the embedding column

## Testing the Full Workflow

1. Start the system using one of the approaches above
2. Navigate to http://localhost:3333 in your browser
3. Go to a World (e.g., "Engineering")
4. Look for the "Guidelines" section in the navigation
5. Upload a new guideline or open an existing one
6. Click "Extract Concepts" to trigger the concept extraction process
7. Review the extracted concepts and their mappings to the ontology
8. Select concepts to save and click "Save Selected Concepts"

## Key Breakpoints to Set

### Flask Application
- `app/services/guideline_analysis_service.py`:
  - `extract_concepts`: Method that calls the MCP server
  - `save_guideline_concepts`: Method that saves concepts to database
- `app/routes/guidelines.py`:
  - Route handlers for guideline management and extraction

### MCP Server (if debugging MCP)
- `mcp/modules/guideline_analysis_module.py`:
  - `extract_guideline_concepts`: Method that calls Claude API
  - `generate_concept_triples`: Method that creates RDF triples
  - Tool handlers: `handle_query_ontology`, `handle_search_similar_concepts`, etc.

## Troubleshooting

### Common Issues

#### PostgreSQL Connection Issues
If you encounter database connection issues:
```bash
# Check if PostgreSQL container is running
docker ps | grep postgres

# If not running or need to restart, use the "Setup Database and Apply Fixes" task
# or run the commands manually:
docker stop postgres17-pgvector-codespace || true
docker rm postgres17-pgvector-codespace || true
docker run --name postgres17-pgvector-codespace -e POSTGRES_PASSWORD=PASS -p 5433:5432 -d pgvector/pgvector:pg17
```

#### MCP Server Issues
If the MCP server fails to start:
1. Check if the claude_tools initialization is properly done in GuidelineAnalysisModule.__init__()
2. Verify that the claude_tools attribute is defined before super().__init__() is called
3. Review the mcp_server.log file for errors

#### Flask Application Issues
If the Flask application fails:
1. Ensure PostgreSQL is running and accessible
2. Verify MCP server is running and accessible at http://localhost:5001
3. Check if the guidelines table has all required columns including 'embedding'

### Quick Fixes

#### Missing Embedding Column
If you encounter the error `column "embedding" of relation "guidelines" does not exist`:
```bash
PGPASSWORD=PASS psql -h localhost -p 5433 -U postgres -d ai_ethical_dm -c "ALTER TABLE guidelines ADD COLUMN embedding FLOAT[];"
```

#### GuidelineAnalysisModule Tool Attribute Error
If you encounter the error `'GuidelineAnalysisModule' object has no attribute 'claude_tools'`:
1. Edit mcp/modules/guideline_analysis_module.py
2. Move the claude_tools definition before the super().__init__() call

## Using Mock Responses

For testing without making actual Claude API calls:
1. Set the environment variable `USE_MOCK_GUIDELINE_RESPONSES=true` 
2. Check or edit mock responses in `tests/mock_responses/guideline_concepts_response.json`

This variable is set by default in the VSCode debug configurations.
