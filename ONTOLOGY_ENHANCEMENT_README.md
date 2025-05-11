# Ontology Enhancement Branch

This branch focuses on enhancing the ontology capabilities of ProEthica based on the realm-integration branch.

## Focus Areas

1. **Unified Ontology System**: Integrating and enhancing the ontology capabilities
2. **Enhanced Case Analysis**: Using ontologies for improved case analysis
3. **Temporal Ontology Features**: Adding temporal functionality to the ontology system

## Implementation Details

### Unified Ontology Server

The unified ontology server provides centralized access to ontology data and functionality.
Key features include:
- Standardized API for ontology access
- Dynamic loading of ontology modules
- Query capabilities across multiple ontology sources

### Case Analysis Integration

Case analysis functionality uses ontologies to:
- Extract ethical principles from cases
- Map case elements to ontology concepts
- Provide structured ethical reasoning

## Configuration

The ontology server runs on port 5002 by default to avoid conflicts with other services.
The MCP client has been modified to handle URL formatting issues and properly connect to the ontology server.

## Usage

To start the unified ontology server:
```bash
./start_unified_ontology_server.sh
```

To stop the server:
```bash
./stop_unified_ontology_server.sh
```
