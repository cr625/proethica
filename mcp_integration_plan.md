# MCP Server Implementation Plan for UI Integration

This document outlines the comprehensive plan to implement the full MCP server that sends ontology data to the language model, integrating the functionality we verified in command-line tests into the UI.

## System Architecture Overview

The system consists of:

1. **UI Layer**: The Flask app renders templates (like `guideline_concepts_review.html`) that allow users to review extracted ontology concepts and triples.

2. **Routes Layer**: Routes in `app/routes/worlds.py` handle API endpoints for guideline analysis and concept extraction.

3. **Service Layer**: `GuidelineAnalysisService` acts as a client for the MCP server, making JSON-RPC requests to extract concepts, match to ontology, and generate triples.

4. **MCP Server**: The MCP server hosts modules including the `GuidelineAnalysisModule` that performs the actual AI-powered extraction and matching logic.

## Key Issues to Address

1. **Circular Imports**: There are circular import issues between the app modules and MCP modules that need to be resolved.

2. **MCP Server Initialization**: The enhanced MCP server with guidelines support is failing to start in Codespaces.

3. **Database Connection**: The MCP server needs to properly connect to the Codespace database on port 5433.

4. **JSON-RPC Communication**: Ensure reliable communication between the MCP client and server.

5. **Model References**: Update all Claude model references to use the latest version.

## Implementation Plan

### Phase 1: Standalone MCP Server Setup in Codespace Environment

1. **Create Codespace-specific Server Launcher**:
   ```python
   # codespace_ontology_server.py
   import os
   import sys
   import asyncio
   from pathlib import Path

   # Add project root to path
   project_root = Path(__file__).parent
   sys.path.insert(0, str(project_root))

   # Set environment variables for Codespace
   os.environ["MCP_SERVER_PORT"] = "5001"  # Use a port that's available in Codespace
   os.environ["PGPORT"] = "5433"           # Codespace uses port 5433 for PostgreSQL
   os.environ["PGHOST"] = "localhost"
   os.environ["FLASK_ENV"] = "development"
   os.environ["DEBUG"] = "True"

   # Import and run the enhanced server
   from mcp.enhanced_ontology_server_with_guidelines import run_server

   if __name__ == "__main__":
       asyncio.run(run_server())
   ```

2. **Create Server Launch Script**:
   ```bash
   #!/bin/bash
   # start_mcp_ontology_server.sh
   
   # Kill any existing MCP server processes
   echo "Checking for existing MCP server processes..."
   pkill -f "python.*enhanced_ontology_server" || true
   
   # Start the server in the background
   echo "Starting MCP ontology server..."
   python codespace_ontology_server.py > mcp_server_log.txt 2>&1 &
   
   # Save PID
   echo $! > mcp_server.pid
   echo "MCP server started with PID: $!"
   
   # Wait for server to start
   echo "Waiting for server to initialize..."
   sleep 3
   
   # Test if server is responding
   echo "Testing server connectivity..."
   curl -s -X POST http://localhost:5001/jsonrpc \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}'
   
   echo -e "\nServer started. Log file: mcp_server_log.txt"
   ```

### Phase 2: Fix Circular Import Issues

The test scripts avoid circular imports by keeping modules separate. We need to use the same approach:

1. **Extract Shared Models to Separate Module**:
   ```python
   # mcp/models/shared_models.py
   """Shared models used by both MCP server and Flask app."""
   
   class EntityTriple:
       """Common representation of an entity triple."""
       def __init__(self, subject, predicate, object_value, is_literal=False):
           self.subject = subject
           self.predicate = predicate
           self.object = object_value
           self.is_literal = is_literal
   
   # Other shared models here
   ```

2. **Update Client Code to Use Standalone MCP Client**:
   ```python
   # app/services/mcp_jsonrpc_client.py
   """Standalone MCP JSON-RPC client with no dependencies on app models."""
   
   import requests
   import logging
   
   logger = logging.getLogger(__name__)
   
   class MCPJsonRpcClient:
       """JSON-RPC client for MCP server."""
       
       def __init__(self, url="http://localhost:5001"):
           self.url = url
           self.jsonrpc_endpoint = f"{url}/jsonrpc"
       
       def call_tool(self, name, arguments):
           """Call a tool on the MCP server."""
           request_data = {
               "jsonrpc": "2.0",
               "method": "call_tool",
               "params": {
                   "name": name,
                   "arguments": arguments
               },
               "id": 1
           }
           
           try:
               response = requests.post(
                   self.jsonrpc_endpoint,
                   json=request_data,
                   timeout=60  # Longer timeout for LLM operations
               )
               
               if response.status_code != 200:
                   logger.error(f"HTTP error {response.status_code}: {response.text}")
                   return {"error": f"HTTP error {response.status_code}"}
               
               result = response.json()
               
               if "error" in result:
                   logger.error(f"JSON-RPC error: {result['error']}")
                   return {"error": result["error"]}
               
               return result.get("result", {})
               
           except Exception as e:
               logger.error(f"Error calling MCP tool: {str(e)}")
               return {"error": str(e)}
   ```

