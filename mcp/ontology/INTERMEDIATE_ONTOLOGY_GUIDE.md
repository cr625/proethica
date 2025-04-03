# ProEthica Intermediate Ontology Guide

This guide explains the structure and usage of the ProEthica Intermediate Ontology, which serves as a bridge between the Basic Formal Ontology (BFO) and domain-specific ontologies like the Engineering Ethics Ontology.

## Purpose

The Intermediate Ontology provides:

1. A standardized set of entity types that can be used across different ethical domains
2. A consistent framework for representing ethical scenarios
3. Alignment with BFO to ensure philosophical rigor
4. A foundation for domain-specific ontologies to build upon

## Core Entity Types

The Intermediate Ontology defines six core entity types that are recognized by the ProEthica system:

### 1. Role

Roles represent professional positions and responsibilities. They are based on BFO's role class (BFO_0000023).

Key properties:
- `hasTier`: Indicates the level or tier of a role
- `hasCapability`: Relates a role to capabilities it possesses
- `hasResponsibility`: Relates a role to responsibilities it entails

Example usage in a domain ontology:
```
:StructuralEngineerRole rdf:type owl:Class ;
    rdf:type proeth:EntityType ;
    rdf:type proeth:Role ;
    rdfs:subClassOf :EngineeringRole ;
    rdfs:label "Structural Engineer Role"@en ;
    rdfs:comment "The role of an engineer who analyzes and designs structural systems"@en ;
    proeth:hasCapability :StructuralAnalysisCapability ;
    proeth:hasCapability :StructuralDesignCapability .
```

### 2. Condition

Conditions represent states, situations, and contexts. They are based on BFO's quality class (BFO_0000019).

Key properties:
- `severity`: Indicates the severity level of a condition (1-10)
- `location`: Indicates the location where a condition applies
- `duration`: Indicates how long a condition persists

### 3. Resource

Resources represent tangible and intangible assets. They are based on BFO's material entity class (BFO_0000040).

Key properties:
- `quantity`: Indicates the quantity of a resource
- `resourceOwner`: Indicates who owns or controls a resource
- `resourceValue`: Indicates the importance or value of a resource

### 4. Event

Events represent occurrences, happenings, and situations. They are based on BFO's process class (BFO_0000015).

Key properties:
- `eventSeverity`: Indicates the severity or impact level of an event
- `eventLocation`: Indicates where an event takes place
- `eventDuration`: Indicates how long an event lasts

### 5. Action

Actions represent activities, processes, and interventions. They are based on BFO's process class (BFO_0000015).

Key properties:
- `actionPriority`: Indicates the priority level of an action
- `actionDuration`: Indicates how long an action takes
- `actionAgent`: Indicates who performs an action

### 6. Decision

Decisions represent choices and determinations. They are a subclass of Action.

Key properties:
- `decisionImpact`: Describes the impact or consequences of a decision
- `decisionCriteria`: Factors considered in making a decision
- `decisionAlternatives`: Alternative options considered in the decision

## Relationship Properties

The Intermediate Ontology also defines several relationship properties that connect entities:

- `involves`: General relation indicating involvement between entities
- `precedes`: Indicates temporal precedence between processes
- `resultsIn`: Indicates a causal relationship
- `participatesIn`: Relates an agent to a process they participate in
- `hasRole`: Relates an agent to a role they have
- `usesResource`: Relates an action to resources it uses
- `hasCondition`: Relates an entity to conditions that apply to it
- `requiresDecision`: Relates an ethical dilemma to the decision it requires

## Creating Domain-Specific Ontologies

When creating a domain-specific ontology based on the Intermediate Ontology:

1. Import both the BFO and the Intermediate Ontology:
   ```
   owl:imports <http://purl.obolibrary.org/obo/bfo.owl> ;
   owl:imports <http://proethica.org/ontology/intermediate> ;
   ```

2. Define domain-specific subclasses for each entity type:
   ```
   :EngineeringRole rdfs:subClassOf proeth:Role ;
   :EngineeringCondition rdfs:subClassOf proeth:Condition ;
   ```

3. Mark instances with the appropriate entity types:
   ```
   :StructuralEngineerRole rdf:type proeth:EntityType ;
                           rdf:type proeth:Role ;
   ```

4. Use the properties defined in the Intermediate Ontology:
   ```
   :StructuralEngineerRole proeth:hasCapability :StructuralAnalysisCapability ;
   ```

5. Define domain-specific object properties as needed:
   ```
   :documentsHazard rdfs:domain :EngineeringReport ;
                    rdfs:range :SafetyHazard ;
   ```

## ProEthica System Integration

The ProEthica system recognizes entities marked with the appropriate entity types:

- `proeth:Role` for roles
- `proeth:ConditionType` for conditions
- `proeth:ResourceType` for resources
- `proeth:EventType` for events
- `proeth:ActionType` for actions and decisions

These entities will appear in the "World Entities" section of the ProEthica application, categorized by type.

## Best Practices

1. Always mark domain-specific entities with both `rdf:type proeth:EntityType` and the specific type (e.g., `rdf:type proeth:Role`)
2. Provide clear labels and comments for all entities
3. Use the properties defined in the Intermediate Ontology when possible
4. Define domain-specific properties only when needed
5. Use the hasCapability property to specify what a role can do
6. Align all entities with the appropriate BFO classes
