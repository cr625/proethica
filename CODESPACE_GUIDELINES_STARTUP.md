# Running the Guidelines Feature in GitHub Codespaces

This document provides instructions for running the ProEthica application with guidelines support in the GitHub Codespaces environment.

## Quick Start

You can use either the standard startup script or the Codespace-specific starter script:

```bash
# Option 1: Use the main startup script which now has Codespace auto-detection
./start_proethica_updated.sh

# Option 2: Use the Codespace-specific starter script
./codespace_custom_start.sh
```

This script will:
1. Set up PostgreSQL in the Codespaces environment
2. Configure environment variables
3. Start the enhanced MCP server with guidelines support
4. Initialize the database schema
5. Launch the Flask application in debug mode

## Manual Startup

If you prefer to start the services individually, follow these steps:

### 1. Set up PostgreSQL

The Codespace environment uses PostgreSQL on port 5433 (different from the default 5432):

```bash
./scripts/setup_codespace_db.sh
```

### 2. Configure Environment Variables

Create or update your `.env` file with the correct Codespace settings:

```bash
# Database connection (same as in setup_codespace_db.sh)
DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm

# MCP server URL
MCP_SERVER_URL=http://localhost:5001

# LLM model
CLAUDE_MODEL_VERSION=claude-3-7-sonnet-20250219

# Environment 
ENVIRONMENT=codespace
USE_MOCK_FALLBACK=false
SET_CSRF_TOKEN_ON_PAGE_LOAD=true
```

### 3. Start the MCP Server

Start the enhanced MCP server with guidelines support:

```bash
python mcp/run_enhanced_mcp_server_with_guidelines.py
```

The server runs on `http://localhost:5001` with a JSON-RPC endpoint at `http://localhost:5001/jsonrpc`.

### 4. Test the MCP Server Connection

Ensure the MCP server is running correctly:

```bash
python test_mcp_jsonrpc_connection.py
```

### 5. Launch the Flask Application

Start the Flask application:

```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
export MCP_SERVER_ALREADY_RUNNING=true
python run.py
```

## Testing the Guidelines Feature

To verify that the guidelines feature is working correctly, follow these steps:

### 1. Access the Web Interface

After starting the application, open the web interface at the provided URL (typically shown in the GitHub Codespaces ports tab).

### 2. Navigate to Guidelines

Go to the Guidelines section from the main navigation menu.

### 3. Upload a Guideline File

Create a sample guideline file (or use an existing one):
```
# Engineering Ethics Guidelines

Engineers shall hold paramount the safety, health, and welfare of the public in the performance of their professional duties.

Engineers shall perform services only in areas of their competence.

Engineers shall act in such a manner as to uphold and enhance the honor, integrity, and dignity of the engineering profession.
```

Upload this file through the web interface.

### 4. Process the Guideline

Click the "Process" button to extract concepts from the guidelines and match them to the ontology.

### 5. Review the Results

Review the extracted concepts and their mappings to ontology entities.

### 6. Generate Triples

Generate RDF triples from the guideline concepts.

## Testing via Command Line

You can also test the guideline processing pipeline from the command line:

```bash
./run_guidelines_mcp_pipeline.sh
```

This script will:
1. Start the MCP server (if not already running)
2. Process a test guideline
3. Extract concepts from the guideline
4. Match concepts to ontology entities
5. Generate RDF triples
6. Save the results as JSON and Turtle files

Check the generated files:
- `guideline_concepts.json`: Extracted concepts
- `guideline_matches.json`: Matches to ontology entities
- `guideline_triples.json`: RDF triples in JSON format
- `guideline_triples.ttl`: RDF triples in Turtle format

## Troubleshooting

### MCP Server Connection Issues

If you encounter connection issues with the MCP server:

1. Check that the server is running:
```bash
curl -X POST http://localhost:5001/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}'
```

2. Update the client to use JSON-RPC:
```bash
python fix_mcp_client.py
```

3. Verify that the model references are correct:
```bash
python update_claude_models_in_mcp_server.py
```

### Database Connection Issues

If you encounter database connection issues:

1. Check the PostgreSQL container status:
```bash
docker ps | grep postgres
```

2. Restart the container if needed:
```bash
docker start postgres17-pgvector-codespace
```

3. Verify the connection settings:
```bash
psql -h localhost -p 5433 -U postgres -d ai_ethical_dm
```

## Integration Progress

For a detailed implementation plan and progress, see:
- `mcp_integration_plan.md`: Detailed MCP server UI integration plan
- `CODESPACE_CHANGES.md`: Changes made for GitHub Codespaces compatibility
- `guidelines_progress.md`: Overall progress tracking for the guidelines feature
