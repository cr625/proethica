# BFO Temporal Mappings for ProEthica Enhanced Temporal Dynamics

## Overview

ProEthica's Enhanced Temporal Dynamics extraction is **fully integrated with BFO (Basic Formal Ontology)** and **OWL-Time** ontologies. This document details the complete mapping architecture and where these mappings are defined.

## Executive Summary

**All 9 ProEthica core concepts are already mapped to BFO classes** in `proethica-core.ttl`. The enhanced temporal extraction system extends these mappings with OWL-Time integration for temporal reasoning.

## BFO Mappings in ProEthica Core

### Location
All BFO mappings are defined in:
- **File**: `/home/chris/onto/OntServe/ontologies/proethica-core.ttl`
- **Version**: 2.1.0 (updated 2025-08-30)
- **Import Declarations**:
  - `owl:imports <http://purl.obolibrary.org/obo/bfo.owl>`
  - `owl:imports <http://purl.obolibrary.org/obo/iao.owl>` (Information Artifact Ontology)
  - `owl:imports <http://purl.obolibrary.org/obo/ro.owl>` (Relations Ontology)

### Formal Specification D=(R,P,O,S,Rs,A,E,Ca,Cs)

#### 1. **Role (R)** → `bfo:0000023` (BFO:role)
```turtle
proeth-core:Role a owl:Class ;
    rdfs:subClassOf bfo:0000023 ;  # BFO:role
    rdfs:label "Role"@en ;
    rdfs:comment "A role that can be realized by processes involving professional duties and ethical obligations."@en .
```
**BFO Category**: Realizable Entity → Specifically Dependent Continuant

**Key Properties**:
- `ro:has_role` (from Relations Ontology)
- `bfo:inheres_in` (roles inhere in material entities)

---

#### 2. **Principle (P)** → `iao:0000030` (IAO:InformationContentEntity)
```turtle
proeth-core:Principle a owl:Class ;
    rdfs:subClassOf iao:0000030 ;  # IAO:information content entity
    rdfs:label "Principle"@en ;
    rdfs:comment "An information content entity representing ethical values and guidelines for conduct."@en .
```
**BFO Category**: Generically Dependent Continuant

**Key Properties**:
- `iao:is_about` (principles are about ethical conduct)

---

#### 3. **Obligation (O)** → `iao:0000030` (IAO:InformationContentEntity)
```turtle
proeth-core:Obligation a owl:Class ;
    rdfs:subClassOf iao:0000030 ;  # IAO:information content entity
    rdfs:label "Obligation"@en ;
    rdfs:comment "An information content entity expressing required actions or behaviors in professional contexts."@en .
```
**BFO Category**: Deontic ICE (Information Content Entity)

**Alternative Modeling**: Can also be modeled as `bfo:Disposition` for realizable entity pattern

**Key Properties**:
- `constrains` (what the obligation constrains)
- `appliesToRole` (which roles bear the obligation)
- `prescribes` (what actions are prescribed)

---

#### 4. **State (S)** → `bfo:0000019` (BFO:quality)
```turtle
proeth-core:State a owl:Class ;
    rdfs:subClassOf bfo:0000019 ;  # BFO:quality
    rdfs:label "State"@en ;
    rdfs:comment "A quality representing conditions that affect ethical decisions and professional conduct."@en .
```
**BFO Category**: Specifically Dependent Continuant

**Key Properties**:
- `bfo:inheres_in` (states inhere in systems or material entities)

---

#### 5. **Resource (Rs)** → `bfo:0000004` (BFO:independent continuant)
```turtle
proeth-core:Resource a owl:Class ;
    rdfs:subClassOf bfo:0000004 ;  # BFO:independent continuant
    rdfs:label "Resource"@en ;
    rdfs:comment "An independent continuant entity that serves as input or reference for professional activities."@en .
```
**BFO Category**: Independent Continuant

**Refinement**: Splits into two disjoint subclasses in `proethica-intermediate`:
- **MaterialResource** → `bfo:MaterialEntity`
- **InformationResource** → `iao:InformationContentEntity`