3. **Update GuidelineAnalysisService to Use the New Client**:
   ```python
   # Modified import in app/services/guideline_analysis_service.py
   from app.services.mcp_jsonrpc_client import MCPJsonRpcClient

   class GuidelineAnalysisService:
       def __init__(self):
           self.mcp_client = MCPJsonRpcClient()
   ```

### Phase 3: Implementing MCP Server Integration with UI

1. **Create an MCP Server Manager**:
   ```python
   # app/services/mcp_server_manager.py
   """Service to manage the MCP server lifecycle."""
   
   import os
   import subprocess
   import signal
   import time
   import logging
   import requests
   from pathlib import Path
   
   logger = logging.getLogger(__name__)
   
   class MCPServerManager:
       """Manages the MCP server process."""
       
       def __init__(self):
           self.server_pid = None
           self.server_process = None
           self.mcp_url = "http://localhost:5001"
       
       def ensure_server_running(self):
           """Ensure that the MCP server is running."""
           if self.is_server_running():
               logger.info("MCP server is already running")
               return True
           
           return self.start_server()
       
       def is_server_running(self):
           """Check if the MCP server is running."""
           try:
               # Try with JSON-RPC ping
               response = requests.post(
                   f"{self.mcp_url}/jsonrpc",
                   json={"jsonrpc": "2.0", "method": "list_tools", "params": {}, "id": 1},
                   timeout=2
               )
               return response.status_code == 200
           except:
               return False
       
       def start_server(self):
           """Start the MCP server."""
           try:
               # Path to the server script
               script_path = Path(__file__).parent.parent.parent / "codespace_ontology_server.py"
               
               # Start the server as a subprocess
               self.server_process = subprocess.Popen(
                   ["python", str(script_path)],
                   stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE
               )
               self.server_pid = self.server_process.pid
               
               # Wait for the server to start
               logger.info(f"Starting MCP server (PID: {self.server_pid})...")
               timeout = time.time() + 30
               while time.time() < timeout:
                   if self.is_server_running():
                       logger.info("MCP server started successfully")
                       return True
                   time.sleep(1)
               
               logger.error("Timed out waiting for MCP server to start")
               return False
               
           except Exception as e:
               logger.error(f"Error starting MCP server: {str(e)}")
               return False
       
       def stop_server(self):
           """Stop the MCP server."""
           if self.server_pid:
               try:
                   os.kill(self.server_pid, signal.SIGTERM)
                   logger.info(f"Stopped MCP server (PID: {self.server_pid})")
                   self.server_pid = None
                   return True
               except Exception as e:
                   logger.error(f"Error stopping MCP server: {str(e)}")
           return False
   ```

2. **Update Flask Application Initialization**:
   ```python
   # app/__init__.py (modified section)
   from app.services.mcp_server_manager import MCPServerManager

   def create_app(config_object=None):
       # ... existing initialization ...
       
       # Start MCP server if needed
       mcp_manager = MCPServerManager()
       with app.app_context():
           if not mcp_manager.is_server_running():
               mcp_manager.start_server()
       
       # ... rest of initialization ...
   ```

3. **Add Status Monitoring Endpoint**:
   ```python
   # New route in app/routes
   @app.route('/mcp/status', methods=['GET'])
   def mcp_status():
       """Check MCP server status."""
       manager = MCPServerManager()
       is_running = manager.is_server_running()
       return jsonify({
           'status': 'running' if is_running else 'stopped',
           'url': manager.mcp_url
       })
   ```

### Phase 4: Enhancing the UI for Guideline Analysis

1. **Add Server Status Indicator to Templates**:
   ```html
   <!-- Add to base.html or relevant templates -->
   <div class="mcp-status-indicator">
     <span id="mcp-status-light" class="status-light"></span>
     <span id="mcp-status-text">MCP Server: Checking...</span>
   </div>
   
   <script>
   // Add to JS section
   function checkMcpStatus() {
     fetch('/mcp/status')
       .then(response => response.json())
       .then(data => {
         const statusLight = document.getElementById('mcp-status-light');
         const statusText = document.getElementById('mcp-status-text');
         
         if (data.status === 'running') {
           statusLight.className = 'status-light status-online';
           statusText.textContent = 'MCP Server: Online';
         } else {
           statusLight.className = 'status-light status-offline';
           statusText.textContent = 'MCP Server: Offline';
         }
       })
       .catch(err => {
         console.error('Error checking MCP status:', err);
       });
   }
   
   // Check status on page load and every 30 seconds
   checkMcpStatus();
   setInterval(checkMcpStatus, 30000);
   </script>
   ```

