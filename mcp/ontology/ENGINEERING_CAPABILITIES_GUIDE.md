# Engineering Capabilities in ProEthica Ontology

This guide explains the engineering capabilities added to the Engineering Ethics ontology and how they relate to engineering roles.

## Overview

Engineering roles in ethical scenarios often involve specialized capabilities that influence how engineers approach and resolve ethical dilemmas. By explicitly modeling these capabilities in our ontology, we can better represent:

1. The specific competencies different engineering roles possess
2. The relationship between capabilities and ethical responsibilities
3. How capabilities influence decision-making in ethical scenarios
4. The boundaries of professional competence in engineering ethics

## Capability Structure

Each capability is represented as a class in the ontology, with the following hierarchy:

```
:EngineeringCapability
  ├─ :StructuralAnalysisCapability
  ├─ :StructuralDesignCapability
  ├─ :ElectricalSystemsDesignCapability
  ├─ :MechanicalSystemsDesignCapability
  ├─ :EngineeringConsultationCapability
  ├─ :ProjectManagementCapability
  ├─ :RegulatoryComplianceCapability
  ├─ :TechnicalReportingCapability
  └─ :SafetyAssessmentCapability
```

## Capabilities and Roles

Each engineering role has specific capabilities associated with it through the `proeth:hasCapability` property. For example:

```ttl
:StructuralEngineerRole rdf:type owl:Class ;
    rdf:type proeth:EntityType ;
    rdf:type proeth:Role ;
    rdfs:subClassOf :EngineeringRole ;
    rdfs:label "Structural Engineer Role"@en ;
    rdfs:comment "The role of an engineer who analyzes and designs structural systems"@en ;
    proeth:hasCapability :StructuralAnalysisCapability ;
    proeth:hasCapability :StructuralDesignCapability ;
    proeth:hasCapability :TechnicalReportingCapability ;
    proeth:hasCapability :SafetyAssessmentCapability ;
    proeth:hasCapability :RegulatoryComplianceCapability .
```

### Role-Capability Mapping

| Role | Capabilities |
|------|-------------|
| Structural Engineer | Structural Analysis, Structural Design, Technical Reporting, Safety Assessment, Regulatory Compliance |
| Electrical Engineer | Electrical Systems Design, Technical Reporting, Safety Assessment, Regulatory Compliance |
| Mechanical Engineer | Mechanical Systems Design, Technical Reporting, Safety Assessment, Regulatory Compliance |
| Consulting Engineer | Engineering Consultation, Technical Reporting, Safety Assessment, Regulatory Compliance |
| Project Engineer | Project Management, Technical Reporting, Safety Assessment, Regulatory Compliance |
| Regulatory Official | Regulatory Compliance |

## Ethical Implications

The capabilities framework has several important ethical implications:

1. **Competence Boundaries**: The capabilities associated with a role define the boundaries of professional competence, which relates directly to the Competency Principle in engineering ethics.

2. **Responsibility Alignment**: Capabilities help align responsibilities with competencies, ensuring that engineers are not ethically obligated beyond their capabilities.

3. **Dilemma Resolution**: In ethical dilemmas like the "Competence vs Client Wishes Dilemma," understanding capabilities helps clarify the ethical decision process.

4. **Whistleblowing Context**: Capability boundaries provide context for whistleblowing decisions when engineers identify issues outside their direct competence.

## Implementation in Scenarios

When creating ethical scenarios in ProEthica, you can use capabilities to:

1. Define the scope of a role's competence in addressing ethical issues
2. Create realistic constraints on what actions a character with a particular role can take
3. Model ethical dilemmas that arise from capability limitations
4. Represent conflicts between different capabilities (e.g., regulatory compliance vs. technical reporting)

## Example Scenario: Structural Safety Concern

In a scenario where a structural engineer discovers a safety concern:

1. The engineer's `StructuralAnalysisCapability` enables them to identify the problem
2. Their `SafetyAssessmentCapability` allows them to evaluate the risk
3. Their `TechnicalReportingCapability` gives them competence to document the issue
4. Their `RegulatoryComplianceCapability` provides knowledge of code violations

This comprehensive set of capabilities establishes both the engineer's ability to address the issue and their ethical responsibility to do so.

## Extending Capabilities

To extend capabilities for new domains:

1. Define new capability classes as subclasses of `EngineeringCapability`
2. Associate these capabilities with appropriate roles using `proeth:hasCapability`
3. Ensure the capabilities align with the ethical principles and dilemmas in your domain
4. Document how each capability influences ethical decision-making

## Best Practices

1. Assign capabilities based on realistic professional qualifications
2. Ensure all engineering roles have at least one capability
3. Use capabilities to clarify ethical responsibilities in scenarios
4. Consider capability limitations when designing ethical dilemmas
5. Reference capabilities when discussing competence-related ethical principles
