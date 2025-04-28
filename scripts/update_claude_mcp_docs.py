#!/usr/bin/env python3
"""
Script to update CLAUDE.md with information about the MCP documentation added
"""

import os
import datetime
from pathlib import Path

def update_claude_md():
    # Get current date in required format
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Read the current CLAUDE.md
    try:
        with open("CLAUDE.md", "r") as f:
            content = f.read()
    except FileNotFoundError:
        print("Error: CLAUDE.md file not found.")
        return
    
    # Create the update entry
    entry = f"""## {date_str} - Added MCP Server Documentation

### Created Comprehensive Model Context Protocol Documentation

1. **Created MCP Documentation Directory**
   - Created docs/mcp_docs/ directory to centralize MCP documentation
   - Added detailed guides for MCP server creation and configuration
   - Created reference documentation for using MCP in the project

2. **Key Documentation Files Added**
   - **mcp_server_guide.md**: Comprehensive guide for creating and configuring MCP servers
   - **ontology_mcp_integration_guide.md**: Detailed instructions for integrating ontologies with MCP
   - **mcp_project_reference.md**: Proethica-specific MCP implementation details and best practices

3. **Documentation Content**
   - Architecture overviews and diagrams
   - Code examples for tools and resources
   - Implementation patterns for ontology integration
   - Best practices for creating custom MCP servers
   - Troubleshooting guides for common issues

### Benefits

- **Better Knowledge Transfer**: Comprehensive documentation for future developers
- **Standardized Implementation**: Clear patterns for MCP server development
- **Ontology Integration Guide**: Specialized documentation for working with ontologies in MCP
- **Project-specific Resources**: References tailored to this project's implementation

### Implementation

The documentation was created based on:
1. The official MCP SDK repository (https://github.com/modelcontextprotocol/python-sdk)
2. Our existing implementation in mcp/http_ontology_mcp_server.py
3. Best practices for MCP server implementation and ontology integration
"""

    # Insert the entry after the first line (assumed to be the title)
    if "\n" in content:
        first_line_end = content.find("\n") + 1
        updated_content = content[:first_line_end] + entry + "\n\n" + content[first_line_end:]
    else:
        updated_content = content + "\n\n" + entry

    # Write back to CLAUDE.md
    with open("CLAUDE.md", "w") as f:
        f.write(updated_content)
    
    print(f"Successfully updated CLAUDE.md with MCP documentation information")

if __name__ == "__main__":
    update_claude_md()
