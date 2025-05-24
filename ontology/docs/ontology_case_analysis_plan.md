# Ontology-Based Case Analysis Plan Using McLaren's Extensional Definition Approach

This document outlines the implementation plan for enhancing ProEthica with ontology-based case analysis capabilities using McLaren's extensional definition approach.

## Overview

The ontology-focused branch extends ProEthica to leverage its ontology system for sophisticated case analysis. By incorporating McLaren's extensional definition methodology, we can analyze engineering ethics cases to identify principle instantiations, principle conflicts, and operationalization techniques, providing more nuanced ethical reasoning.

## McLaren's Extensional Definition Approach

McLaren's approach focuses on:

1. **Principle Instantiations**: How abstract principles apply to concrete facts in cases
2. **Principle Conflicts**: Where two or more principles conflict in a specific context
3. **Operationalization Techniques**: Methods for connecting abstract principles to concrete facts
4. **Extensional Definitions**: Defining principles through their applications in concrete cases

These elements have been incorporated into our ontology schema and database design to enable comprehensive case analysis.

## Key Components

### 1. Ontology Extensions

We've extended our existing ontologies with:

- **McLaren Extensional Definitions Ontology**: A specialized ontology capturing the concepts from McLaren's approach
- **Operationalization Techniques**: Ontological representation of the nine operationalization techniques
- **Resolution Types**: Classes for different ways principle conflicts can be resolved

### 2. Database Schema for McLaren's Approach

Our implementation includes tables for:

- `principle_instantiations`: Stores how principles apply to concrete facts
- `principle_conflicts`: Records conflicts between principles and their resolutions
- `case_operationalization`: Tracks operationalization techniques used in cases
- `case_triples`: Stores RDF triples representing the case analysis

### 3. Direct Processing Scripts

To efficiently process cases without Flask application dependencies:

- `direct_create_mclaren_tables.py`: Creates necessary database tables
- `direct_import_nspe_cases.py`: Imports NSPE cases directly into the database
- `direct_process_nspe_cases.py`: Processes cases using McLaren's approach
- `setup_ontology_case_analysis_direct.sh`: Runs the entire workflow automatically

## Implementation Plan

### Phase 1: Core Infrastructure (Completed)

- [x] Create McLaren extensional definitions ontology
- [x] Implement database schema for McLaren's approach
- [x] Develop direct processing scripts for case analysis
- [x] Create automated setup script

### Phase 2: ProEthica Integration (In Progress)

- [ ] Extend ProEthica API for McLaren-based case analysis
- [ ] Implement UI components for visualizing principle instantiations and conflicts
- [ ] Create visualization tools for operationalization techniques

### Phase 3: Advanced Features (Planned)

- [ ] Implement cross-case analysis to identify patterns
- [ ] Add support for extracting common resolution patterns
- [ ] Develop machine learning integration for improved principle detection
- [ ] Create ethical reasoning enhancements based on extensional definitions

## Technical Architecture

### McLaren Case Analysis Module

The case analysis module (`mcp/modules/mclaren_case_analysis_module.py`) provides:

1. **Principle Instantiation Extraction**: Identify where principles apply to specific facts
2. **Principle Conflict Detection**: Detect conflicts between principles in cases
3. **Operationalization Technique Identification**: Identify techniques used in cases
4. **Triple Generation**: Convert analyses to RDF triples for the ontology

### Database Schema

```sql
-- Table for principle instantiations
CREATE TABLE principle_instantiations (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL,
    principle_uri TEXT NOT NULL,
    principle_label TEXT NOT NULL,
    fact_text TEXT NOT NULL,
    fact_context TEXT,
    confidence FLOAT NOT NULL DEFAULT 0.5,
    is_negative BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Table for principle conflicts
CREATE TABLE principle_conflicts (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL,
    principle1_uri TEXT NOT NULL,
    principle2_uri TEXT NOT NULL,
    principle1_label TEXT NOT NULL,
    principle2_label TEXT NOT NULL,
    resolution_type TEXT,
    context TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Table for operationalization techniques
CREATE TABLE case_operationalization (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL,
    technique_name TEXT NOT NULL,
    technique_matches JSONB NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 0.5,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Table for RDF triples representing case analyses
CREATE TABLE case_triples (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL,
    triples TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
```

### API Endpoints (Planned)

New API endpoints for McLaren case analysis:

- `GET /api/cases/{case_id}/principle-instantiations`: Get principle instantiations for a case
- `GET /api/cases/{case_id}/principle-conflicts`: Get principle conflicts for a case
- `GET /api/cases/{case_id}/operationalization-techniques`: Get operationalization techniques for a case
- `GET /api/cases/{case_id}/extensional-definitions`: Get extensional definitions for principles used in a case
- `POST /api/cases/{case_id}/analyze-mclaren`: Trigger McLaren analysis for a case

## Integration with the MCP System

The McLaren case analysis module is integrated with the existing MCP system:

1. Registered as a module with the unified ontology server
2. Exposes McLaren analysis capabilities through MCP tools
3. Provides access to case analysis results via MCP resources

## UI Enhancements (Planned)

The ProEthica UI will be enhanced with:

1. McLaren case analysis view showing:
   - Principle instantiations with their concrete facts
   - Principle conflicts and their resolutions
   - Operationalization techniques used in the case
   - Extensional definitions derived from multiple cases

2. Interactive visualizations:
   - Principle conflict graphs
   - Principle-fact association networks
   - Operationalization technique frequency charts

## Testing Plan

1. **Unit Tests**: Test individual functions in the McLaren module
2. **Integration Tests**: Test integration with the unified ontology server
3. **End-to-End Tests**: Test the full workflow from case import to analysis
4. **Case Studies**: Test with real-world NSPE engineering ethics cases

## Future Extensions

1. **Enhanced Principle Detection**: Improve detection of principles in case text
2. **Cross-Case Learning**: Learn from multiple cases to improve analysis
3. **UI Integration**: Provide rich UI for exploring McLaren analyses
4. **LLM Integration**: Use LLMs to enhance the quality of principle extraction

## Resources

- Engineering ethics cases from the NSPE database
- McLaren's extensional definition ontology
- Engineering ethics ontology for domain-specific concepts
- SPARQL for ontology queries
- LLMs for principle detection and analysis