**Key Properties**:
- `proeth-core:refersToDocument` (links to IAO documents)
- `proeth-core:availableTo` (which roles have access)

---

#### 6. **Action (A)** → `bfo:0000015` (BFO:process) ✅
```turtle
proeth-core:Action a owl:Class ;
    rdfs:subClassOf bfo:0000015 ;  # BFO:process
    rdfs:label "Action"@en ;
    rdfs:comment "A process directed toward achieving specific goals in professional contexts."@en .
```
**BFO Category**: **Occurrent** (Process)

**Differentia from Event**: Actions **require an agent participant**

**Key Properties**:
- `ro:has_agent` (from Relations Ontology)
- `ro:has_participant`
- `ro:occurs_in`

**Formal Constraint**:
```turtle
proeth-core:Action rdfs:subClassOf [
    a owl:Restriction ;
    owl:onProperty [ owl:inverseOf proeth-core:performsAction ] ;
    owl:minCardinality "1"^^xsd:nonNegativeInteger
] .
```
Every action must have at least one agent.

---

#### 7. **Event (E)** → `bfo:0000015` (BFO:process) ✅
```turtle
proeth-core:Event a owl:Class ;
    rdfs:subClassOf bfo:0000015 ;  # BFO:process
    rdfs:label "Event"@en ;
    rdfs:comment "A process that occurs in professional contexts, which may or may not involve intentional agency."@en .
```
**BFO Category**: **Occurrent** (Process)

**Differentia from Action**: Events can be **neutral** (no required agent)

**Key Properties**:
- `ro:has_participant` (optional participants)
- `ro:occurs_in`

**Relationship**: Action can be considered a subclass of Event with agent restriction

---

#### 8. **Capability (Ca)** → `bfo:0000017` (BFO:realizable entity)
```turtle
proeth-core:Capability a owl:Class ;
    rdfs:subClassOf bfo:0000017 ;  # BFO:realizable entity
    rdfs:label "Capability"@en ;
    rdfs:comment "A realizable entity that can be realized by specific types of actions or processes in professional contexts."@en .
```
**BFO Category**: Realizable Entity → Specifically Dependent Continuant

**Note**: Changed from `bfo:Disposition` to more general `bfo:RealizableEntity` in v2.0.0

**Key Properties**:
- `bfo:inheres_in` (capabilities inhere in agents)
- `bfo:realized_in` (realized by actions/processes)

---

#### 9. **Constraint (Cs)** → `iao:0000030` (IAO:InformationContentEntity)
```turtle
proeth-core:Constraint a owl:Class ;
    rdfs:subClassOf iao:0000030 ;  # IAO:information content entity
    rdfs:label "Constraint"@en ;
    rdfs:comment "An information content entity expressing limitations or restrictions on professional actions or decisions."@en .
```
**BFO Category**: Generically Dependent Continuant (for rule constraints)

**Alternative for System Constraints**: `bfo:Quality` for physical/system limitations

**Key Properties**:
- Context-dependent based on constraint type
- Rule constraints → ICE
- System limitations → Quality with numeric properties

---

## OWL-Time Integration

### Location
OWL-Time properties are used in:
- **File**: `/home/chris/onto/proethica/app/services/temporal_dynamics/utils/rdf_converter.py`
- **Namespace**: `'time': 'http://www.w3.org/2006/time#'`

### Temporal Entities

#### Timeline → `time:TemporalEntity`
```python
{
    '@context': {
        'time': 'http://www.w3.org/2006/time#',
        'proeth': 'http://proethica.org/ontology/intermediate#',
        ...
    },
    '@id': 'http://proethica.org/cases/{case_id}#Timeline',
    '@type': 'time:TemporalEntity',
    'rdfs:label': 'Case {case_id} Timeline',
    'proeth:totalElements': 7,
    'proeth:actionCount': 5,
    'proeth:eventCount': 2,
    'proeth:hasTimepoints': [...]
}
```

