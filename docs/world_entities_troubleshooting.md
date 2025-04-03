# Troubleshooting World Entities Display

This guide will help you troubleshoot issues with world entities not displaying correctly in the ProEthica application, particularly when working with custom ontologies.

## Problem Description

When you create a world and set its ontology source to a custom ontology file, you may find that the entities (roles, conditions, resources, events, actions) don't appear in the "World Entities" section of the world detail page.

## Root Causes

There are several possible causes for this issue:

1. **Incorrect Entity Type Designation**: The MCP server looks for specific type designations to identify entities.
2. **MCP Server Connection Issues**: The MCP server might not be running or accessible.
3. **Syntax Errors in Ontology Files**: The ontology files might have TTL syntax errors.
4. **Incorrect Ontology Source Path**: The world's ontology_source field might be incorrect.

## Solution: Fix Entity Type Designations

The most common issue is that entity classes in the ontology need to be explicitly marked with specific type designations for the MCP server to recognize them:

- For roles: Classes must have `rdf:type proeth:Role` 
- For conditions: Classes must have `rdf:type proeth:ConditionType`
- For resources: Classes must have `rdf:type proeth:ResourceType`
- For events: Classes must have `rdf:type proeth:EventType`
- For actions: Classes must have `rdf:type proeth:ActionType`

We've fixed this in the provided ontology files.

## Troubleshooting Steps

### 1. Verify that your world has the correct ontology source

Run the update script to ensure your world has the correct ontology source:

```bash
python scripts/update_world_ontology.py 12 engineering-ethics.ttl
```

This will update World ID 12 to use the engineering-ethics.ttl ontology.

### 2. Test ontology entity extraction

Use the test script to verify that entities can be extracted from the ontology:

```bash
python scripts/test_ontology_extraction.py engineering-ethics.ttl
```

This will attempt to extract entities from the ontology using the MCP server API. You should see output showing the number of roles, conditions, resources, events, and actions found.

### 3. Restart the MCP server

If you're still having issues, try restarting the MCP server:

```bash
./scripts/restart_mcp_server.sh
```

### 4. Refresh the world in the UI

After making changes:

1. Go to the world detail page in your browser 
2. Click the Edit button
3. Without making any changes, click Save to trigger a refresh
4. Check the World Entities section again

## Common Issues

### MCP Server Not Running

If you see connection errors when running the test script, make sure the MCP server is running. Check for error messages in the terminal where you started the application.

### Syntax Errors in Ontology Files

If the ontology files have syntax errors, they might not load correctly. Check for error messages in the terminal where the MCP server is running.

### Database Connection Issues

If you're using a custom database URL, make sure it's set correctly in your environment:

```bash
export DATABASE_URL=sqlite:///path/to/your/database.db
```

### API Endpoints Incorrect

The test script assumes the MCP server is running on localhost:3333. If your server is using a different port, update the script.

## Additional Resources

For more information on how to create and use ontologies with ProEthica, see:

- [ProEthica Intermediate Ontology Guide](../mcp/ontology/INTERMEDIATE_ONTOLOGY_GUIDE.md)
- [ProEthica Technical Overview](../ProEthica_Technical_Overview.md)