2. **Add Progress Indicators**:
   ```html
   <!-- Add to guideline_concepts_review.html -->
   <div class="progress-container" id="extraction-progress" style="display: none;">
     <div class="progress">
       <div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" aria-valuenow="100" aria-valuemin="0" aria-valuemax="100" style="width: 100%"></div>
     </div>
     <p class="text-center">Processing guideline concepts... This may take a few moments.</p>
   </div>
   ```

### Phase 5: Testing and Error Handling

1. **Create MCP Connectivity Test Script**:
   ```bash
   #!/bin/bash
   # test_mcp_connectivity.sh
   
   echo "Testing MCP server connectivity..."
   
   # Check if server is running 
   response=$(curl -s -X POST http://localhost:5001/jsonrpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}')
   
   if [[ $response == *"tools"* ]]; then
     echo "✅ MCP server is running and responding correctly"
     echo "Available tools:"
     echo "$response" | jq .result.tools[].name
   else
     echo "❌ MCP server is not responding properly"
     echo "Response: $response"
     exit 1
   fi
   
   # Test the guideline tools specifically
   echo -e "\nTesting guideline extraction tool..."
   
   curl -s -X POST http://localhost:5001/jsonrpc \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc":"2.0",
       "method":"call_tool",
       "params":{
         "name":"extract_guideline_concepts",
         "arguments":{"content":"Engineers shall hold paramount the safety of the public."}
       },
       "id":1
     }' | jq .
   
   echo "Test completed"
   ```

2. **Add Comprehensive Client Error Handling**:
   ```python
   # Add to guideline_analysis_service.py
   
   def extract_concepts_with_retry(self, content, ontology_source=None, max_retries=3):
       """Extract concepts with retry logic."""
       for attempt in range(max_retries):
           try:
               result = self.extract_concepts(content, ontology_source)
               if "error" not in result:
                   return result
               
               logger.warning(f"Attempt {attempt+1} failed: {result['error']}")
               # Wait before retry (exponential backoff)
               time.sleep(2 ** attempt)
           except Exception as e:
               logger.exception(f"Exception in attempt {attempt+1}: {str(e)}")
               time.sleep(2 ** attempt)
       
       # Last attempt without catching exceptions
       return self.extract_concepts(content, ontology_source)
   ```

### Phase 6: Database Connection and Isolation

1. **Ensure Proper PostgreSQL Configuration**:
   ```python
   # Add to codespace_ontology_server.py
   
   # Set PostgreSQL environment variables for Codespace
   os.environ["PGDATABASE"] = "ai_ethical_dm"
   os.environ["PGUSER"] = "postgres"
   os.environ["PGPASSWORD"] = "postgres"  # Same as in setup_codespace_db.sh
   os.environ["PGPORT"] = "5433"
   os.environ["PGHOST"] = "localhost"
   ```

2. **Add Database Connection Test**:
   ```python
   # Add to mcp/enhanced_ontology_server_with_guidelines.py
   
   def _test_database_connection(self):
       """Test database connection."""
       try:
           import psycopg2
           conn_string = (
               f"dbname={os.environ.get('PGDATABASE', 'ai_ethical_dm')} "
               f"user={os.environ.get('PGUSER', 'postgres')} "
               f"password={os.environ.get('PGPASSWORD', 'postgres')} "
               f"host={os.environ.get('PGHOST', 'localhost')} "
               f"port={os.environ.get('PGPORT', '5433')}"
           )
           conn = psycopg2.connect(conn_string)
           conn.close()
           logger.info("Database connection test successful")
           return True
       except Exception as e:
           logger.error(f"Database connection test failed: {str(e)}")
           return False
   ```

## Insights from Working Test Scripts

From analyzing the working test scripts (`run_guideline_mcp_test.sh`, `run_guidelines_mcp_pipeline.sh`), we've identified the following key factors for success:

1. **Direct JSON-RPC Communication**: The test scripts use direct JSON-RPC calls with proper formatting, avoiding REST API calls that might be less reliable.

2. **Proper Server Initialization**: The tests start a clean, isolated MCP server process, which avoids potential conflicts.

3. **Client Fixes**: The `fix_test_guideline_mcp_client.py` script shows how connection issues can be fixed programmatically.

4. **Explicit Error Handling**: The test client implementation has comprehensive error handling and proper timeouts.

5. **Clean Process Management**: The tests properly manage process lifecycle, including graceful startup and shutdown.

By following these patterns from the working test implementation, we can ensure a robust integration of the MCP server with the UI components.

## Step-by-step Integration Plan

1. Create the codespace-specific server launcher and startup script
2. Implement the standalone MCP JSON-RPC client
3. Create the MCP server manager service
4. Update the GuidelineAnalysisService to use the new client
5. Add UI enhancements for server status and progress indicators
6. Implement comprehensive error handling and retry logic
7. Test the complete integration with real guideline data

This plan addresses all the key issues observed in the integration while leveraging the approaches that have been proven to work in our test scripts.
