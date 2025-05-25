# Debugging the MCP Server Guidelines Processing

Follow these step-by-step instructions to debug the concept extraction flow between the Guidelines feature and MCP server:

## Step 1: Prepare the Environment

1. Make sure all applications are stopped
2. Run the setup script to prepare the debug environment:
   ```bash
   ./debug_mcp_server.sh
   ```

## Step 2: Set Breakpoints in VSCode

1. Open the following files in VSCode:
   - `mcp/enhanced_ontology_server_with_guidelines.py`
   - `mcp/modules/guideline_analysis_module.py`

2. Set breakpoints at these specific locations:
   - In `enhanced_ontology_server_with_guidelines.py`:
     - Line ~200 in the `handle_jsonrpc` method
     - Line ~276 in the `_handle_call_tool` method when `name == 'extract_guideline_concepts'`
   - In `guideline_analysis_module.py`:
     - Line ~221 in the `extract_guideline_concepts` method

3. Click on each line number in the gutter area to set the breakpoint (a red dot should appear)

## Step 3: Launch the Debug Configuration

1. Click on the "Run and Debug" icon in the VSCode sidebar (or press Ctrl+Shift+D)
2. Select "Debug Enhanced MCP Server with Guidelines" from the dropdown at the top
3. Click the green play button to start debugging

## Step 4: Launch the Main Application

1. Open a new terminal in VSCode
2. Run the main application using the debug bash script:
   ```bash
   ./debug_app.sh
   ```
3. Wait for the application to start completely

> **Note:** `debug_app.sh` does the following:
> - Applies a patch to fix the SQLAlchemy URL issue
> - Sets necessary environment variables
> - Runs the application with the correct port settings

## Step 5: Trigger the Concept Extraction

1. Open a browser and navigate to `http://localhost:3333`
2. Go to a world detail page
3. Navigate to the Guidelines tab
4. Open an existing guideline or create a new one
5. Click on the "Analyze Concepts" button

## Step 6: Debug the Flow

1. VSCode should stop at your breakpoints when the request is received
2. You can examine variables, step through the code, and understand the flow
3. Use F10 to step over, F11 to step into, and Shift+F11 to step out of functions
4. Hover over variables to see their values
5. Use the Debug Console to evaluate expressions

## Debugging Notes

- The JSON-RPC request is first processed by `handle_jsonrpc` in the server
- It then gets routed to `_handle_call_tool` if it's a tool call
- The request then routes to the appropriate module method, in this case `extract_guideline_concepts`
- You can track the complete flow by following the execution with the debugger

## Key Source Files

- `app/routes/fix_concept_extraction.py`: Handles the route for analyzing concepts
- `app/services/guideline_analysis_service.py`: Service that calls the MCP server
- `mcp/enhanced_ontology_server_with_guidelines.py`: MCP server implementation
- `mcp/modules/guideline_analysis_module.py`: Module that handles guideline analysis
