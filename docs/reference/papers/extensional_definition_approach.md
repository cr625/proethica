# Extensional Definition Approach to Engineering Ethics Case Analysis

## Overview

This paper presents an implementation of Bruce McLaren's extensional definition approach for engineering ethics case analysis, combined with formal ontology integration and large language model (LLM) evaluation. The system establishes a framework for analyzing engineering ethics cases by extracting principle instantiations, identifying conflicts, and generating ontology-aligned representations.

## Background

Engineering ethics education and decision support systems typically rely on abstract principles that can be difficult to apply in concrete situations. McLaren's extensional definition approach (2003) addresses this challenge by defining principles through concrete case examples rather than abstract definitions alone. This approach identifies nine operationalization techniques that bridge abstract principles and concrete cases.

## Methodology

### 1. Extensional Definition Framework

We implemented McLaren's extensional definition approach through a computational framework that:

- Identifies instances of abstract principles in concrete case facts (principle instantiation)
- Detects conflicts between competing principles in cases (principle conflict resolution)
- Extracts operationalization techniques used in ethical reasoning
- Generates RDF triples representing the case analysis

### 2. Ontology Integration

The system integrates with a formal engineering ethics ontology built on the Basic Formal Ontology (BFO) foundation. This integration:

- Maps case entities to ontology concepts
- Represents relationships between case entities using ontological relations
- Provides a formal structure for ethical reasoning
- Enables semantic queries across multiple cases

Our ontology structure includes:

- Classes for principle instantiations and conflicts
- Properties linking principles to concrete facts
- Representations of all nine operationalization techniques
- Temporal aspects of ethical decision-making

### 3. Case Processing Pipeline

The system includes a robust pipeline for processing engineering ethics cases:

- Ingestion of cases from the National Society of Professional Engineers (NSPE)
- Extraction of principle instantiations and conflicts
- Identification of operationalization techniques
- Generation of RDF triples
- Storage in a structured database

### 4. LLM Evaluation Approach

A key innovation in our approach is the use of LLMs to evaluate ethical reasoning through:

1. **Case-based Learning**: Training LLMs on extensionally defined principles from existing cases
2. **Principle Application**: Testing if LLMs can identify relevant principles in new cases
3. **Leave-one-out Validation**: Withholding case results during testing to evaluate if the LLM reaches similar conclusions to human experts
4. **Conflict Resolution**: Assessing LLM's ability to handle conflicts between competing principles

## Preliminary Results

The system has successfully processed both historical and modern NSPE cases, extracting:
- Principle instantiations connecting abstract principles to concrete facts
- Conflicts between competing principles
- Operationalization techniques used in ethical reasoning

Initial testing suggests that LLMs trained on extensionally defined principles can identify relevant principles in new cases with promising accuracy.

## Future Work

Planned extensions include:
1. Complete implementation of all nine operationalization techniques
2. Enhanced conflict resolution mechanisms
3. Cross-case analysis to identify patterns in ethical reasoning
4. Comprehensive evaluation of LLM performance against human expert judgments
5. Development of a decision support system for engineering ethics education and practice

## Conclusion

The integration of McLaren's extensional definition approach with formal ontologies and LLM evaluation provides a promising framework for engineering ethics education and decision support. By grounding abstract principles in concrete cases and leveraging modern AI techniques, this approach has the potential to bridge the gap between ethical theory and practice in engineering.

---

*Keywords*: engineering ethics, extensional definition, ontology, large language models, case-based reasoning
