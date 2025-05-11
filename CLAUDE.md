# ProEthica AI Ethical Decision-Making System

This document tracks the development of the ProEthica AI Ethical Decision-Making System, recording key implementation details, architecture decisions, and development tasks.

## Recent Updates

### May 11, 2025 - Temporal Module for Ontology Enhancement

Created a new temporal module (`mcp/modules/temporal_module.py`) for integration into the unified ontology server architecture. This module provides temporal functionality for representing, analyzing, and querying ethical cases in their temporal context.

Key implementations:
1. Integrated temporal functionality into the modular architecture of the unified ontology server
2. Removed dependency on the standalone `add_temporal_functionality.py` script
3. Created proper tool registration through the BaseModule system
4. Established consistent pattern following the unified server architecture

This work aligns with our ontology-focused development branch that concentrates on case analysis and representation capabilities.

### May 11, 2025 - Ontology-Focused Branch Creation

Created a new branch focused on enhancing the ontology functionality within ProEthica, particularly for engineering ethics applications. This branch builds on the realm-integration work and focuses on implementing McLaren's approach to case analysis and ethical reasoning.

Key changes:

1. **Unified Ontology Server Configuration**
   - Modified the Unified Ontology Server to run on port 5002 (changed from 5001)
   - Updated all references to the server port in various components:
     - `run_unified_mcp_server.py`
     - `scripts/verify_proethica_ontology.py`
     - `app/routes/ontology_routes.py`

2. **Management Scripts**
   - Created `scripts/create_ontology_branch.sh` for setting up the ontology-focused branch
   - Created `start_unified_ontology_server.sh` and `stop_unified_ontology_server.sh` for server management
   - Made all scripts executable

3. **Documentation**
   - Created `docs/ontology_case_analysis_plan.md` outlining the implementation plan for ontology-based case analysis
   - Organized the implementation into four phases:
     1. Infrastructure Setup (completed)
     2. Case Analysis Implementation
     3. Case Transformation
     4. Analysis and Visualization

## System Architecture

### Core Components

1. **Flask Web Application**
   - Main web interface and API
   - Handles user authentication, scenario management, and document processing
   - Connects to the various subsystems

2. **Database Layer**
   - PostgreSQL with pgvector extension for embeddings
   - Stores cases, scenarios, user data, analysis results, and ontology information

3. **Ontology System**
   - Engineering ethics formal ontology
   - Provides structured representation of ethical principles, roles, responsibilities
   - Now enhanced with case analysis capabilities through the Unified Ontology Server

4. **Unified Ontology Server**
   - Modular server providing ontology access and querying
   - JSON-RPC interface for tool access
   - Modules include:
     - Query Module: Basic ontology querying
     - Case Analysis Module: Analysis of ethics cases using the ontology
     - Temporal Module: Representation of cases in temporal context

5. **Agent System**
   - LLM-powered agents for ethical reasoning
   - Simulation orchestration and character interactions
   - Case analysis and report generation

### MCP Integration

The Model Context Protocol (MCP) is used for:
1. Providing access to the ontology via the Unified Ontology Server
2. Enabling case analysis through specialized tools
3. Connecting the Flask application to ontology capabilities

## Development Roadmap

### Current Focus: Ontology-Based Case Analysis

The current development focus is on implementing McLaren's methodology for engineering ethics case analysis:

1. Extensional definitions of ethics principles through concrete examples
2. Temporal representation of ethics cases for analysis
3. Case-based reasoning to find similar cases and principles
4. Operationalization of abstract principles through specific case instantiations

### Next Steps

1. Complete the case analysis functionality in the Case Analysis Module
2. Implement entity extraction from case text
3. Develop the temporal representation system
4. Create visualization components for case analysis
5. Integrate with the simulation system

## Technical Notes

### Running the Unified Ontology Server

The Unified Ontology Server can be managed using:

```bash
# Start the server (runs on port 5002)
./start_unified_ontology_server.sh

# Stop the server
./stop_unified_ontology_server.sh
```

### Creating a New Ontology-Focused Branch

To create a new branch for ontology development:

```bash
# Create branch with default name "ontology-focused"
./scripts/create_ontology_branch.sh

# Create branch with custom name
./scripts/create_ontology_branch.sh my-custom-branch-name
```

### Testing Ontology Server Connectivity

To verify the connection between the Flask app and the Unified Ontology Server:

```bash
python scripts/verify_proethica_ontology.py
```

## References

- McLaren, B. M. (2003). Extensionally Defining Principles and Cases in Ethics: An AI Model. Artificial Intelligence Journal, 150, 145-181.
