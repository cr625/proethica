# Enhanced Ontology-LLM Integration Guide

This guide provides comprehensive information about the enhanced integration between ontologies and Language Learning Models (LLMs) using the Model Context Protocol (MCP). This integration enables LLMs to access, understand, and reason with ontological knowledge in a more sophisticated way.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Components](#components)
- [Setup and Configuration](#setup-and-configuration)
- [Usage Examples](#usage-examples)
- [Troubleshooting](#troubleshooting)
- [Advanced Features](#advanced-features)

## Overview

The Enhanced Ontology-LLM Integration provides a bridge between structured ontological knowledge and LLMs like Claude. By leveraging the Model Context Protocol (MCP), this integration allows LLMs to:

1. **Query and navigate ontology structures**: Explore entity relationships and hierarchies
2. **Validate against constraints**: Check if relationships satisfy ontological constraints
3. **Extract guidelines and principles**: Access structured ethical guidelines from ontologies
4. **Perform semantic searches**: Find entities based on keywords or patterns
5. **Access comprehensive entity information**: Get rich details about ontology entities

## Architecture

The integration is built on a layered architecture:

```
+-------------------+
|      LLM Agent    |
+-------------------+
         ↑
         | Enhanced Context
         ↓
+-------------------+
| Ontology Context  |
|    Provider       |
+-------------------+
         ↑
         | Rich Ontology Data
         ↓
+-------------------+
| Enhanced MCP      |
|    Client         |
+-------------------+
         ↑
         | JSON-RPC / HTTP
         ↓
+-------------------+
| Enhanced Ontology |
|   MCP Server      |
+-------------------+
         ↑
         | Query & Access
         ↓
+-------------------+
| Ontology Database |
| & File Storage    |
+-------------------+
```

## Components

### 1. Enhanced Ontology MCP Server

Located in `mcp/enhanced_ontology_mcp_server.py`, this component extends the basic HTTP MCP server with advanced ontology capabilities:

- **SPARQL Query Support**: Run queries against ontologies
- **Relationship Navigation**: Explore entity connections
- **Hierarchy Traversal**: Navigate parent-child relationships
- **Constraint Checking**: Validate against ontological constraints
- **Semantic Search**: Find entities based on patterns and keywords

### 2. Enhanced MCP Client

Located in `app/services/enhanced_mcp_client.py`, this client provides high-level methods for interacting with the enhanced MCP server:

- **Simplified Tool Access**: Easy-to-use methods for each tool
- **Error Handling**: Robust error handling and fallback mechanisms
- **Formatting Helpers**: Methods to format ontology data for LLM consumption
- **Singleton Pattern**: Consistent access across the application

### 3. Ontology Context Provider

Located in `app/services/context_providers/ontology_context_provider.py`, this provider enriches LLM context with ontology information:

- **Query-Based Entity Extraction**: Finds relevant entities based on user queries
- **Relationship Context**: Provides relationship information for better understanding
- **Guideline Extraction**: Includes applicable ethical guidelines and principles
- **Seamless Integration**: Works with existing application context system

## Setup and Configuration

### 1. Start the Enhanced MCP Server

```bash
# Option 1: Direct start
python3 mcp/run_enhanced_mcp_server.py

# Option 2: Using the restart script
./scripts/restart_mcp_server.sh
```

### 2. Enable the Enhanced Integration

```bash
python3 scripts/enable_enhanced_ontology_integration.py
```

This script:
- Registers the OntologyContextProvider
- Updates the application configuration
- Sets appropriate token allocation for ontology context

### 3. Test the Integration

```bash
python3 scripts/test_enhanced_ontology_integration.py
```

## Usage Examples

### Accessing Ontology Data in LLM Prompts

The enhanced integration automatically injects relevant ontology information into LLM prompts based on the user's query. For example, if a user asks about "engineering ethics," the system will:

1. Find entities related to "engineering ethics" in the ontology
2. Extract details about the most relevant entity
3. Include relationship information for better context
4. Add applicable guidelines and principles
5. Format everything for easy LLM consumption

### Manually Accessing Enhanced MCP Capabilities

You can also use the Enhanced MCP Client directly in your code:

```python
from app.services.enhanced_mcp_client import get_enhanced_mcp_client

# Get the client instance
client = get_enhanced_mcp_client()

# Search for entities
results = client.search_entities(
    ontology_source="engineering-ethics",
    query="responsibility"
)

# Get entity details
entity = client.get_entity_details(
    ontology_source="engineering-ethics",
    entity_uri="http://proethica.org/ontology/engineering-ethics#Engineer"
)

# Get entity relationships
relationships = client.get_entity_relationships(
    ontology_source="engineering-ethics",
    entity_uri="http://proethica.org/ontology/engineering-ethics#Engineer"
)

# Format for human-readable output
formatted_entity = client.format_entity_for_context(entity)
print(formatted_entity)
```

## Troubleshooting

### Common Issues

#### 1. Application Context Errors

If you see errors like:
```
Working outside of application context
```

This typically means the MCP server is trying to access the database without a proper Flask application context. To resolve:

- Ensure the MCP server is running within the application context
- Use `with app.app_context():` when accessing database models

#### 2. Connection Issues

If the enhanced MCP client cannot connect to the server:

- Ensure the server is running (`ps aux | grep enhanced`)
- Check the default port is available (5001)
- Verify network access is not blocked by firewall

#### 3. Missing Ontology Data

If entity queries return empty results:

- Verify the ontology exists in the database
- Check the ontology source name is correct
- Ensure the database connection is working properly

## Advanced Features

### 1. Constraint-Based Reasoning

The enhanced integration supports constraint checking:

```python
constraint_check = client.check_constraint(
    ontology_source="engineering-ethics",
    entity_uri="http://proethica.org/ontology/engineering-ethics#Engineer",
    constraint_type="custom",
    constraint_data={
        "validation_type": "role_capability",
        "required_capabilities": [
            "http://proethica.org/ontology/engineering-ethics#Technical_Design"
        ]
    }
)
```

### 2. Ontology Querying

Run SPARQL queries against ontologies:

```python
query_results = client.query_ontology(
    ontology_source="engineering-ethics",
    query="""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX proeth: <http://proethica.org/ontology/intermediate#>
    
    SELECT ?role ?label
    WHERE {
        ?role rdf:type proeth:Role .
        OPTIONAL { ?role rdfs:label ?label }
    }
    LIMIT 5
    """
)
```

### 3. Ontology Guidelines

Extract guidelines and principles:

```python
guidelines = client.get_ontology_guidelines("engineering-ethics")
formatted_guidelines = client.format_guidelines_for_context(guidelines)
```

---

## Further Reading

- [Model Context Protocol Documentation](docs/mcp_docs/mcp_server_guide.md)
- [Ontology MCP Integration Guide](docs/mcp_docs/ontology_mcp_integration_guide.md)
- [MCP Project Reference](docs/mcp_docs/mcp_project_reference.md)
- [Comprehensive Ontology Guide](docs/ontology_comprehensive_guide.md)
