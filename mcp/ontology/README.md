# ProEthica Engineering Ethics Ontology

## Overview

This directory contains a set of ontologies designed to represent engineering ethics cases, principles, and reasoning within the Basic Formal Ontology (BFO) framework. The ontologies follow a layered architecture:

1. **Foundation Layer**: BFO Core Ontology (imported)
2. **Mid-Level Layer**: Agent-Role Ontology
3. **Domain Layer**: Engineering Ethics Ontology
4. **Instance Layer**: Case-specific ontologies (e.g., NSPE Case 89-7-1)

This structure enables the representation of case-based ethical reasoning in engineering while maintaining philosophical rigor through BFO alignment.

## Ontology Files

- **bfo-core.ttl**: Basic Formal Ontology core concepts (foundation)
- **agent-role-ontology.ttl**: Mid-level ontology linking BFO to domain concepts
- **engineering-ethics.ttl**: Domain-specific ontology for engineering ethics
- **nspe-case-89-7-1.ttl**: Instance-level representation of NSPE BER Case 89-7-1

## Architectural Design

### Foundation Layer: BFO Core

The Basic Formal Ontology (BFO) provides a rigorous upper-level framework consisting of:

- **Continuants**: Entities that persist through time (e.g., material entities, roles)
- **Occurrents**: Entities that unfold in time (e.g., processes, events)

BFO offers a foundation for representing both physical entities (engineers, buildings) and abstract concepts (obligations, principles) in a consistent philosophical framework.

### Mid-Level Layer: Agent-Role Ontology

The Agent-Role ontology bridges BFO's abstract concepts to more specific domain concepts:

- **Agent**: Extends BFO's independent continuant, representing entities capable of action
- **Character**: Subclass of HumanAgent for specific individuals in scenarios 
- **Role**: Aligns with BFO's role concept, representing the social positions agents occupy
- **EthicalPrinciple**: Framework for representing normative guidance as generically dependent continuants
- **EthicalObligation**: Represents duties arising from principles or professional codes

Key object properties include:
- `hasRole`: Links agents to their roles
- `realizesRole`: Links processes to the roles they realize
- `hasObligation`: Links agents to their ethical obligations

### Domain Layer: Engineering Ethics Ontology

The Engineering Ethics ontology extends the mid-level with engineering-specific concepts:

- **Professional Roles**: InspectionEngineerRole, ConsultantRole, DesignEngineerRole, etc.
- **Ethical Principles**: PublicSafetyPrinciple, ConfidentialityPrinciple, etc.
- **Engineered Entities**: Building, Infrastructure, EngineeringSystem, etc.
- **Engineering Processes**: InspectionProcess, EngineeringProcess, etc.
- **Ethical Dilemmas**: ConfidentialityVsSafetyDilemma, CompetencyVsClientWishesDilemma, etc.

This ontology also defines key classes for operationalization:
- `Role`: For role-based operationalization
- `ConditionType`: For condition-based operationalization
- `ResourceType`: For resource-based operationalization
- `EventType`: For event-based operationalization
- `ActionType`: For action-based operationalization

### Instance Layer: Case-Specific Ontologies

Case-specific ontologies (e.g., nspe-case-89-7-1.ttl) instantiate the concepts from higher layers:

- Specific individuals (EngineerA, ClientX)
- Physical entities (ApartmentBuilding, StructuralReport)
- Events and actions (BuildingInspection, NonDisclosureEvent)
- Role instances (InspectionEngineerRoleInstance)
- Ethical dilemmas (ConfidentialityVsSafetyDilemmaInstance)

## Core Concepts

### Role Operationalization

The most critical element of the ontology is the `Role` class, which:

1. Bridges abstract BFO concepts to concrete ethical situations
2. Connects agents to their obligations
3. Links to the processes that realize those roles
4. Provides an extensional definition mechanism for abstract principles

Through role instantiation, abstract principles like "preserve public safety" become operationalized in specific contexts.

### Ethical Dilemmas and Conflicts

The ontology models ethical dilemmas as:

- Situations where principles conflict (e.g., confidentiality vs. public safety)
- Instances of the `:EthicalDilemma` class
- Relating to specific principles via the `:involvesPrinciple` property
- Resolved through decisions that override certain principles (`:overridesPrinciple`)

### Temporal Relations

Case representations include temporal ordering of events using BFO's temporal relations:

- `precedes`: Indicates temporal ordering between occurrents
- Enables representation of the case narrative as a sequence of events
- Critical for understanding ethical constraints (e.g., knowing a hazard before failing to report it)

## Case Representation Example

NSPE Case 89-7-1 demonstrates how ethical dilemmas are represented:

1. An engineer discovers safety violations while under confidentiality agreement
2. The dilemma involves conflicting principles (confidentiality vs. public safety)
3. The NSPE Board ruled that public safety should override confidentiality
4. The case represents this as instances of principles, obligations, and decisions

## Future Extensions

The ontology framework can be extended to support:

1. **Additional engineering domains**: Civil, electrical, software engineering
2. **More ethical principles**: From other professional codes and frameworks
3. **Enhanced reasoning**: Adding more operationalization techniques from McLaren's work
4. **Integration with other ontologies**: Material science, legal frameworks, etc.

## References

- McLaren, B. M. (2003). Extensionally Defining Principles and Cases in Ethics: An AI Model. Artificial Intelligence Journal, 150, 145-181.
- National Society of Professional Engineers (NSPE). Board of Ethical Review (BER) Cases.
- Smith, B. et al. (2005). Basic Formal Ontology (BFO).
