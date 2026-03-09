# ProEthica Ontology ObjectProperties Reference

**Generated**: 2026-01-12
**Source**: OntServe/ontologies/proethica-intermediate.ttl

This document lists all ObjectProperties defined in the ProEthica ontology. These should be used for extracted relations instead of ad-hoc property names.

---

## Normative Relations (9-Component Framework)

These connect the core extracted concept types:

| Property | Domain | Range | Description |
|----------|--------|-------|-------------|
| `:guidedByPrinciple` | Action | Principle | Action guided by ethical principle |
| `:fulfillsObligation` | Action | Obligation | Action fulfills professional obligation |
| `:violatesObligation` | Action | Obligation | Action violates professional obligation |
| `:constrainedBy` | Action | Constraint | Action limited by constraint |
| `:hasAgentRole` | Action | Role | Role of agent performing action |
| `:hasObligation` | Role | Obligation | Role carries professional obligation |
| `:adheresToPrinciple` | Role | Principle | Role governed by ethical principle |
| `:hasRole` | IndependentContinuant | Role | Entity bears a role |
| `:hasState` | Process | State | Process affected by state |
| `:hasResource` | Process | Resource | Process uses resource |
| `:performsAction` | MaterialEntity | Action | Agent performs action |
| `:hasCapability` | MaterialEntity | Capability | Entity has capability |

## Role-to-Role Instance Relations

Model professional relationships between role instances in cases:

| Property | Domain | Range | Inverse | Description |
|----------|--------|-------|---------|-------------|
| `:retainedBy` | Role | Role | `:retains` | Professional retained by client |
| `:retains` | Role | Role | `:retainedBy` | Client retains professional |
| `:employedBy` | Role | Role | `:employs` | Professional employed by organization |
| `:employs` | Role | Role | `:employedBy` | Organization employs professional |
| `:supervises` | Role | Role | `:supervisedBy` | Role supervises another |
| `:supervisedBy` | Role | Role | `:supervises` | Role supervised by another |
| `:mentors` | Role | Role | `:mentoredBy` | Role mentors another |
| `:mentoredBy` | Role | Role | `:mentors` | Role mentored by another |
| `:reportsTo` | Role | Role | `:receivesReportFrom` | Role reports to another |
| `:receivesReportFrom` | Role | Role | `:reportsTo` | Role receives reports from another |
| `:collaboratesWith` | Role | Role | (symmetric) | Roles collaborate as peers |

## Provision Relations

Connect guidelines to ethical concepts:

| Property | Domain | Range | Description |
|----------|--------|-------|-------------|
| `:establishes` | Resource | Principle/Obligation/Constraint | Provision establishes ethical concept |
| `:establishedBy` | Principle/Obligation/Constraint | Resource | Inverse of establishes |
| `:governedByCode` | Role | EthicalCode | Role governed by code of ethics |

## Case Analysis Relations (Step 4)

| Property | Domain | Range | Description |
|----------|--------|-------|-------------|
| `:hasQuestion` | Case | EthicalQuestion | Case poses ethical question |
| `:hasConclusion` | Case | BoardConclusion | Case has board conclusion |
| `:hasDecisionPoint` | Case | DecisionPoint | Case contains decision point |
| `:answersQuestion` | BoardConclusion | EthicalQuestion | Conclusion answers question |

## Decision Point Relations

| Property | Domain | Range | Description |
|----------|--------|-------|-------------|
| `:hasOption` | DecisionPoint | DecisionOption | Decision point has option |
| `:involvesRole` | DecisionPoint | Role | Decision point involves role |
| `:appliesProvision` | DecisionPoint | EthicalCode | Decision point applies provision |

## Argument Relations

| Property | Domain | Range | Description |
|----------|--------|-------|-------------|
| `:hasArgument` | DecisionOption | EthicalArgument | Option has argument |
| `:argumentFor` | EthicalArgument | DecisionOption | PRO argument for option |
| `:argumentAgainst` | EthicalArgument | DecisionOption | CON argument against option |
| `:citesProvision` | EthicalArgument | EthicalCode | Argument cites code provision |

## Deprecated

| Property | Replacement | Reason |
|----------|-------------|--------|
| `:hasCondition` | `:hasState` | Terminology alignment |

---

## JSON Key to ObjectProperty Mapping

For migrating embedded JSON relations to proper triples:

### CausalNormativeLink Relations

| JSON Key | ObjectProperty |
|----------|----------------|
| `fulfills_obligations` | `:fulfillsObligation` |
| `violates_obligations` | `:violatesObligation` |
| `guided_by_principles` | `:guidedByPrinciple` |
| `constrained_by` | `:constrainedBy` |
| `agent_role` | `:hasAgentRole` |

### Role Instance Relations

| JSON type value | ObjectProperty |
|-----------------|----------------|
| `retained_by` | `:retainedBy` |
| `retains` | `:retains` |
| `employed_by` | `:employedBy` |
| `employs` | `:employs` |
| `supervises` | `:supervises` |
| `supervised_by` | `:supervisedBy` |
| `mentors` | `:mentors` |
| `mentored_by` | `:mentoredBy` |
| `reports_to` | `:reportsTo` |
| `collaborates_with` | `:collaboratesWith` |

---

## Usage in Extraction Prompts

When updating extraction prompts, require the LLM to use ONLY these property names for relationships:

```
## Allowed Relationship Properties

For Action relationships:
- guidedByPrinciple: action guided by ethical principle
- fulfillsObligation: action fulfills professional obligation
- violatesObligation: action violates professional obligation
- constrainedBy: action limited by constraint
- hasAgentRole: role performing the action

For Role relationships:
- hasObligation: role carries professional obligation
- adheresToPrinciple: role governed by ethical principle
- retainedBy: professional retained by client
- employedBy: professional employed by organization
- supervises: role supervises another role
- supervisedBy: role supervised by another
- mentors: role mentors another
- mentoredBy: role mentored by another
- reportsTo: role reports to another
- collaboratesWith: roles work together as peers
```

---

**Last Updated**: 2026-01-12