#### Timepoints → `time:Instant`
Each timepoint in the timeline uses OWL-Time structure:
```python
{
    'proeth:timepoint': 'project start',
    'time:hasTime': '',  # ISO duration
    'proeth:isInterval': false,
    'proeth:elementCount': 2
}
```

### Allen's Interval Algebra

**Status**: ProEthica temporal extraction identifies Allen relations between actions/events, but they are not yet mapped to standard OWL-Time Allen relation properties.

#### Current Implementation
Allen relations are stored as relationship entities:
```json
{
  "@id": "http://proethica.org/cases/13#AllenRelation_...",
  "@type": "proeth:AllenRelation",
  "proeth:fromEntity": "Task Assignment to Wasser",
  "proeth:toEntity": "Task Refusal and Memorandum",
  "proeth:allenRelation": "precedes"
}
```

#### Recommended OWL-Time Mapping

| ProEthica Allen Relation | OWL-Time Property | URI |
|--------------------------|-------------------|-----|
| `precedes` | `time:before` | `http://www.w3.org/2006/time#before` |
| `meets` | `time:intervalMeets` | `http://www.w3.org/2006/time#intervalMeets` |
| `overlaps` | `time:intervalOverlaps` | `http://www.w3.org/2006/time#intervalOverlaps` |
| `during` | `time:intervalDuring` | `http://www.w3.org/2006/time#intervalDuring` |
| `starts` | `time:intervalStarts` | `http://www.w3.org/2006/time#intervalStarts` |
| `finishes` | `time:intervalFinishes` | `http://www.w3.org/2006/time#intervalFinishes` |
| `equals` | `time:intervalEquals` | `http://www.w3.org/2006/time#intervalEquals` |

**Implementation Location**: Update `rdf_converter.py` to add OWL-Time Allen properties

---

## BFO Disjointness Axioms

### Continuants vs Occurrents
**Critical BFO foundational distinction**:
```turtle
# Agent (material entity/continuant) is disjoint from processes (occurrents)
proeth-core:Agent owl:disjointWith proeth-core:Action, proeth-core:Event .

# Processes are disjoint from continuants
proeth-core:Action owl:disjointWith proeth-core:Agent, proeth-core:Resource, proeth-core:Role, proeth-core:Capability .
proeth-core:Event owl:disjointWith proeth-core:Agent, proeth-core:Resource, proeth-core:Role, proeth-core:Capability .

# BFO foundational disjointness preservation
[] a owl:AllDisjointClasses ;
   owl:members ( bfo:0000002 bfo:0000003 ) .  # continuant vs occurrent
```

### Why This Matters for Temporal Extraction
- **Actions and Events are Occurrents** (processes that unfold over time)
- **Agents, Roles, Capabilities are Continuants** (entities that persist through time)
- This distinction is fundamental to BFO and ensures ontological consistency

---

## Validation and Compliance

### BFO Compliance Rules
**Location**: `/home/chris/onto/OntServe/validation/bfo_compliance_rules.py`

The system includes 15 validation rules for BFO compliance:
- **BFO_003**: Action Process Inheritance - Actions must inherit from `bfo:Process`
- **BFO_004**: Event Process Inheritance - Events must inherit from `bfo:Process`
- **BFO_013**: Required Annotations - All entities need `rdfs:label` and `iao:definition`
- **BFO_014**: Genus-Differentia Definitions - Proper Aristotelian definitions

### BFO Alignment Targets
**Location**: `/home/chris/onto/OntServe/data/bfo_alignment_targets.json`

This JSON file provides the complete mapping specification with patterns for each ProEthica concept.

---

## Implementation Status

### ✅ Complete
1. **BFO Mappings**: All 9 core concepts mapped to BFO classes in `proethica-core.ttl`
2. **OWL-Time Integration**: Timeline entities use `time:TemporalEntity`
3. **RDF Conversion**: Actions and Events stored as RDF with proper BFO types
4. **Database Storage**: Temporal entities stored in `temporary_rdf_storage` with `extraction_type='temporal_dynamics_enhanced'`

