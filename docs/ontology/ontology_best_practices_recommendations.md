# ProEthica Ontology Best Practices Recommendations

## Overview

This document provides actionable recommendations for improving the ProEthica ontologies based on the analysis against "Principles of Best Practice II: Terms, Definitions, and Classification" by Arp et al.

**Date**: December 2024  
**Scope**: `proethica-intermediate.ttl` and `engineering-ethics.ttl`

## Priority Recommendations

### 1. Adopt Aristotelian Definition Format

**Current State**: Definitions are descriptive comments with mixed examples.

**Recommendation**: Implement formal genus + differentia definitions.

**Implementation**:

```turtle
# BEFORE:
:Role rdfs:comment "A socially recognized status that carries a set of responsibilities, expectations, and norms established by a professional or social community. Examples include Engineer, Manager, Client, Regulator."@en .

# AFTER:
:Role a owl:Class ;
    rdfs:label "role"@en ;
    skos:definition "role =def. a realizable entity (BFO:0000017) that is socially recognized and bears responsibilities established by a professional or social community"@en ;
    rdfs:comment "A role in the context of professional ethics"@en ;
    skos:example "Engineer"@en, "Manager"@en, "Client"@en, "Regulator"@en ;
    rdfs:subClassOf bfo:BFO_0000023 .
```

### 2. Add Numeric Identifiers

**Current State**: Only URI identifiers exist.

**Recommendation**: Add alphanumeric identifiers for version control and cross-referencing.

**Implementation**:

```turtle
# Add to ontology header
@prefix proeth: <http://proethica.org/ontology/intermediate#> .
@prefix dct: <http://purl.org/dc/terms/> .

# Add to each class
:Role a owl:Class ;
    dct:identifier "PROETH:0000001" ;
    # ... other properties
```

**Suggested ID Scheme**:
- Intermediate ontology: `PROETH:0000001` - `PROETH:0000999`
- Engineering ethics: `PROENG:0001000` - `PROENG:0001999`
- Future domains: Reserved ranges

### 3. Separate Examples from Definitions

**Current State**: Examples embedded in definition text.

**Recommendation**: Use separate annotation properties.

**Implementation**:

```turtle
# Add SKOS vocabulary for examples
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

# Apply to classes
:State a owl:Class ;
    skos:definition "state =def. a quality (BFO:0000019) that provides context for ethical decision-making"@en ;
    skos:example "Budget Constraint"@en, 
                 "Safety Hazard"@en, 
                 "Time Pressure"@en, 
                 "Regulatory Compliance"@en ;
```

### 4. Implement Lowercase Labels

**Current State**: Title case labels ("Role"@en).

**Recommendation**: Use lowercase for common nouns per Principle 6.

**Implementation**:

```turtle
# Change all labels
:Role rdfs:label "role"@en ;  # not "Role"@en
:Principle rdfs:label "principle"@en ;  # not "Principle"@en
```

## Implementation Plan

### Phase 1: Definition Refactoring (Priority: HIGH)

1. **Create new annotation properties**:
   ```turtle
   proeth:aristotelianDefinition a owl:AnnotationProperty ;
       rdfs:label "aristotelian definition"@en ;
       rdfs:comment "Formal definition following genus + differentia pattern"@en .
   ```

2. **Update all 8 core GuidelineConceptTypes**:
   - Role → "a realizable entity that..."
   - Principle → "a generically dependent continuant that..."
   - Obligation → "a realizable entity that..."
   - State → "a quality that..."
   - Resource → "a material entity that..."
   - Action → "a process that..."
   - Event → "a process that..."
   - Capability → "a disposition that..."

### Phase 2: Identifier System (Priority: MEDIUM)

1. **Define identifier property**:
   ```turtle
   proeth:identifier a owl:AnnotationProperty ;
       rdfs:label "identifier"@en ;
       rdfs:comment "Unique alphanumeric identifier for version control"@en .
   ```

2. **Assign identifiers systematically**:
   - Start with core concepts
   - Document ID assignment rules
   - Create ID registry

### Phase 3: Enhanced Axiomatization (Priority: LOW)

1. **Add disjointness axioms**:
   ```turtle
   # GuidelineConceptTypes are mutually disjoint
   [ a owl:AllDisjointClasses ;
     owl:members ( :Role :Principle :Obligation :State 
                   :Resource :Action :Event :Capability ) ] .
   ```

2. **Add domain/range restrictions**:
   ```turtle
   :hasRole rdfs:domain bfo:BFO_0000040 ;  # material entity
            rdfs:range :Role .
   ```

## Validation Checklist

- [ ] All non-root terms have Aristotelian definitions
- [ ] Examples separated into skos:example annotations  
- [ ] Numeric identifiers assigned to all classes
- [ ] Labels converted to lowercase
- [ ] No circular definitions
- [ ] All definitions use simpler terms than definiendum
- [ ] Single inheritance maintained in asserted hierarchy
- [ ] All classes connected to BFO root

## Benefits of Implementation

1. **Improved Interoperability**: Standard definition format aids cross-ontology mapping
2. **Better Maintenance**: Numeric IDs enable stable references across versions
3. **Enhanced Clarity**: Separated examples reduce definition complexity
4. **Formal Reasoning**: Aristotelian format supports automated reasoning
5. **Standards Compliance**: Aligns with OBO Foundry and similar initiatives

## Tools and Resources

- **Protégé**: For editing and validation
- **ROBOT**: For automated quality checks
- **OWLTools**: For ID assignment and management
- **Jenkins/CI**: For continuous validation

## Next Steps

1. Review recommendations with team
2. Create test branch with Phase 1 changes
3. Validate with reasoner (HermiT/Pellet)
4. Update documentation
5. Plan migration strategy for existing data

## References

- Arp, R., Smith, B., & Spear, A. D. (2015). Building Ontologies with Basic Formal Ontology. MIT Press.
- OBO Foundry Principles: http://www.obofoundry.org/principles/
- BFO Documentation: https://basic-formal-ontology.org/