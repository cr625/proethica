# ProEthica Ontology ObjectProperties Reference

**Source**: OntServe/ontologies/proethica-core.ttl (v2.10.23), proethica-intermediate.ttl, proethica-cases.ttl (v3.8.0)

This document lists the ObjectProperties defined in the ProEthica ontologies.
Extracted relations use these properties rather than ad-hoc names; the
authoritative definition of each property, with its full annotation record, is
its entity page on [OntServe](https://ontserve.ontorealm.net?origin=proethica&filter=proethica).

---

## Normative Relations (Nine-Component Framework)

These connect the core extracted concept types:

| Property | Domain | Range | Description |
|----------|--------|-------|-------------|
| `proeth-core:guidedByPrinciple` | Action | Principle | Action guided by ethical principle |
| `proeth-core:fulfillsObligation` | Action | Obligation | Action fulfills professional obligation |
| `proeth-core:violatesObligation` | Action | Obligation | Action violates professional obligation |
| `proeth-core:raisesObligation` | Action | Obligation | Action puts an obligation in force, to be resolved by a later action |
| `proeth-core:derivedFromPrinciple` | Obligation | Principle | Obligation specifies a principle (the R-to-P-to-O chain) |
| `proeth-core:hasObligation` | Role | Obligation | Role carries an obligation in the case |
| `proeth-core:adheresToPrinciple` | Role | Principle | Role governed by ethical principle |
| `proeth-core:requiresCapability` | Obligation | Capability | Obligation presupposes the capacity to discharge it |
| `proeth-core:hasRole` / `isRoleOf` | Agent / Role | Role / Agent | Entity bears a role (inverse pair) |
| `proeth-core:performsAction` / `isPerformedBy` | Agent / Action | Action / Agent | Agent performs action (inverse pair) |
| `proeth-core:hasCapability` | Agent | Capability | Agent possesses a competence |

The three pairwise `owl:propertyDisjointWith` axioms on `fulfillsObligation`,
`violatesObligation`, and `raisesObligation` make the per-action engagement
partition reasoner-visible: one action engages one obligation in exactly one
of the three ways.

## Actor Relations (Role to Role)

Professional relationships between role facets. The bearer Agent on each side
is reached via `hasRole`. Asserted edges drive the reasoner-inferred
relational archetypes (a `hasClient` edge classifies the provider side into
`ProviderClientRole`, and so on).

| Property | Characteristic | Description |
|----------|----------------|-------------|
| `proeth-core:hasClient` | | Provider-side role to client-side role |
| `proeth-core:professionalPeerOf` | Symmetric | Collegial relation between practitioners |
| `proeth-core:employedBy` | | Employment relation from the employee side |
| `proeth-core:reviewsWorkOf` / `workReviewedBy` | Inverse pair | Peer-review relation |
| `proeth:owesDutyToward` | Domain ProfessionalRole | The Canon 1 duty relation toward the public |
| `proeth-core:relatedTo` | | Deliberately domain-less fallback for unvetted relationships |

Participant-side facts attach through the actor-edge family
(`affects`, `obligatedParty`, `constrainedEntity`, `possessedBy`, `invokedBy`,
`citedByAgent`, `availableTo`), which resolve extracted who-fields to Agent
endpoints at commit; see the property pages on OntServe for domains and
ranges.

## Fluent and Temporal Relations

The Event Calculus layer connecting happenings (Actions and Events) to States:

| Property | Domain | Range | Description |
|----------|--------|-------|-------------|
| `proeth-core:initiates` | Action or Event | State | Happening brings a fluent into force |
| `proeth-core:terminates` | Action or Event | State | Happening ends a fluent |
| `proeth-core:activatedByEvent` | State | Event | Evidence channel for the event that activated the state |
| `proeth-core:terminatedByEvent` | State | Event | Evidence channel for the event that ended the state |
| `proeth-core:activatesObligation` | State | Obligation | State puts an obligation in force |
| `proeth-core:activatesConstraint` | State | Constraint | State puts a constraint in force |
| `proeth:causedByAction` | Event | Action | Cause-in-fact per the NESS test |
| `proeth:cause` / `effect` / `responsibleAgent` | CausalChain | | The NESS responsibility analysis of a causal linkage |
| `proeth:analyzesAction` | CausalNormativeLink | Action | Grounds a reasoning node in the case graph |
| `proeth:fromEntity` / `toEntity` | TemporalRelation | Action or Event | Endpoints of a reified Allen interval relation |

## Provision Relations

Connect codes and their provisions to ethical concepts:

| Property | Domain | Range | Description |
|----------|--------|-------|-------------|
| `proeth-core:establishes` / `establishedBy` | CodeProvision | Principle/Obligation/Constraint | Provision establishes the concept (inverse pair) |
| `proeth-core:containsProvision` | Resource | CodeProvision | Code document contains provision |
| `proeth-core:partOfGuideline` | CodeProvision | Guideline | Provision belongs to a guideline document |
| `proeth-core:citesProvision` | analysis record | CodeProvision | Analysis record cites a provision as authority |
| `proeth:governedByCode` | ProfessionalRole | EthicalCode | Professional role governed by a code of ethics |

## Analysis-Record Relations (Step 4, proethica-cases)

The Step 4 analysis layer is SPARQL-traversable through object properties
introduced in proethica-cases v3.5.0 through v3.8.0:

| Property | Domain | Range |
|----------|--------|-------|
| `proeth-cases:answersQuestion` | EthicalConclusion | EthicalQuestion |
| `proeth-cases:extendsQuestion` | EthicalQuestion | EthicalQuestion (asymmetric, irreflexive) |
| `proeth-cases:explainsQuestion` | QuestionEmergence | EthicalQuestion |
| `proeth-cases:describesResolutionOf` | ResolutionPattern | case individual |
| `proeth-cases:referencesProvision` | CodeProvisionReference | CodeProvision |
| `proeth-cases:appliesTo` | CodeProvisionReference | case individual (open range) |
| `proeth-cases:decidesQuestion`, `addressesQuestion`, `alignsWithConclusion`, `involvesObligation`, `involvesAction`, `involvesConstraint`, `decidedByAgent` | DecisionPoint | respective targets |

## Defeasibility Relations

These properties expose obligation competition as first-class graph structure
(introduced in proethica-core v2.5.0). They are SPARQL-queryable and
reasoner-visible, replacing earlier narrative datatype encodings of
competing-duties resolution.

| Property | Domain | Range | Characteristic | Description |
|----------|--------|-------|----------------|-------------|
| `proeth-core:competesWith` | Obligation | Obligation | Symmetric | Two obligations stand in mutual competition |
| `proeth-core:prevailsOver` | Obligation | Obligation | Asymmetric, irreflexive | Winning obligation prevails over losing obligation |
| `proeth-core:defeasibleUnder` | Obligation | State | Directed | Obligation yields under the named state |

The three properties model obligation defeat as a triple: when an obligation
`O1` `competesWith` `O2`, and a state `S` obtains, then `O1` `prevailsOver`
`O2` `defeasibleUnder` `S`. Cases that report tension resolution between
competing duties carry these edges so non-monotonic reasoners can compute
defeat without parsing narrative text.

## Deprecated

Deprecated properties are retained for identifier stability and marked
`owl:deprecated`:

| Property | Live equivalent |
|----------|-----------------|
| `proeth-core:hasState` | `initiates` / `terminates` carry the linkage |
| `proeth-core:triggersEvent` | `proeth:causedByAction` and the causal family |
| `proeth-core:refersToDocument` | `containsProvision` and `documentTitle` |
| `proeth:hasTemporalRelation` | `fromEntity` / `toEntity` anchor the relation |

---

## Usage in Extraction

Extraction prompts derive their allowed relationship vocabulary from these
declarations; relations outside the declared inventory are carried as literal
overflow fields rather than minted as new properties. Reserved edges
(`usesResource`, `constrainedBy`, `realizesCapability`) are declared for the
Step 4 enrichment vocabulary and are not yet written by the pipeline.
