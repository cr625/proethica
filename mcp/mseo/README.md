# MSEO MCP Server

A Model Context Protocol (MCP) server for the Materials Science Engineering Ontology (MSEO).

## Overview

This module provides a server that exposes the Materials Science Engineering Ontology (MSEO) through the Model Context Protocol (MCP). The ontology is sourced from [MatPortal.org](https://matportal.org/ontologies/MSEO), a comprehensive resource for materials science knowledge.

The server enables AI agents to query and reason about materials science concepts, properties, and relationships through a standardized API, enhancing their ability to provide informed responses on materials science topics.

## Features

- Automatic downloading and validation of the MSEO ontology
- Materials, categories, and properties extraction and indexing
- Search capabilities for materials and their properties
- Material comparison tools
- LLM integration via Anthropic API (when available) for enhanced responses
- RESTful API access through the MCP protocol

## Installation

The MSEO MCP server is designed to be used as part of the REALM application or as a standalone component for materials science applications.

### Prerequisites

- Python 3.8+
- RDFlib
- Requests
- Flask (provided by the base MCP server)
- Anthropic SDK (optional, for LLM integration)

### Setup

1. Ensure the module directory is in your Python path
2. Install the required dependencies
3. Run the setup script to download the ontology:

```bash
python -m mcp.mseo.setup_mseo
```

## Usage

### Starting the Server

To start the MSEO MCP server:

```bash
python -m mcp.mseo.run_mseo_mcp_server
```

Options:
- `--host`: Host to bind the server to (default: localhost)
- `--port`: Port to run the server on (default: 8078)
- `--data-dir`: Directory for ontology data
- `--ontology-file`: Path to a specific ontology file
- `--name`: Name for the MCP server
- `--debug`: Enable debug mode

### Available Tools

The server provides the following MCP tools:

1. `get_materials` - Get a list of materials from the ontology
2. `get_material` - Get details about a specific material
3. `get_categories` - Get a list of material categories
4. `get_category` - Get details about a specific category
5. `get_material_properties` - Get properties of a specific material
6. `compare_materials` - Compare two materials by their properties
7. `search_ontology` - Search the ontology for materials, categories, or properties
8. `chat_completion` - Generate a chat response with ontology context (requires Anthropic API)

### Integrating with Client Applications

To integrate the MSEO MCP server with a client application, use the Model Context Protocol client library. Example:

```python
from mcp_client import MCPClient

# Connect to the server
client = MCPClient("http://localhost:8078")

# Search for materials
result = client.use_tool("search_ontology", {"query": "aluminum"})

# Get material properties
if result.get("materials"):
    material_uri = result["materials"][0]["uri"]
    properties = client.use_tool("get_material_properties", {"uri": material_uri})
    print(properties)
```

## Development

### Project Structure

- `mseo_mcp_server.py`: Main server implementation
- `setup_mseo.py`: Utilities for downloading and setting up the ontology
- `run_mseo_mcp_server.py`: Server runner script
- `__init__.py`: Package exports

### Extending the Server

To add new capabilities:

1. Add new methods to the `MSEOMCPServer` class
2. Register them as tools in the `register_tools` method
3. Update the documentation

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [MatPortal.org](https://matportal.org) for the Materials Science Engineering Ontology
- The Model Context Protocol for enabling standardized AI tool interactions
