#!/usr/bin/env python3
"""
Script to update the MCP server to use the enhanced ontology implementation.

This script:
1. Creates a new startup script for the enhanced MCP server
2. Updates references in other scripts
3. Makes the new script executable
"""

import os
import sys
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def create_enhanced_mcp_server_script():
    """Create the startup script for the enhanced MCP server."""
    server_script = """#!/usr/bin/env python3
"""
    server_script += '''
"""
Enhanced Ontology MCP Server startup script.
This script starts the enhanced MCP server with support for advanced ontology interactions.
"""

import os
import sys
import asyncio
import aiohttp
from pathlib import Path

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import the enhanced server
from mcp.enhanced_ontology_mcp_server import EnhancedOntologyMCPServer

if __name__ == "__main__":
    print("Starting Enhanced Ontology MCP Server...")
    port = int(os.environ.get("MCP_SERVER_PORT", 5001))
    print(f"Server will listen on port {port}")
    
    # Create and run the server
    server = EnhancedOntologyMCPServer()
    asyncio.run(server.run_server())
'''

    # Write the script to the mcp directory
    script_path = Path('mcp/run_enhanced_mcp_server.py')
    script_path.parent.mkdir(exist_ok=True)
    
    with open(script_path, 'w') as f:
        f.write(server_script)
    
    # Make the script executable
    os.chmod(script_path, 0o755)
    
    print(f"Created enhanced MCP server script at {script_path}")
    return script_path

def update_restart_script():
    """Update the restart MCP server script to use the enhanced version."""
    restart_script_path = Path('scripts/restart_mcp_server.sh')
    backup_path = restart_script_path.with_suffix('.sh.bak')
    
    # Create backup
    if restart_script_path.exists():
        shutil.copy2(restart_script_path, backup_path)
        print(f"Created backup of restart script at {backup_path}")
    
    # Create or update restart script
    with open(restart_script_path, 'w') as f:
        f.write('''#!/bin/bash
# Restart script for the enhanced MCP ontology server

# Kill any existing MCP server processes
echo "Stopping any existing MCP server processes..."
pkill -f "python3 mcp/run_enhanced_mcp_server.py" || true
sleep 1

# Start the enhanced MCP server in the background
echo "Starting enhanced MCP server..."
python3 mcp/run_enhanced_mcp_server.py &

# Wait a moment to ensure server has time to start
sleep 2
echo "Enhanced MCP server has been restarted."
''')
    
    # Make the script executable
    os.chmod(restart_script_path, 0o755)
    print(f"Updated restart script at {restart_script_path}")
    return restart_script_path

def update_run_script():
    """Update the main run script to restart the enhanced MCP server."""
    run_script_path = Path('run.py')
    if not run_script_path.exists():
        print(f"Warning: {run_script_path} not found, skipping update")
        return None
    
    backup_path = run_script_path.with_suffix('.py.bak')
    shutil.copy2(run_script_path, backup_path)
    print(f"Created backup of run script at {backup_path}")
    
    with open(run_script_path, 'r') as f:
        content = f.read()
    
    # Check if there's a reference to restarting MCP server
    if "restart_mcp_server" in content:
        # Update content to use enhanced MCP server
        updated_content = content.replace(
            "python3 mcp/http_ontology_mcp_server.py", 
            "python3 mcp/run_enhanced_mcp_server.py"
        )
        
        with open(run_script_path, 'w') as f:
            f.write(updated_content)
        print(f"Updated run script at {run_script_path}")
    else:
        print(f"No MCP reference found in {run_script_path}, skipping update")
    
    return run_script_path

def update_claude_md():
    """Update CLAUDE.md with information about the enhanced MCP server."""
    today = "2025-04-28"  # Replace with actual date if needed
    
    claude_md_path = Path('CLAUDE.md')
    backup_path = claude_md_path.with_suffix('.md.bak')
    
    # Create backup
    if claude_md_path.exists():
        shutil.copy2(claude_md_path, backup_path)
        print(f"Created backup of CLAUDE.md at {backup_path}")
    
    # Read current content
    with open(claude_md_path, 'r') as f:
        content = f.read()
    
    # Add new section at the top
    new_section = f"""## {today} - Enhanced Ontology-LLM Integration

### Implemented Enhanced MCP Server

1. **Created Enhanced Ontology MCP Server**
   - Implemented `mcp/enhanced_ontology_mcp_server.py` with advanced ontology interaction tools
   - Added new capabilities for semantic queries, constraint checking, and relationship navigation
   - Created startup script `mcp/run_enhanced_mcp_server.py`

2. **Tool Capabilities Added**
   - **query_ontology**: Run SPARQL queries against ontologies
   - **get_entity_relationships**: View incoming and outgoing relationships for an entity
   - **navigate_entity_hierarchy**: Explore parent-child class hierarchies
   - **check_constraint**: Validate against ontology constraints (domain/range, cardinality, etc.)
   - **search_entities**: Find entities by keywords or patterns
   - **get_entity_details**: Get comprehensive information about entities
   - **get_ontology_guidelines**: Extract guidelines and principles from ontologies

3. **Enhanced Integration with LLMs**
   - Better structuring of entity information for clarity to LLMs
   - Human-readable labels alongside URIs for better comprehension
   - Rich constraint checking capabilities for logical validation
   - Relationship-based navigation for connected knowledge exploration

### Usage

1. Start the enhanced MCP server using one of these methods:
   ```
   python3 mcp/run_enhanced_mcp_server.py
   # OR
   ./scripts/restart_mcp_server.sh
   ```

2. The enhanced MCP server exposes the same API endpoint as the previous version, but with additional tools:
   ```
   http://localhost:5001/jsonrpc
   ```

3. Use the MCP client to access the enhanced functionality in the same way as before, with additional tool capabilities now available.

### Benefits

- **Richer Knowledge Access**: LLMs can access deeper ontological knowledge structures
- **Constraint-Based Reasoning**: Enables validation against formal ontology constraints
- **Semantic Search**: Find entities based on keywords, patterns, or semantic properties
- **Relationship Navigation**: Explore connections between entities
- **Structured Guidelines**: Extract ethical principles and guidelines directly from ontologies

"""
    
    # Add the new section at the top
    updated_content = new_section + content
    
    # Write the updated content
    with open(claude_md_path, 'w') as f:
        f.write(updated_content)
    
    print(f"Updated {claude_md_path} with enhanced MCP server information")
    return claude_md_path

def main():
    """Run the update process."""
    print("Updating MCP server to use enhanced ontology implementation")
    
    # Create the enhanced MCP server script
    create_enhanced_mcp_server_script()
    
    # Update restart script
    update_restart_script()
    
    # Update run script if possible
    update_run_script()
    
    # Update CLAUDE.md
    update_claude_md()
    
    print("\nUpdate completed successfully!")
    print("To use the enhanced MCP server, run:")
    print("  python3 mcp/run_enhanced_mcp_server.py")
    print("  or")
    print("  ./scripts/restart_mcp_server.sh")

if __name__ == "__main__":
    main()
