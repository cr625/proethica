# Engineering Ethics Ontology Audit

This document provides an audit of the existing engineering-ethics.ttl ontology, identifying patterns, issues, and opportunities for improvement.

## Class Organization and Patterns

The engineering-ethics.ttl file contains approximately 100 classes organized into several conceptual areas:

1. **Roles**: Various engineering roles and stakeholders (e.g., `ElectricalEngineerRole`, `ClientRole`)
2. **Principles**: Ethical principles specific to engineering (e.g., `PublicSafetyPrinciple`, `ConfidentialityPrinciple`)
3. **Conditions**: States or contexts relevant to ethical decisions (e.g., `BuildingSystemDeficiency`, `ConflictOfInterestCondition`)
4. **Actions**: Activities performed by engineers (e.g., `DesignRevisionAction`, `HazardReportingAction`)
5. **Events**: Occurrences in engineering practice (e.g., `SafetyHazardDiscovery`, `ConfidentialReportDelivery`)
6. **Resources**: Materials and documents used in engineering (e.g., `DesignDrawings`, `InspectionReport`)
7. **Capabilities**: Skills or competencies of engineers (e.g., `ElectricalSystemsDesignCapability`)

## Audit Findings

### Naming Patterns

1. **Inconsistent class naming**:
   - Most classes use CamelCase format (e.g., `PublicSafetyPrinciple`)
   - Some classes have redundant terms in names (e.g., both `EngineeringDeficiency` and `EngineeringEthicalDilemma` vs. just `Deficiency` and `EthicalDilemma`)
   - Some lack proper suffixes indicating their type (Principle, Role, etc.)

2. **Label consistency**:
   - Most classes have rdfs:label matching their class name with spaces
   - Some lack language tags (e.g., "@en")

3. **Description consistency**:
   - Some descriptions include "A" or "The" prefixes while others don't
   - Varying levels of detail in descriptions
   - Some descriptions reference types (e.g., "the role of rdf:type building official") that seem like errors

### Inheritance Structure

1. **Intermediate ontology integration**:
   - Many classes properly inherit from proethica-intermediate classes
   - Some inherit directly from BFO when they should use intermediate classes

2. **Cyclical inheritance**:
   - Several classes reference themselves in their rdfs:subClassOf property (e.g., :ApprovalAction, :DeliveryEvent)
   - This creates circular dependencies that should be resolved

3. **Multiple inheritance**:
   - Some classes have multiple parent classes (e.g., `ConfidentialReportDelivery` inherits from both `:DeliveryEvent` and `:DisclosureEvent`)
   - This is not necessarily an issue but should be intentional and consistent

### Property Usage

1. **Capability associations**:
   - Some Role classes properly use `proeth:hasCapability` to define capabilities
   - Others lack these associations entirely

2. **Missing semantic properties**:
   - Classes lack properties for semantic matching with document sections
   - No `hasMatchingTerm` or similar property to facilitate search

3. **Description quality**:
   - Some descriptions are too brief or generic
   - Others use placeholder text that needs updating (e.g., references to "rdf:type")

## Classes Matching Guideline Concepts

| Guideline Concept | Existing Class | Match Quality | Issues |
|-------------------|----------------|---------------|--------|
| public-safety-primacy | :PublicSafetyPrinciple, :NSPEPublicSafetyPrinciple | Good | Description could be enhanced |
| professional-competence | :CompetencyPrinciple, :NSPECompetencyPrinciple | Partial | Names don't exactly match, description differences |
| truthfulness | :HonestyPrinciple | Partial | Different terminology but similar concept |
| confidentiality | :ConfidentialityPrinciple, :NSPEConfidentialityPrinciple | Good | Description could be enhanced |
| conflict-of-interest | :ConflictOfInterestCondition, :ConflictOfInterestDilemma | Partial | Different class types (Condition vs. Dilemma) |
| professional-integrity | None found | N/A | New concept needed |
| fiduciary-duty | None found | N/A | New concept needed |
| professional-accountability | None found | N/A | New concept needed |
| public-interest-service | None found | N/A | New concept needed |
| intellectual-property-respect | None found | N/A | New concept needed |

## Domain-General vs. Domain-Specific Assessment

Some classes in engineering-ethics.ttl appear to be domain-general and might be better placed in the proethica-intermediate ontology:

1. **Domain-general concepts currently in engineering-ethics.ttl**:
   - `EthicalDilemma` - generic concept applicable to all domains
   - `Principle` - generic concept for all ethical principles
   - Several basic action and event types

2. **Domain-specific concepts properly in engineering-ethics.ttl**:
   - Engineering roles (e.g., `StructuralEngineerRole`)
   - Engineering-specific principles (e.g., `NSPEPublicSafetyPrinciple`)
   - Engineering resources and events (e.g., `DesignDrawings`, `StructuralInspectionEvent`)

## Recommendations for Improvement

### Structural Improvements

1. **Resolve circular references**:
   - Fix classes that reference themselves in rdfs:subClassOf
   - Ensure proper inheritance hierarchy

2. **Standardize naming conventions**:
   - Use CamelCase for all class names
   - Add appropriate type suffixes (Role, Principle, etc.) consistently
   - Remove redundant prefixes where possible

3. **Improve descriptions**:
   - Standardize description format (with or without initial articles)
   - Fix placeholder references (e.g., "rdf:type")
   - Add more detailed descriptions where needed

### Content Enhancements

1. **Add missing classes from guideline concepts**:
   - ProfessionalIntegrityPrinciple
   - FiduciaryDutyPrinciple
   - ProfessionalAccountabilityPrinciple
   - PublicInterestServicePrinciple
   - IntellectualPropertyRespectPrinciple

2. **Move domain-general classes to proethica-intermediate.ttl**:
   - Review and relocate appropriate classes
   - Ensure proper references after moving

3. **Add semantic matching properties**:
   - Add hasMatchingTerm property with key terms
   - Add hasCategory property as found in guideline concepts
   - Add hasTextReference for relevant text fragments

### Next Steps

1. Create a list of classes to be moved to proethica-intermediate.ttl
2. Develop a standardized format for class descriptions
3. Create templates for new classes needed from guideline concepts
4. Resolve circular references in the current ontology
5. Design semantic matching properties to be added to all classes
