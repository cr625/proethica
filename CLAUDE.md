# ProEthica Development Documentation

## Project Overview

ProEthica is an AI-powered ethical reasoning system that integrates multiple components:
- Web application for user interaction
- Ontology management for ethical knowledge representation
- Case analysis functionality for ethical reasoning
- MCP (Model Context Protocol) for AI model interaction

## Recent Development Work

### Ontology Enhancement Branch (2025-05-11)

Created a new branch focused on enhancing the ontology portion of ProEthica, based on the realm-integration branch. Key accomplishments:

1. **Branch Setup and Infrastructure**
   - Created `scripts/create_ontology_branch.sh` for automating branch creation
   - Configured unified ontology server to use port 5002 to avoid conflicts
   - Fixed port conflict issues with running MCP server processes

2. **Documentation**
   - Created `docs/ontology_case_analysis_plan.md` outlining the ontology-based case analysis features
   - Updated `ONTOLOGY_ENHANCEMENT_README.md` with branch information and configuration details

3. **Technical Fixes**
   - Resolved URL string escape issues (where "\x3a" was appearing instead of ":")
   - Fixed ontology blueprint conflicts in the Flask application
   - Improved error handling in MCP client

### URL Escape Sequence Fixes

Addressed issues where URL strings were being improperly escaped, causing "\x3a" to appear instead of ":". This was occurring in the MCP client when constructing URLs for API endpoints. The fix involved:

1. Using Python's string format() method instead of f-strings for URL construction
2. Adding URL normalization in the MCPClient class
3. Implementing proper string handling for URL paths

### Ontology Blueprint Resolution

Fixed conflicts between multiple ontology blueprints in app/__init__.py by:
1. Removing duplicate blueprint registrations
2. Ensuring correct naming conventions for blueprints
3. Properly structuring route paths

### Next Steps

1. **Module Implementation**
   - Complete the case analysis module functionality
   - Implement temporal ontology support
   - Enhance query capabilities

2. **Integration Testing**
   - Test ontology server with ProEthica application
   - Verify proper communication between components
   - Validate case analysis functionality

3. **Documentation**
   - Complete API documentation for new endpoints
   - Update user documentation with new features
   - Document ontology data model

## Running the System

### Starting the Unified Ontology Server

```bash
./start_unified_ontology_server.sh
```

### Stopping the Server

```bash
./stop_unified_ontology_server.sh
```

### Creating a New Ontology-Focused Branch

```bash
./scripts/create_ontology_branch.sh [custom-branch-name]
```

## Technical Notes

- The unified ontology server runs on port 5002 by default
- ProEthica communicates with the ontology server via HTTP
- Case analysis modules extend the base module functionality
- Temporal reasoning is handled by specialized ontology structures
