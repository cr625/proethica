# ProEthica Intermediate Ontology Guide

## Overview

The ProEthica system uses a layered ontology approach to model ethical domains:

1. **Foundation Layer**: BFO Core Ontology (Basic Formal Ontology)
2. **Intermediate Layer**: ProEthica Intermediate Ontology
3. **Domain Layer**: Domain-specific ethics ontologies (e.g., Engineering Ethics)
4. **Instance Layer**: World-specific instances and scenarios

This guide explains how to use the intermediate ontology as a bridge between BFO and domain-specific ontologies, and how to create your own domain-specific worlds.

## Ontology Structure

```
Foundation (BFO)
     ↓
Intermediate (proethica-intermediate.ttl)
     ↓
Domain (engineering-ethics.ttl, legal-ethics.ttl, etc.)
     ↓
World Instances (scenarios, cases, entities)
```

## Core Entity Categories

The intermediate ontology defines six core entity categories that form the foundation of the ProEthica system:

1. **Roles**: Professional positions and responsibilities
2. **Conditions**: States, situations, and contexts
3. **Resources**: Tangible and intangible assets
4. **Events**: Occurrences, happenings, situations
5. **Actions**: Activities, processes, interventions
6. **Decisions**: Choices and determinations

Each of these categories is properly aligned with BFO concepts and provides the structure for domain-specific extensions.

## How Entities Appear in the UI

The world detail page displays entities from the ontology under "World Entities" in five categories:
- Roles
- Conditions
- Resources
- Events
- Actions (includes Decisions)

For an entity class to appear in these categories, it must:
1. Be a subclass of the corresponding intermediate ontology class (`proeth:Role`, `proeth:Condition`, etc.)
2. Have the `rdf:type proeth:EntityType` triple to mark it for extraction
3. Be included in the ontology source specified in the world configuration

## Creating Domain-Specific Ontologies

To create a new domain-specific ontology:

1. Create a new TTL file (e.g., `your-domain-ethics.ttl`)
2. Import both BFO and the intermediate ontology:
   ```ttl
   owl:imports <http://purl.obolibrary.org/obo/bfo.owl> ;
   owl:imports <http://proethica.org/ontology/intermediate> ;
   ```
3. Define domain-specific classes that extend the intermediate classes
4. Mark entity classes for extraction using `rdf:type proeth:EntityType`
5. Add appropriate labels and descriptions

### Example Domain Class Definition

```ttl
:LegalAdvocateRole rdf:type owl:Class ;
    rdf:type proeth:EntityType ;         # Mark for extraction
    rdfs:subClassOf proeth:Role ;        # Inherit from intermediate class
    rdfs:label "Legal Advocate Role"@en ;
    rdfs:comment "The role of representing and advocating for a client in legal proceedings"@en .
```

## Using Ontologies with Worlds

To use an ontology with a world in ProEthica:

1. Upload your ontology file to the `mcp/ontology/` directory
2. Create a new world in the ProEthica UI
3. Set the "Ontology Source" field to your ontology file name (e.g., `legal-ethics.ttl`)
4. Save the world

The system will automatically extract entity classes from your ontology and display them on the world detail page under "World Entities".

## Testing Ontology Extraction

You can test your ontology with the provided script:

```bash
python scripts/test_intermediate_ontology.py
```

Add the `--create-worlds` flag to automatically create test worlds:

```bash
python scripts/test_intermediate_ontology.py --create-worlds
```

## Best Practices

1. **Proper Inheritance**: Always extend from the appropriate intermediate class
2. **Mark for Extraction**: Use `rdf:type proeth:EntityType` for classes you want displayed
3. **Clear Labeling**: Provide clear, descriptive labels and comments
4. **Domain Specificity**: Create domain-specific classes rather than using intermediate classes directly
5. **Relationship Modeling**: Use appropriate object properties to model relationships between entities

## Engineering Ethics Example

The `engineering-ethics.ttl` ontology demonstrates how to extend the intermediate ontology for a specific domain:

- It defines engineering-specific roles (StructuralEngineerRole, ConsultingEngineerRole)
- It models domain-specific conditions (SafetyHazard, CodeViolation)
- It includes domain-specific resources (EngineeringReport, BuildingCode)
- It defines relevant events (InspectionEvent, HazardDiscoveryEvent)
- It models domain actions and decisions (HazardReportingAction, WhistleblowingDecision)

This provides a template for creating other domain-specific ontologies.
