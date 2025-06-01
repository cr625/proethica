# Ontology Enhancement Branch

> **Note**: For comprehensive ontology system documentation, see [README.md](./README.md)

This branch focuses on enhancing the ontology portion of ProEthica, with an emphasis on ontology-based case analysis.

## Overview

The ontology enhancement branch extends ProEthica's capabilities to perform detailed case analysis using ontological representations of ethical concepts, relationships, and principles. The system now uses the 8 GuidelineConceptTypes (Role, Principle, Obligation, State, Resource, Action, Event, Capability) for structured ethical reasoning.

## Key Components

### 1. Unified Ontology Server

The unified ontology server has been extended with:

- **Case Analysis Module**: For analyzing cases against ontology structures
- **Temporal Reasoning Module**: For handling temporal relationships between events
- **Enhanced Query Module**: For specialized SPARQL queries

### 2. Configuration

- The unified ontology server runs on port 5001
- URL escaping issues in the MCP client have been fixed
- Database connection has been properly configured for WSL environment

### 3. Documentation

- `docs/ontology_case_analysis_plan.md`: Detailed plan for ontology-based case analysis features
- `docs/unified_ontology_server.md`: Documentation for the unified ontology server
- `mcp/modules/case_analysis_module.py`: Module for case analysis functionality

## Getting Started

1. **Check out the branch**:
   ```bash
   git checkout ontology-focused
   ```

2. **Start the unified ontology server**:
   ```bash
   ./start_unified_ontology_server.sh
   ```

3. **Run ProEthica**:
   ```bash
   python run.py
   ```

## Development Workflow

1. **Case Analysis Implementation**:
   - Implement the case analysis module in `mcp/modules/case_analysis_module.py`
   - Add database tables using `scripts/create_case_analysis_tables.py`
   - Create API endpoints in `app/routes`

2. **Testing**:
   - Run `test_case_analysis.py` to test case analysis functionality
   - Test integration with the unified ontology server

3. **UI Development**:
   - Add UI components for visualizing ontology-based case analysis
   - Integrate with existing ProEthica UI

## Technical Details

### Database Schema

The case analysis functionality requires additional database tables (see `docs/ontology_case_analysis_plan.md` for details):

- `case_analysis`: Stores analysis results for cases
- `case_entity_mappings`: Maps case entities to ontology concepts
- `case_relation_mappings`: Maps relationships between case entities

### API Endpoints

New API endpoints for case analysis:

- `GET /api/cases/{case_id}/analysis`: Get analysis for a case
- `POST /api/cases/{case_id}/analyze`: Trigger analysis for a case
- `GET /api/cases/{case_id}/entity-mappings`: Get entity mappings for a case
- `GET /api/cases/{case_id}/relation-mappings`: Get relation mappings for a case

## Important Files

- `mcp/unified_ontology_server.py`: Main server implementation
- `mcp/modules/case_analysis_module.py`: Case analysis module
- `mcp/modules/temporal_module.py`: Temporal reasoning module
- `app/routes/ontology_routes.py`: API routes for ontology functionality
- `app/services/mcp_client.py`: Client for interacting with the MCP server
- `scripts/create_case_analysis_tables.py`: Script to create database tables

## Known Issues

- URL escaping in certain API calls may need additional handling
- Database connection issues may occur if PostgreSQL is not properly configured

## Future Work

See `docs/ontology_case_analysis_plan.md` for a detailed roadmap of future enhancements.
