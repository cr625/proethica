# McLaren's Extensional Definition Implementation Tracker

This document tracks the progress of implementing Bruce McLaren's extensional definition approach to analyze engineering ethics cases.

## Project Overview

Bruce McLaren's extensional definition approach, as described in his 2003 paper "Extensionally Defining Principles and Cases in Ethics: an AI Model," provides a systematic framework for analyzing ethical cases using nine operationalization techniques:

1. **Principle Instantiation**: Linking abstract principles to specific facts
2. **Fact Hypotheses**: Hypothesizing facts that affect principle application
3. **Principle Revision**: Evolving principle interpretation over time
4. **Conflicting Principles Resolution**: Resolving conflicts between principles
5. **Principle Grouping**: Grouping related principles to strengthen an argument
6. **Case Instantiation**: Using past cases as precedent
7. **Principle Elaboration**: Elaborating principles from past cases
8. **Case Grouping**: Grouping related cases to support an argument
9. **Operationalization Reuse**: Reusing previous applications

The goal of this project is to implement this approach within the ProEthica system to provide robust ethical analysis capabilities.

## Current Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Database Tables | ✅ Complete | Created direct_create_mclaren_tables.py script |
| Case Processing | ✅ Complete | Created direct_process_nspe_cases.py script |
| McLaren Module | 🟡 Partial | Basic implementation exists with mock server |
| Integration with Ontology | ⚪ Planned | Will link with engineering ethics ontology |
| UI Components | ⚪ Planned | Will create visualizations of analysis |
| API Endpoints | ⚪ Planned | Will add endpoints for case analysis |

### Database Schema

We've implemented the following tables to store McLaren's extensional definition analysis:

- `document`: Stores basic case information
- `principle_instantiations`: Records instances of principles in cases
- `principle_conflicts`: Records conflicts between principles
- `case_operationalization`: Records operationalization techniques used
- `case_triples`: Stores RDF triples representing the case analysis

### Case Processing Tools

We've created the following scripts to facilitate case analysis:

1. **setup_ontology_case_analysis_direct.sh**: Main setup script that creates tables and processes cases
2. **direct_create_mclaren_tables.py**: Creates necessary database tables
3. **direct_process_nspe_cases.py**: Processes cases using McLaren's approach
4. **batch_process_nspe_cases.py**: Batch processes multiple cases
5. **inspect_cases.py**: Utility to inspect case data structure

## NSPE Case Import

We have successfully imported and processed NSPE cases from these sources:

1. **Original NSPE Cases**: 7 cases from data/nspe_cases.json
2. **Modern NSPE Cases**: 22 cases from data/modern_nspe_cases.json

### Case Processing Options

Cases can be processed in the following ways:

1. **Individual case processing**:
   ```bash
   ./setup_ontology_case_analysis_direct.sh "89-7-1"  # Process by case number
   ```

2. **Batch processing**:
   ```bash
   # Process all original cases
   ./scripts/batch_process_nspe_cases.py
   
   # Process modern cases
   ./scripts/batch_process_nspe_cases.py --modern
   
   # Process specific cases
   ./scripts/batch_process_nspe_cases.py --case-numbers "89-7-1" "76-4-1"
   
   # Limit the number of cases
   ./scripts/batch_process_nspe_cases.py --limit 5
   
   # Dry run (preview without processing)
   ./scripts/batch_process_nspe_cases.py --dry-run
   ```

## Analysis Techniques Status

| McLaren's Technique | Implementation Status |
|--------------------|----------------------|
| Principle Instantiation | 🟡 Basic implementation |
| Fact Hypotheses | ⚪ Planned |
| Principle Revision | ⚪ Planned |
| Conflicting Principles Resolution | 🟡 Basic implementation |
| Principle Grouping | ⚪ Planned |
| Case Instantiation | ⚪ Planned |
| Principle Elaboration | ⚪ Planned |
| Case Grouping | ⚪ Planned |
| Operationalization Reuse | ⚪ Planned |

## Integration with Ontology

The current implementation uses a mock ontology server for testing. Full integration with the engineering ethics ontology is planned to enable more sophisticated analysis capabilities, including:

1. Mapping case entities to ontology concepts
2. Identifying relationships between case entities
3. Reasoning about temporal aspects of cases
4. Generating recommendations based on ontology-guided analysis

## Next Steps

1. **Enhance McLaren Module**: Complete the implementation of all nine operationalization techniques
2. **Integrate with Ontology**: Connect case analysis with the engineering ethics ontology
3. **Improve UI**: Create visualizations for case analysis results
4. **Add API Endpoints**: Develop API endpoints for case analysis
5. **Cross-Case Analysis**: Implement functionality to compare multiple cases

## Known Issues

1. The current implementation shows warnings about Flask app context not being available, since we're bypassing the Flask-SQLAlchemy layer.
2. The document table needs to be created manually since it wasn't part of the original schema.

## Recent Updates

- 2025-05-11: Created batch_process_nspe_cases.py script for batch processing cases
- 2025-05-11: Fixed direct_create_mclaren_tables.py to create document table
- 2025-05-11: Updated direct_process_nspe_cases.py to handle case numbers
- 2025-05-11: Created inspect_cases.py to examine case data structure
