# Ontology Enhancement Branch

This branch focuses on enhancing the ontology functionality within ProEthica, particularly for engineering ethics applications. It builds on the REALM integration work and implements McLaren's approach to case analysis and ethical reasoning.

## Overview

The ontology enhancement focuses on:

1. **Case Representation**: Implementing temporal representation of ethics cases
2. **Extensional Definitions**: Using concrete examples to define ethical principles
3. **Case-Based Reasoning**: Finding similarities between cases to guide ethical analysis
4. **Operationalization**: Making abstract principles concrete through specific case examples

## Setup

1. **Clone this branch**:
   ```bash
   git checkout ontology-enhancement-v1
   ```

2. **Set up the environment**:
   ```bash
   python -m pip install -r requirements.txt
   ```

3. **Start the unified ontology server**:
   ```bash
   ./start_unified_ontology_server.sh
   ```

## Architecture

The implementation follows a modular architecture with the following components:

1. **Unified Ontology Server**: Provides ontology access and query capabilities
2. **Case Analysis Module**: Extracts ontology entities from cases and performs analysis
3. **Temporal Module**: Manages temporal aspects of case representation
4. **Database Layer**: Stores case analysis results and relationships
5. **API Integration**: Connects the Flask application to the ontology system

## Key Improvements

- **Modular Architecture**: Better organized code with clear separation of concerns
- **Temporal Functionality**: Integrated temporal functionality directly into the unified server architecture
- **Enhanced Case Analysis**: Support for analyzing engineering ethics cases with ontology support
- **Better Documentation**: Comprehensive documentation of the ontology case analysis methodology

## Usage

To use the ontology case analysis functionality:

1. Start the unified ontology server:
   ```bash
   ./start_unified_ontology_server.sh
   ```

2. Access the case analysis tools through the Flask API at:
   ```
   http://localhost:5000/api/ontology/analyze_case/{id}
   ```

3. Stop the server when done:
   ```bash
   ./stop_unified_ontology_server.sh
   ```

## References

- McLaren, B. M. (2003). Extensionally Defining Principles and Cases in Ethics: An AI Model. Artificial Intelligence Journal, 150, 145-181.
