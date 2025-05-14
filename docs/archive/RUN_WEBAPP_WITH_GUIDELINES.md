# Running the Web Application with Guidelines Integration

This guide explains how to run the Flask web application with the enhanced ontology server that supports guidelines integration.

## Step 1: Prepare the Environment

First, make sure you have all dependencies installed:

```bash
pip install -r requirements.txt  # Core application requirements
pip install -r requirements-mcp.txt  # MCP server requirements
```

## Step 2: Start the Application with Enhanced Server

We've created a special startup script that uses the enhanced ontology server with guidelines support:

```bash
./start_with_enhanced_ontology_server.sh
```

This script will:
1. Start the enhanced ontology server with guidelines module
2. Check the database schema
3. Start the Flask web application

## Step 3: Access the Web Interface

Once the application is running, you can access:

- Main web interface: http://localhost:3333
- Guidelines interface: http://localhost:3333/worlds/[world_id]/guidelines

## Testing the Guideline Features

After the application is running, you can:

1. **Upload a guideline**:
   - Navigate to a world detail page
   - Click on the "Guidelines" tab
   - Use the "Add Guideline" button

2. **View extracted concepts**:
   - After uploading, you'll be redirected to the guideline detail page
   - The system will automatically extract concepts from the guideline

3. **Review concept matches**:
   - The system will show concepts that match entities in the ontology
   - You can approve or reject these matches

4. **Generate and view triples**:
   - After reviewing matches, you can generate RDF triples
   - The triples will be displayed and stored in the database

## Debugging Connection Issues

If you experience connection issues with the MCP server:

1. Verify the server is running:
   ```bash
   ps aux | grep run_enhanced_mcp_server_with_guidelines
   ```

2. Test the JSON-RPC endpoint:
   ```bash
   curl -X POST http://localhost:5001/jsonrpc -H "Content-Type: application/json" \
   -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}'
   ```

3. Check the server logs:
   ```bash
   cat logs/enhanced_ontology_server_*.log | tail -100
   ```

## Key Differences from Standard Startup

This approach differs from the standard startup method in the following ways:

1. Uses the enhanced ontology server instead of the unified ontology server
2. Configures the server to use the GuidelineAnalysisModule
3. Tests connectivity using the JSON-RPC endpoint
4. Provides better error handling for connection issues

## Stopping the Application

To stop both the Flask application and the MCP server:

1. Press Ctrl+C in the terminal where the application is running
2. The script includes a cleanup function that will automatically terminate the MCP server

If the MCP server is still running after stopping the application, you can manually stop it:

```bash
pkill -f "python.*run_enhanced_mcp_server_with_guidelines.py"
```

## Troubleshooting

### Flask Application Fails to Start

If the Flask application fails to start:

1. Check if another instance is already running:
   ```bash
   ps aux | grep run.py
   ```

2. Verify the port is not in use:
   ```bash
   netstat -tuln | grep 3333
   ```

3. Check for error messages in the terminal output

### MCP Server Fails to Start

If the MCP server fails to start:

1. Check if another MCP server is already running:
   ```bash
   ps aux | grep mcp
   ```

2. Look at the log file that was created:
   ```bash
   cat logs/enhanced_ontology_server_*.log
   ```

3. Make sure your API keys are properly set in the .env file:
   ```
   ANTHROPIC_API_KEY=your_key_here
   ```