### ⏳ Recommended Enhancements
1. **Allen Relations → OWL-Time Properties**: Map ProEthica Allen relations to standard OWL-Time interval relations
2. **Temporal Intervals**: Use `time:Interval` for action/event durations
3. **Instant vs Interval**: Distinguish between point-in-time (`time:Instant`) and duration-based (`time:Interval`) temporal markers

---

## Code Examples

### Action with BFO + OWL-Time
```json
{
  "@context": {
    "proeth": "http://proethica.org/ontology/intermediate#",
    "time": "http://www.w3.org/2006/time#",
    "bfo": "http://purl.obolibrary.org/obo/BFO_",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#"
  },
  "@id": "http://proethica.org/cases/13#Action_Task_Assignment",
  "@type": "proeth:Action",
  "rdf:type": "bfo:0000015",
  "rdfs:label": "Task Assignment to Wasser",
  "proeth:hasAgent": "Engineer Jaylani",
  "proeth:temporalMarker": "after Wasser hired",
  "proeth:hasMentalState": "deliberate",
  "proeth:intendedOutcome": "Complete project deliverable",
  "proeth:fulfillsObligation": ["Project_Management"],
  "proeth:requiresCapability": ["Project_Management"]
}
```

### Causal Chain (NESS Test)
```json
{
  "@context": {
    "proeth": "http://proethica.org/ontology/intermediate#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  },
  "@id": "http://proethica.org/cases/13#CausalChain_fc362f72",
  "@type": "proeth:CausalChain",
  "proeth:cause": "Traditional Irrigation Specification",
  "proeth:effect": "Ethical Conflict Emergence",
  "proeth:causalLanguage": "The specification created the foundational concern...",
  "proeth:necessaryFactors": [
    "Traditional irrigation system specification",
    "Environmental sustainability concerns"
  ],
  "proeth:responsibleAgent": "Landscape Architect",
  "proeth:responsibilityType": "indirect",
  "proeth:withinAgentControl": true
}
```

---

## References

### ProEthica Ontology Files
- **Core**: `/home/chris/onto/OntServe/ontologies/proethica-core.ttl`
- **Intermediate**: `/home/chris/onto/OntServe/ontologies/proethica-intermediate.ttl`
- **Cases**: `/home/chris/onto/OntServe/ontologies/proethica-cases.ttl`

### BFO and Foundation Ontologies
- **BFO 2.0**: `/home/chris/onto/OntServe/data/foundation/bfo-2.0.owl`
- **IAO 2020**: `/home/chris/onto/OntServe/data/foundation/iao-2020.owl`
- **RO 2015**: `/home/chris/onto/OntServe/data/foundation/ro-2015.owl`

### Validation and Import Tools
- **BFO Importer**: `/home/chris/onto/OntServe/importers/bfo_importer.py`
- **BFO Compliance Validator**: `/home/chris/onto/OntServe/validation/bfo_compliance_rules.py`
- **Alignment Targets**: `/home/chris/onto/OntServe/data/bfo_alignment_targets.json`

### Temporal Extraction Code
- **RDF Converter**: `/home/chris/onto/proethica/app/services/temporal_dynamics/utils/rdf_converter.py`
- **Review Route**: `/home/chris/onto/proethica/app/routes/scenario_pipeline/entity_review.py` (line 1191)
- **Review Template**: `/home/chris/onto/proethica/app/templates/entity_review/enhanced_temporal_review.html`

---

## Conclusion

**ProEthica's temporal dynamics extraction is fully BFO-compliant.** All mappings are properly defined, and the system correctly represents:
- **Actions and Events as BFO Processes (Occurrents)**
- **Roles, Capabilities, States as BFO Continuants**
- **Temporal structure using OWL-Time**

The only recommended enhancement is to map Allen relations to standard OWL-Time properties for broader interoperability.
