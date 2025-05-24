# Ontology Enhancement Implementation Plan

This document outlines the specific changes to be made to both the engineering-ethics.ttl and proethica-intermediate.ttl ontologies.

## 1. Classes to Move from engineering-ethics.ttl to proethica-intermediate.ttl

The following classes should be moved from engineering-ethics.ttl to proethica-intermediate.ttl as they represent domain-general concepts:

| Class | Reason | Required Updates After Move |
|-------|--------|----------------------------|
| :Principle | General ethical concept applicable across domains | Update references in engineering-ethics.ttl |
| :EthicalDilemma | Generic concept for ethical dilemmas in any field | Update subclass references in engineering-ethics.ttl |
| :EngineeringAction | Should be renamed to :Action to be domain-general | Ensure engineering-specific actions remain in engineering-ethics.ttl |
| :EngineeringEvent | Should be renamed to :Event to be domain-general | Ensure engineering-specific events remain in engineering-ethics.ttl |
| :EngineeringResource | Should be renamed to :Resource to be domain-general | Ensure engineering-specific resources remain in engineering-ethics.ttl |
| :EngineeringCapability | Should be renamed to :Capability to be domain-general | Ensure engineering-specific capabilities remain in engineering-ethics.ttl |

## 2. New Semantic Matching Properties

The following properties should be added to the ontologies to facilitate semantic matching between classes and document sections:

```turtle
# For proethica-intermediate.ttl
:hasMatchingTerm rdf:type owl:DatatypeProperty ;
    rdfs:domain owl:Class ;
    rdfs:range xsd:string ;
    rdfs:label "has matching term"@en ;
    rdfs:comment "Key term that can be used to match this concept in text"@en .

:hasMatchingPattern rdf:type owl:DatatypeProperty ;
    rdfs:domain owl:Class ;
    rdfs:range xsd:string ;
    rdfs:label "has matching pattern"@en ;
    rdfs:comment "Regex pattern that can be used to identify this concept in text"@en .

:hasRelevanceScore rdf:type owl:DatatypeProperty ;
    rdfs:domain owl:Class ;
    rdfs:range xsd:float ;
    rdfs:label "has relevance score"@en ;
    rdfs:comment "A score from 0.0 to 1.0 indicating the concept's relevance for section matching"@en .

:hasRelevanceToSectionType rdf:type owl:ObjectProperty ;
    rdfs:domain owl:Class ;
    rdfs:range :DocumentSection ;
    rdfs:label "has relevance to section type"@en ;
    rdfs:comment "Indicates which document section types this concept is most relevant to"@en .

:hasCategory rdf:type owl:DatatypeProperty ;
    rdfs:domain owl:Class ;
    rdfs:range xsd:string ;
    rdfs:label "has category"@en ;
    rdfs:comment "The category this concept belongs to (e.g., 'core ethical principle', 'professional obligation')"@en .

:hasTextReference rdf:type owl:DatatypeProperty ;
    rdfs:domain owl:Class ;
    rdfs:range xsd:string ;
    rdfs:label "has text reference"@en ;
    rdfs:comment "A textual reference or example of this concept, often from codes or standards"@en .
```

## 3. New Classes from Guideline Concepts

The following classes should be added to engineering-ethics.ttl based on guideline concepts:

### 3.1 Professional Integrity Principle

```turtle
:ProfessionalIntegrityPrinciple a owl:Class ;
    rdf:type proeth:EntityType ;
    rdf:type proeth:ConditionType ;
    rdfs:label "Professional Integrity Principle"@en ;
    rdfs:comment "Engineers must maintain honesty, ethical conduct, and avoid deceptive practices in all professional activities"@en ;
    rdfs:subClassOf :Principle ;
    :hasCategory "core ethical principle" ;
    :hasMatchingTerm "professional integrity" ;
    :hasMatchingTerm "honesty" ;
    :hasMatchingTerm "ethical conduct" ;
    :hasTextReference "Engineers shall be guided by honesty and integrity" ;
    :hasTextReference "Avoid deceptive acts" ;
    :hasTextReference "Do not misrepresent qualifications or responsibilities" ;
    :hasRelevanceScore "0.9"^^xsd:float ;
    :hasRelevanceToSectionType proeth:DiscussionSection .
```

### 3.2 Fiduciary Duty Principle

```turtle
:FiduciaryDutyPrinciple a owl:Class ;
    rdf:type proeth:EntityType ;
    rdf:type proeth:ConditionType ;
    rdfs:label "Fiduciary Duty Principle"@en ;
    rdfs:comment "Engineers must act as faithful agents or trustees for their employers or clients"@en ;
    rdfs:subClassOf :Principle ;
    :hasCategory "professional relationship" ;
    :hasMatchingTerm "fiduciary duty" ;
    :hasMatchingTerm "faithful agent" ;
    :hasMatchingTerm "trustee" ;
    :hasTextReference "Act for each employer or client as faithful agents or trustees" ;
    :hasTextReference "Disclose actual or potential conflicts of interest" ;
    :hasRelevanceScore "0.8"^^xsd:float ;
    :hasRelevanceToSectionType proeth:DiscussionSection .
```

### 3.3 Professional Accountability Principle

