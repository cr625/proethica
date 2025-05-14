# Guideline MCP Integration

This document explains the integration of the guidelines feature with the MCP server ontology for triple extraction.

## Overview

The integration connects the guidelines feature with the MCP server to enable:
1. Extraction of concepts from guidelines text
2. Matching concepts to ontology entities
3. Generating RDF triples representing relationships

## Key Files

- **Startup Script**: `start_with_enhanced_ontology_server.sh`
- **MCP Server**: `mcp/enhanced_ontology_server_with_guidelines.py`
- **Guideline Module**: `mcp/modules/guideline_analysis_module.py`
- **Testing Tools**:
  - `test_mcp_jsonrpc_connection.py`
  - `test_guideline_mcp_client.py`
  - `run_guidelines_mcp_pipeline.sh`
- **Fix Scripts**:
  - `fix_mcp_client.py`
  - `fix_test_guideline_mcp_client.py`
  - `final_fix_mcp_client_jsonrpc.py`
  - `update_claude_models_in_mcp_server.py`

## Setup and Configuration

### Dependencies

Install required packages:

```bash
pip install -r requirements.txt
pip install -r requirements-mcp.txt
```

### Starting the Application

To run the application with guidelines support:

```bash
./start_with_enhanced_ontology_server.sh
```

This script performs these steps:
1. Starts the enhanced MCP server with guidelines module
2. Updates the MCP client to use JSON-RPC
3. Ensures proper model references
4. Starts the Flask application

## JSON-RPC API

The integration uses JSON-RPC for communication between clients and the server.

### Available Methods

- `extract_guideline_concepts`: Extract concepts from guideline text
- `match_concepts_to_ontology`: Match extracted concepts to ontology entities
- `generate_concept_triples`: Generate RDF triples from matched concepts

### Example JSON-RPC Request

```json
{
  "jsonrpc": "2.0",
  "method": "extract_guideline_concepts",
  "params": {
    "guideline_text": "Engineers shall hold paramount the safety, health, and welfare of the public."
  },
  "id": 1
}
```

## Troubleshooting

### JSON-RPC Connection Issues

If you see errors about failed MCP server connection:

1. Ensure server is running:
   ```bash
   ps aux | grep enhanced_ontology_server_with_guidelines
   ```

2. Test JSON-RPC connectivity:
   ```bash
   ./test_mcp_jsonrpc_connection.py --verbose
   ```

3. Check if server is accessible:
   ```bash
   curl -X POST http://localhost:5001/jsonrpc -H "Content-Type: application/json" \
   -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}'
   ```

### Client Request Method Issues

If client fails with 405 Method Not Allowed:

1. The client might be using GET instead of POST for JSON-RPC
2. Run the fix script: `./final_fix_mcp_client_jsonrpc.py`

### Model Reference Issues

If you see errors about outdated Claude models:

1. Update model references: `./update_claude_models_in_mcp_server.py`
2. Set the environment variable: `export CLAUDE_MODEL_VERSION="claude-3-7-sonnet-20250219"`

## Current Status

The integration is now complete and functional with:

1. ✅ Server-side guideline analysis module
2. ✅ JSON-RPC communication protocol
3. ✅ Updated client for proper API usage
4. ✅ Documentation of integration process
5. ✅ Testing tools for verification

## Next Steps

1. Enhance web UI for guideline management
2. Implement visualization for extracted concepts
3. Add batch processing capabilities
4. Create automated tests for guideline processing
