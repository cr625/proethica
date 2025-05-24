# McLaren Engineering Ethics Case Guide

## Overview
This document describes how the ProEthica system implements the theoretical framework outlined in Bruce M. McLaren's 2003 paper "Extensionally Defining Principles and Cases in Ethics: an AI Model." The paper explores how abstract ethical principles gain meaning through their application to specific cases, creating extensional definitions that bridge the gap between abstract rules and concrete facts.

## Key Concepts from McLaren 2003

### Operationalization Techniques
McLaren identified nine operationalization techniques used by engineering ethics experts to connect abstract principles to specific case facts:

1. **Principle Instantiation**: Linking an abstract principle to specific factual elements in a case
2. **Fact Hypotheses**: Hypothesizing facts that affect how a principle applies
3. **Principle Revision**: Evolving a principle's interpretation over time
4. **Conflicting Principles Resolution**: Resolving conflicts between principles in a case
5. **Principle Grouping**: Grouping related principles to strengthen an argument
6. **Case Instantiation**: Using a past case as precedent by linking it to current case facts
7. **Principle Elaboration**: Elaborating or defining principles from past cases
8. **Case Grouping**: Grouping related cases to support an argument
9. **Operationalization Reuse**: Reusing previous applications of any technique

### The Gap Between Abstract and Concrete
McLaren's work addresses the challenge of applying abstract ethical principles (like "hold paramount the safety, health, and welfare of the public") to concrete situations. This gap between abstract rules and specific facts is bridged through operationalization, where experts show through examples how principles apply in specific contexts.

## Implementation in ProEthica

### Engineering Ethics World Description
The Engineering Ethics World in ProEthica provides the context for applying McLaren's framework. It defines:

- Core ethical principles that often create tensions when applied to specific situations
- Common ethical dilemmas where principles conflict (safety vs. confidentiality, etc.)
- Reasoning processes used to resolve ethical questions
- Key stakeholders affected by engineering decisions
- Resolution mechanisms used to address ethical challenges

### Case Repository
The Case Repository contains historical engineering ethics cases that demonstrate operationalization in practice. Each case shows how abstract principles were applied to specific factual scenarios.

### Triple-Based Representation
ProEthica implements RDF triple-based case representation to model the semantic relationships McLaren describes:

1. **Subject-Predicate-Object Structure**:
   - `Case:ThisCase involves:EthicalPrinciple ENG_ETHICS:PublicSafety`
   - `NSPE:CodeI.1 overrides NSPE:CodeII.1.c`

2. **Extensional Definition**: The triple representation directly models how principles gain meaning through concrete applications, capturing the extensional definitions McLaren describes

3. **Conflict Resolution**: Triples can explicitly represent conflict resolution through statements like:
   - `NSPE:CodeI.1 overrides NSPE:CodeII.1.c in Case:89-7-1`

### Supporting McLaren's Hypothesis
McLaren's hypothesis was that "extensionally defined principles, as well as cited past cases, can help in predicting the principles and cases that might be relevant in the analysis of new cases."

ProEthica supports this by:

1. **Case Comparison**: Enabling the comparison of new ethical dilemmas to historical cases based on their triple representations

2. **Principle Application Patterns**: Identifying patterns in how principles have been applied across multiple cases

3. **Conflict Resolution History**: Examining how conflicts between principles have been resolved in similar past scenarios

## Using the Triple-Based Case Interface

### Creating Triple-Based Cases
The Create Triple-Based Case interface allows users to:

1. Enter basic case information (title, description, source)
2. Define RDF namespaces for domain concepts
3. Create triples connecting the case to:
   - Ethical principles involved
   - NSPE codes referenced
   - Conflicts between principles
   - Case decision outcomes

### Triple Templates
To assist users, common engineering ethics patterns are provided as templates:
- Case involves Public Safety
- Case involves Confidentiality
- Conflict: Confidentiality vs Safety
- References specific NSPE codes
- Code overrides relationships

### Viewing and Editing Triples
Once created, cases with triple metadata provide:
- A table view of all triples
- Namespace definitions for context
- Ability to edit and add triples as analysis evolves

## Benefits of the Triple-Based Approach

1. **Semantic Relationships**: Explicitly represents the relationships between principles, cases, and facts

2. **Pattern Recognition**: Enables identification of patterns in ethical reasoning across cases

3. **Complex Queries**: Supports sophisticated queries like "Find all cases where public safety overrides confidentiality"

4. **Knowledge Accumulation**: Creates a growing knowledge base of extensionally defined ethical principles

5. **Integration**: Connects to broader semantic web and ontology frameworks