```turtle
:ProfessionalAccountabilityPrinciple a owl:Class ;
    rdf:type proeth:EntityType ;
    rdf:type proeth:ConditionType ;
    rdfs:label "Professional Accountability Principle"@en ;
    rdfs:comment "Engineers must take responsibility for their professional actions and decisions"@en ;
    rdfs:subClassOf :Principle ;
    :hasCategory "professional responsibility" ;
    :hasMatchingTerm "professional accountability" ;
    :hasMatchingTerm "responsibility" ;
    :hasMatchingTerm "professional actions" ;
    :hasRelevanceScore "0.85"^^xsd:float ;
    :hasRelevanceToSectionType proeth:DiscussionSection .
```

### 3.4 Public Interest Service Principle

```turtle
:PublicInterestServicePrinciple a owl:Class ;
    rdf:type proeth:EntityType ;
    rdf:type proeth:ConditionType ;
    rdfs:label "Public Interest Service Principle"@en ;
    rdfs:comment "Engineers must serve the broader public interest through their professional work"@en ;
    rdfs:subClassOf :PublicSafetyPrinciple ;
    :hasCategory "core ethical principle" ;
    :hasMatchingTerm "public interest" ;
    :hasMatchingTerm "service" ;
    :hasMatchingTerm "societal benefit" ;
    :hasRelevanceScore "0.85"^^xsd:float ;
    :hasRelevanceToSectionType proeth:DiscussionSection .
```

### 3.5 Intellectual Property Respect Principle

```turtle
:IntellectualPropertyRespectPrinciple a owl:Class ;
    rdf:type proeth:EntityType ;
    rdf:type proeth:ConditionType ;
    rdfs:label "Intellectual Property Respect Principle"@en ;
    rdfs:comment "Engineers must properly credit others' work and respect proprietary rights"@en ;
    rdfs:subClassOf :Principle ;
    :hasCategory "professional ethics" ;
    :hasMatchingTerm "intellectual property" ;
    :hasMatchingTerm "proprietary rights" ;
    :hasMatchingTerm "credit" ;
    :hasMatchingTerm "attribution" ;
    :hasRelevanceScore "0.75"^^xsd:float ;
    :hasRelevanceToSectionType proeth:DiscussionSection .
```

## 4. Circular Reference Fixes

The following classes have circular references that need to be resolved:

| Class | Current Reference | Updated Reference |
|-------|------------------|-------------------|
| :ApprovalAction | rdfs:subClassOf :ApprovalAction, :EngineeringAction | rdfs:subClassOf :EngineeringAction |
| :DeliveryEvent | rdfs:subClassOf :DeliveryEvent, :EngineeringEvent | rdfs:subClassOf :EngineeringEvent |
| :DiscoveryEvent | rdfs:subClassOf :DiscoveryEvent, :EngineeringEvent | rdfs:subClassOf :EngineeringEvent |
| :EngineeringAction | rdfs:subClassOf :EngineeringAction, proeth:ActionType | rdfs:subClassOf proeth:ActionType |
| :EngineeringEvent | rdfs:subClassOf :EngineeringEvent, proeth:EventType | rdfs:subClassOf proeth:EventType |
| :MeetingEvent | rdfs:subClassOf :EngineeringEvent, :MeetingEvent | rdfs:subClassOf :EngineeringEvent |
| :ReviewAction | rdfs:subClassOf :EngineeringAction, :ReviewAction | rdfs:subClassOf :EngineeringAction |
| :SafetyAction | rdfs:subClassOf :EngineeringAction, :SafetyAction | rdfs:subClassOf :EngineeringAction |
| :DisclosureEvent | rdfs:subClassOf :DisclosureEvent, :EngineeringEvent | rdfs:subClassOf :EngineeringEvent |
| :ReportAction | rdfs:subClassOf :EngineeringAction, :ReportAction | rdfs:subClassOf :EngineeringAction |
| :DesignAction | rdfs:subClassOf :DesignAction, :EngineeringAction | rdfs:subClassOf :EngineeringAction |
| :DecisionAction | rdfs:subClassOf :DecisionAction, :EngineeringAction | rdfs:subClassOf :EngineeringAction |

## 5. Description Standardization

All class descriptions (rdfs:comment) should follow this standardized format:

1. **No leading articles**: Remove "A" or "The" at the beginning
2. **Active voice**: Use active rather than passive voice
3. **Concise phrasing**: Keep descriptions under 15 words when possible
4. **No placeholder references**: Remove "rdf:type" and similar references
5. **Consistent language**: Use consistent terminology across related concepts

Example transformations:

| Current Description | Standardized Description |
|--------------------|--------------------------|
| "A deficiency in rdf:type building system that may pose safety hazards" | "Deficiency in building system that may pose safety hazards" |
| "The role of an engineer who designs and develops electrical systems" | "Role of an engineer who designs and develops electrical systems" |
| "The principle that engineers shall perform services only in areas of their competence" | "Engineers shall perform services only in areas of their competence" |

## 6. Implementation Sequence

To minimize disruption, implement changes in this order:

1. Add new semantic matching properties to proethica-intermediate.ttl
2. Fix circular references in engineering-ethics.ttl
3. Move domain-general classes to proethica-intermediate.ttl
4. Update references to moved classes in engineering-ethics.ttl
5. Add new classes from guideline concepts to engineering-ethics.ttl
6. Standardize descriptions across both ontologies
7. Add semantic matching properties to all classes
8. Validate the updated ontologies

## 7. Validation Tests

After implementation, run these validation tests:

1. **Syntax validation**: Ensure Turtle syntax is valid
2. **Circular reference check**: Verify no classes reference themselves
3. **Property completeness**: Ensure all classes have required properties
4. **Reference integrity**: Check all references point to existing classes
5. **Semantic matching test**: Test section matching using the new properties
