# Guidelines Ontology Integration Testing Guide

This guide explains how to test the integration between the ontology MCP server and the guidelines analysis functionality.

## Overview

The integration enables:
1. Extracting concepts from guideline documents
2. Matching concepts to ontology entities
3. Generating RDF triples for guideline concepts
4. Analyzing ethical principles in guidelines

## Prerequisites

- Python 3.8 or higher
- Required packages (install with `pip install -r requirements-mcp.txt`)
- An Anthropic API key (set as environment variable `ANTHROPIC_API_KEY`)
- An OpenAI API key (optional, set as environment variable `OPENAI_API_KEY`)

## Testing Steps

### Step 1: Fix the client connectivity issue

Run the fix script to update the test client to use the correct JSON-RPC endpoint:

```bash
./fix_test_guideline_mcp_client.py
```

This updates `test_guideline_mcp_client.py` to properly check for server availability using the JSON-RPC endpoint instead of the root URL.

### Step 2: Start the MCP server

```bash
python mcp/run_enhanced_mcp_server_with_guidelines.py
```

The server log should show successful initialization of all components:
- Anthropic client
- OpenAI client (if configured)
- Embeddings client
- Guideline analysis module

### Step 3: Run the test client

```bash
python test_guideline_mcp_client.py
```

This will:
1. Load a test guideline
2. Extract concepts using the LLM
3. Match concepts to ontology entities
4. Generate RDF triples
5. Save results to JSON and Turtle files

### Step 4: Examine the output files

- `guideline_concepts.json`: Contains extracted concepts
- `guideline_matches.json`: Contains matches between concepts and ontology entities
- `guideline_triples.json`: Contains the generated RDF triples
- `guideline_triples.ttl`: Contains the triples in Turtle format

## Troubleshooting

### Model Version Issues

If you see errors related to `claude-3-sonnet-20240229` being not found, the model version needs to be updated. The correct model name is `claude-3-7-sonnet-20250219`.

### Connection Issues

If the client can't connect to the server, make sure the server is running on port 5001 and check:

```bash
curl -X POST http://localhost:5001/jsonrpc -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}'
```

### API Key Issues

If you see authentication errors, ensure your API keys are set correctly:

```bash
export ANTHROPIC_API_KEY=your_key_here
export OPENAI_API_KEY=your_key_here
```

## Advanced Testing

### Test with Custom Guidelines

1. Create a text file with your guideline content
2. Update the client to use your file path
3. Run the client as before

### Modify the Extraction Process

You can edit `mcp/modules/guideline_analysis_module.py` to customize:
- The concept extraction template
- The matching algorithm
- The triple generation patterns

## Next Steps

After successful testing:
1. Integrate the guidelines analysis with the main application
2. Develop a web interface for guideline management
3. Create visualization tools for guideline concepts and relationships
