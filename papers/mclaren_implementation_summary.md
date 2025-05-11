# McLaren's Extensional Definition Approach: Implementation Summary

This document provides an overview of our implementation of Bruce McLaren's extensional definition approach for engineering ethics case analysis, combining three key aspects of our work: the theoretical approach, system architecture, and experimental design.

## Project Overview

We have developed a comprehensive system for analyzing engineering ethics cases using Bruce McLaren's extensional definition approach (2003). This system:

1. Processes cases from the National Society of Professional Engineers (NSPE)
2. Identifies instances of abstract principles in concrete facts
3. Detects conflicts between competing principles
4. Recognizes operationalization techniques used in ethical reasoning
5. Generates ontology-aligned representations of case analyses
6. Evaluates LLM performance in ethical reasoning using extensional definitions

## Key Components

### Database Schema

We've implemented a robust database schema for storing McLaren's case analysis:

- `document`: Stores case information
- `principle_instantiations`: Records concrete applications of abstract principles
- `principle_conflicts`: Tracks conflicts between competing principles
- `case_operationalization`: Identifies operationalization techniques used
- `case_triples`: Stores RDF triples representing the case analysis

### Processing Pipeline

The case processing pipeline includes:

1. **Case Ingestion**: Loading cases from NSPE sources
2. **Analysis**: Applying McLaren's approach to extract principle instantiations, conflicts, etc.
3. **Ontology Mapping**: Connecting case elements to our engineering ethics ontology
4. **Triple Generation**: Creating RDF triples to represent the case analysis
5. **Storage**: Storing results in our database for further analysis and application

### Ontology Integration

The system integrates with our engineering ethics ontology, which:

- Is built on the Basic Formal Ontology (BFO) foundation
- Includes classes for principle instantiations and conflicts
- Represents all nine operationalization techniques
- Enables semantic reasoning about ethical cases

### LLM Evaluation Framework

Our experimental design for evaluating LLM performance includes:

1. **Training on Extensional Definitions**: Using analyzed cases to train LLMs
2. **Leave-one-out Testing**: Testing on new cases with results withheld
3. **Comparative Analysis**: Comparing LLM outputs with expert consensus
4. **Multiple Condition Testing**: Comparing baseline, extensional definition, and ontology-enhanced approaches

## Implemented Scripts and Tools

We've created a suite of scripts and tools for case analysis:

- **Database Setup**: `direct_create_mclaren_tables.py` creates necessary tables
- **Case Processing**: `direct_process_nspe_cases.py` analyzes cases using McLaren's approach
- **Batch Processing**: `batch_process_nspe_cases.py` processes multiple cases efficiently
- **Case Inspection**: `inspect_cases.py` examines case data structure and metadata
- **Setup Script**: `setup_ontology_case_analysis_direct.sh` orchestrates the case analysis process

## Current Status and Next Steps

### Completed Work

- Basic framework for McLaren's extensional definition approach
- Database schema for storing analysis results
- Case processing pipeline for NSPE cases
- Integration with engineering ethics ontology
- Initial experimental design for LLM evaluation

### Next Steps

1. **Enhanced Implementation**: Complete all nine operationalization techniques
2. **Full Integration**: Connect with the existing ProEthica UI and API
3. **Experimental Execution**: Run the LLM evaluation experiments
4. **UI Development**: Create visualizations for case analysis
5. **Cross-Case Analysis**: Implement tools for comparing multiple cases

## Conclusion

Our implementation of McLaren's extensional definition approach creates a bridge between abstract ethical principles and concrete engineering cases. By grounding principles in case examples and leveraging formal ontology, we provide a more nuanced approach to engineering ethics education and decision support. The integration with LLMs opens new possibilities for AI-assisted ethical reasoning while maintaining the rigor of established engineering ethics frameworks.

The system demonstrates how computational approaches can enhance ethical reasoning without reducing it to simplistic rule following, maintaining the nuanced contextual understanding that characterizes expert ethical judgment.

## References

- McLaren, B. M. (2003). Extensionally Defining Principles and Cases in Ethics: an AI Model. Artificial Intelligence, 150(1-2), 145-181.
- Davis, M. (1998). Thinking like an engineer: Studies in the ethics of a profession. Oxford University Press.
- Guarino, N., & Welty, C. (2002). Evaluating ontological decisions with OntoClean. Communications of the ACM, 45(2), 61-65.
