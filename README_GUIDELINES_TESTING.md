# Guidelines MCP Integration Testing Guide

This guide explains how to test the newly implemented guidelines MCP integration feature that uses the enhanced MCP server to extract concepts from engineering ethics guidelines, match them to ontology entities, and generate RDF triples.

## Prerequisites

Before testing, make sure you have:

1. Set up the environment variables (especially for LLM API access):
   - `ANTHROPIC_API_KEY` - Required for Claude 3 Sonnet model access
   - `OPENAI_API_KEY` - Optional for embeddings (will use fallback if not available)

2. Installed all required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. The test guideline file (`test_guideline.txt`) which contains engineering ethics guidelines content

## Testing Methods

There are three main ways to test the guidelines integration feature:

### 1. Full Pipeline Testing (Recommended)

Run the entire pipeline with a single command to start the server, execute tests, and shut everything down properly:

```bash
./run_guidelines_mcp_pipeline.sh
```

This script:
1. Sets up environment variables (from `.env` if available)
2. Starts the MCP server with guidelines support
3. Runs the test client to process the test guideline
4. Saves results as JSON and Turtle files
5. Shuts down the server properly

After running, check the output files:
- `guideline_concepts.json`: Contains extracted concepts
- `guideline_matches.json`: Contains ontology entity matches
- `guideline_triples.json`: Contains generated triples in JSON format
- `guideline_triples.ttl`: Contains generated triples in Turtle format

### 2. Manual Component Testing

Test each component separately for more detailed examination:

#### Step 1: Start the MCP server manually

```bash
python mcp/run_enhanced_mcp_server_with_guidelines.py
```

The server will start and listen on port 5001 by default (or the port specified in your environment).

#### Step 2: Run the test client

In a separate terminal:

```bash
python test_guideline_mcp_client.py
```

This will connect to the MCP server, process the test guideline, and save the output files.

#### Step 3: Examine the results

Check the generated files as mentioned above.

#### Step 4: Shut down the server

Press Ctrl+C in the terminal where the server is running.

### 3. Interactive Testing with Browser

For a visual examination of the MCP server functionality:

1. Start the MCP server:
   ```bash
   python mcp/run_enhanced_mcp_server_with_guidelines.py
   ```

2. Open a browser and navigate to:
   ```
   http://localhost:5001
   ```

3. Use the MCP server's built-in UI to explore available tools and resources

4. Test individual tools by making JSON-RPC requests through the UI:
   - Tool: `extract_guideline_concepts`
   - Tool: `match_concepts_to_ontology`
   - Tool: `generate_concept_triples`

## Troubleshooting

### MCP Server Won't Start

1. Check for port conflicts:
   ```bash
   lsof -i :5001
   ```
   If another process is using port 5001, either stop that process or set a different port with:
   ```bash
   export MCP_SERVER_PORT=5002
   ```

2. Verify environment variables:
   ```bash
   echo $ANTHROPIC_API_KEY
   ```
   If empty, the LLM features won't work properly. Set it in your `.env` file or directly in the terminal.

3. Check for Python errors:
   - Make sure all required packages are installed
   - Check that project paths are correctly set up in the scripts

### Client Connection Errors

1. Ensure the server is running:
   ```bash
   ps aux | grep enhanced_mcp_server
   ```

2. Check the server logs for any errors

3. Verify the client is using the correct port (same as the server)

### LLM API Errors

1. Check your API key validity

2. Look for rate limiting messages in the logs

3. Ensure you have sufficient API credits/quota

## Expected Results

When everything works correctly, you should see output similar to this:

```
Starting guideline analysis test
Waiting up to 30 seconds for MCP server...
MCP server is running!
Read 3214 characters from test guideline
Available tools: [list of tools]
Calling extract_guideline_concepts tool...
Successfully extracted concepts
Extracted 24 concepts
Concept 1: Public Safety - Obligation
Concept 2: Professional Competence - Principle
Concept 3: Truthful Communication - Obligation
Calling match_concepts_to_ontology tool...
Successfully matched concepts to ontology
Found 17 matches
Match 1: Public Safety -> http://proethica.org/ontology/PublicSafety (confidence: 0.92)
Match 2: Professional Competence -> http://proethica.org/ontology/Competence (confidence: 0.87)
Match 3: Truthful Communication -> http://proethica.org/ontology/Integrity (confidence: 0.83)
Calling generate_concept_triples tool for 10 concepts...
Successfully generated triples
Generated 38 RDF triples
Triple 1: Public Safety -> is a -> Obligation
Triple 2: Public Safety -> defined by -> "Engineers must hold paramount the safety, health, and welfare of the public"
Triple 3: Public Safety -> related to -> Professional Responsibility
Saved concepts to guideline_concepts.json
Saved matches to guideline_matches.json
Saved triples to guideline_triples.json
Saved Turtle triples to guideline_triples.ttl
Guideline analysis test completed
```

## Viewing the Output

### Turtle File

The `guideline_triples.ttl` file contains semantic triples in Turtle format that can be loaded into any RDF-compatible tool. For example:

```turtle
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix proeth: <http://proethica.org/ontology/> .
@prefix guide: <http://proethica.org/guidelines/engineering/> .

<http://proethica.org/guidelines/engineering/PublicSafety> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://proethica.org/ontology/Obligation> .
<http://proethica.org/guidelines/engineering/PublicSafety> <http://www.w3.org/2000/01/rdf-schema#label> "Public Safety" .
<http://proethica.org/guidelines/engineering/PublicSafety> <http://proethica.org/ontology/hasDescription> "Engineers must hold paramount the safety, health, and welfare of the public in the performance of their professional duties." .
```

### JSON Files

The JSON files contain more detailed information about each stage of the process:

- `guideline_concepts.json`: Contains all extracted concepts with their properties
- `guideline_matches.json`: Contains matches between concepts and ontology entities
- `guideline_triples.json`: Contains the generated triples in JSON format

## Advanced Testing

### Custom Guidelines

To test with your own guidelines content:

1. Create a new text file with your guidelines content
2. Update the path in `test_guideline_mcp_client.py`:
   ```python
   TEST_GUIDELINE_PATH = Path("your_custom_guideline.txt")
   ```
3. Run the tests as described above

### Direct API Testing

For advanced testing, you can make direct JSON-RPC calls to the MCP server:

```bash
curl -X POST http://localhost:5001/jsonrpc -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "method": "call_tool",
  "params": {
    "name": "extract_guideline_concepts",
    "arguments": {
      "content": "Your guideline content here",
      "ontology_source": "engineering-ethics"
    }
  },
  "id": 1
}'
```

## Integrating with the Main Application

After testing, you can integrate these features with the main application:

1. Update `app/services/guideline_analysis_service.py` to use the MCP client for guideline analysis
2. Update `app/routes/worlds.py` to handle the new analysis workflow
3. Test the integrated feature through the web interface
