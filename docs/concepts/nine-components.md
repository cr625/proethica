# Nine-Component Framework

ProEthica employs a nine-component formal framework to capture the essential elements of professional ethical evaluation. This framework, defined as **D = (R, P, O, S, Rs, A, E, Ca, Cs)**, synthesizes concepts from computational ethics literature into a unified structure.

## Framework Overview

The nine elements organize into three functional dimensions:

| Dimension | Elements | Function |
|-----------|----------|----------|
| **Contextual Grounding** | Roles (R), States (S), Resources (Rs) | Determines which ethical considerations apply |
| **Normative Structure** | Principles (P), Obligations (O), Constraints (Cs), Capabilities (Ca) | Provides the evaluation framework |
| **Temporal Dynamics** | Actions (A), Events (E) | Tracks how situations evolve |

```
Roles (R)
    | generate
Principles (P)
    | specify
Obligations (O)
    | apply within
States (S) + Resources (Rs)
    | precipitate
Events (E) --> Actions (A)
    | bounded by
Capabilities (Ca) + Constraints (Cs)
```

---

## Contextual Grounding Elements

These elements determine which ethical considerations apply based on professional position, situational circumstances, and accumulated precedents.

### Roles (R)

**Definition**: A role borne by an agent in virtue of a position or standing in professional practice.

Roles filter which principles and obligations apply. A professional role additionally generates obligations from the recognized ends of the profession and is governed by its ethical code; a participant role (a client, owner, or affected member of the public) carries standing in the case without profession-generated duties. An engineer's obligation to protect public safety differs fundamentally from a lawyer's duty of zealous advocacy or a physician's commitment to patient welfare.

**Examples**:

- Engineer (professional)
- Client (participant)
- Employer (participant)
- Contractor (participant)
- Consulting Engineer (professional)

**Ontology Source**: Defined in [proethica-core.ttl](https://ontserve.ontorealm.net/ontology/proethica-core) as `proeth-core:Role`, subclass of BFO:role. Subclasses in [proethica-intermediate.ttl](https://ontserve.ontorealm.net/ontology/proethica-intermediate) form two axes: the occupational axis headed by `ProfessionalRole` and `ParticipantRole` (disjoint), and the relational archetype axis headed by `RelationalRole` with the four Kong-derived archetypes (`ProviderClientRole`, `ProfessionalPeerRole`, `EmployerRelationshipRole`, `PublicResponsibilityRole`), inferred from committed relationship edges.

**Key Literature**: Oakley and Cocking (2001) on role-generated obligations; Kong et al. (2020) on the relational archetypes; Doernberg and Truog (2023) on spheres of morality. [Full references](../references.md#nine-component)

---

### States (S)

**Definition**: Situational context including facts, environmental conditions, and system status.

States capture the specific circumstances that affect ethical evaluation. Identical professional actions carry different ethical weight depending on the state. Context extends beyond technical parameters to include social and cultural factors that shape ethical acceptability.

**Examples**:

- Engineer lacks AI competence
- Client has limited budget
- Project deadline is imminent
- Public safety is at risk

**Ontology Source**: Defined in [proethica-core.ttl](https://ontserve.ontorealm.net/ontology/proethica-core) as `proeth-core:State`, subclass of BFO:specifically dependent continuant (states span the quality-disposition boundary). Represents time-varying properties (fluents) that affect ethical assessment.

**Key Literature**: Jones (1991) on moral intensity; Berreby et al. (2017) on fluents; Anderson and Anderson (2018) on ethically relevant features; Almpani and Stefaneas (2022) on priority ordering. [Full references](../references.md#nine-component)

---

### Resources (Rs)

**Definition**: Accumulated professional knowledge including codes, precedents, and practices.

Resources supply the established wisdom and standards of the profession. McLaren (2003) argues that professional ethical knowledge exists primarily in precedents rather than abstract rules. The meaning of fundamental ethical standards emerges through accumulated cases, not through philosophical analysis alone.

**Examples**:

- NSPE Code of Ethics II.1.a (competence requirement)
- State licensing regulations
- Industry technical standards
- Prior board decisions

**Ontology Source**: Defined in [proethica-core.ttl](https://ontserve.ontorealm.net/ontology/proethica-core) as `proeth-core:Resource`, an IAO information content entity. A code resource links to its provisions via `containsProvision`; the document identity is the `documentTitle` literal.

**Key Literature**: McLaren (2003) on precedents; Davis (1991) and Frankel (1989) on codes; Bench-Capon and Sartor (2003) on legal resources. [Full references](../references.md#nine-component)

---

## Normative Structure Elements

These elements transform high-level ethical ideals into concrete professional requirements.

### Principles (P)

**Definition**: High-level ethical guidelines that establish professional ideals.

Principles provide abstract guidance that must be interpreted through precedents. McLaren (2003) notes that principles contain open-textured terms that resist precise definition, making them subject to interpretation in different contexts. Without precedent-based grounding, principles remain too abstract for operational guidance.

**Examples**:

- Hold paramount the safety, health, and welfare of the public
- Perform services only in areas of competence
- Act as faithful agents or trustees
- Avoid deceptive acts

**Ontology Source**: Defined in [proethica-core.ttl](https://ontserve.ontorealm.net/ontology/proethica-core) as `proeth-core:Principle`, subclass of IAO:directive information entity. Subclasses in [proethica-intermediate.ttl](https://ontserve.ontorealm.net/ontology/proethica-intermediate) include `FundamentalEthicalPrinciple`, `ProfessionalVirtuePrinciple`, `RelationalPrinciple`, `DomainSpecificPrinciple`.

**Key Literature**: McLaren (2003) on extensional definition and open texture; Frankel (1989) on aspirational codes; Morley et al. (2021) on constitutional principles; Taddeo et al. (2024) on teleological balancing; Prem (2023) on operationalization. [Full references](../references.md#nine-component)

---

### Obligations (O)

**Definition**: Specific requirements for action or restraint.

Obligations transform principles into concrete, evaluable professional requirements. Unlike principles that provide general guidance, obligations establish the specific requirements necessary for evaluation. Dennis et al. (2016) specify abstract principles into precise context-dependent constraints so that choices are computationally verifiable.

**Examples**:

- Verify AI-generated designs before certification
- Disclose conflicts of interest to clients
- Maintain confidentiality of client information
- Report safety violations to appropriate authorities

**Ontology Source**: Defined in [proethica-core.ttl](https://ontserve.ontorealm.net/ontology/proethica-core) as `proeth-core:Obligation`, subclass of IAO:directive information entity. Extracted from NSPE Code provisions and case narratives.

**Key Literature**: Donohue (2017) on deontic typing; Dennis et al. (2016) on specification requirements; Ross and Stratton-Lake (2007) and Anderson and Anderson (2011) on prima facie duties and defeasibility. [Full references](../references.md#nine-component)

---

### Constraints (Cs)

**Definition**: Boundaries on permissible conduct, ranging from inviolable prohibitions to defeasible defaults that tolerate justified exceptions.

Constraints establish limits on professional behavior by foreclosing regions of the action space. Systems verify constraints before evaluating trade-offs among competing obligations. Professional ethical evaluation cannot occur without first establishing which actions fall outside acceptable boundaries.

**Examples**:

- Cannot certify work beyond competence
- Cannot misrepresent qualifications
- Cannot prioritize profit over safety
- Cannot disclose confidential information improperly

**Ontology Source**: Defined in [proethica-core.ttl](https://ontserve.ontorealm.net/ontology/proethica-core) as `proeth-core:Constraint`, subclass of IAO:directive information entity. Distinguished from Obligations by expressing prohibitions rather than requirements.

**Key Literature**: Arkin (2008) on negative behavioral limits; Ganascia (2007) on default rules with exceptions; Dennis et al. (2016) on specification; Benzmüller et al. (2020) on formal verification. [Full references](../references.md#nine-component)

---

### Capabilities (Ca)

**Definition**: Competencies spanning norm competence, situational awareness, learning, and explanation abilities.

Capabilities ensure sufficient expertise for professional practice. Tolmeijer et al. (2021) identify four essential capability types: norm competence, situational awareness, learning and adaptation, and explanation and justification. These capabilities define prescriptive requirements for systems that support professional judgment.

**Examples**:

- Can hire specialists for areas outside competence
- Can request additional time for proper review
- Can consult with ethics board
- Can decline work outside expertise

**Ontology Source**: Defined in [proethica-core.ttl](https://ontserve.ontorealm.net/ontology/proethica-core) as `proeth-core:Capability`, subclass of BFO:disposition. Represents competencies the agent possesses, realized through professional activities.

**Key Literature**: Tolmeijer et al. (2021) on the four ethical-competence requirements; Epstein and Hundert (2002) on professional competence. [Full references](../references.md#nine-component)

---

## Temporal Dynamics Elements

These elements track how professional scenarios evolve over time through actions and events.

### Actions (A)

**Definition**: Volitional professional interventions that carry ethical weight.

Actions represent deliberate choices with professional responsibility. Systems must separate Actions from Events through attribution of responsibility, as professional accountability attaches only to volitional interventions. Action evaluation must account for complexity in professional judgment, including cases where omission carries liability.

**Examples**:

- Uses AI without verification (action taken)
- Hire specialist consultant (alternative)
- Decline project (alternative)
- Request deadline extension (alternative)

**Ontology Source**: Defined in [proethica-core.ttl](https://ontserve.ontorealm.net/ontology/proethica-core) as `proeth-core:Action`, subclass of BFO:process. Distinguished from Events by volitional nature.

**Key Literature**: Sarmiento et al. (2022) on volitional causality; Wright (1985) on the NESS test; Kroll (2020) on the bases of accountability; Floridi and Sanders (2004) on accountability without intentionality; Govindarajulu and Bringsjord (2017) on intention. [Full references](../references.md#nine-component)

---

### Events (E)

**Definition**: Occurrences originating outside agent control that affect evaluation.

Events capture temporal dynamics and external triggers. The Event Calculus framework formally distinguishes between agent-caused outcomes (Actions) and exogenous occurrences. Events modify fluents and trigger new obligations to generate state transitions that create the temporal context for professional evaluation.

**Examples**:

- Client requests AI-assisted design
- Engineer discovers safety flaw
- Competitor makes job offer
- Deadline arrives

**Ontology Source**: Defined in [proethica-core.ttl](https://ontserve.ontorealm.net/ontology/proethica-core) as `proeth-core:Event`, subclass of BFO:process. Represents external occurrences distinct from volitional Actions.

**Key Literature**: Kowalski and Sergot (1986) on the Event Calculus; Berreby et al. (2017) on event origins; Sarmiento et al. (2022) on causal chains; Almpani et al. (2023) on emergency contingency protocols. [Full references](../references.md#nine-component)

---

## Extraction Process

ProEthica extracts these nine components through three extraction steps, followed by reconciliation and synthesis.

### Step 1: Contextual Framework

Extracts from Facts and Discussion sections separately (Pass 1, Pass 2). Within each pass, Roles extract first, then States and Resources run in parallel.

| Concept | Typical Count | Focus |
|---------|--------------|-------|
| Roles | 3-6 | Professional positions identified |
| States | 10-20 | Situational conditions |
| Resources | 15-30 | Referenced standards and codes |

### Step 2: Normative Requirements

Extracts from Facts and Discussion sections separately (Pass 1, Pass 2). Within each pass, Obligations extract first, then Constraints and Capabilities run in parallel.

| Concept | Typical Count | Focus |
|---------|--------------|-------|
| Principles | 15-25 | Abstract ethical standards |
| Obligations | 15-25 | Concrete duties |
| Constraints | 15-20 | Prohibitions and limits |
| Capabilities | 15-25 | Permissions and options |

### Step 3: Temporal Dynamics

Extracts from the full case text (Facts and Discussion combined) in a single unified pass using LangGraph orchestration.

| Concept | Typical Count | Focus |
|---------|--------------|-------|
| Actions | 5-12 | Professional responses |
| Events | 3-8 | Precipitating occurrences |
| Causal Chains | 3-6 | NESS test analysis |
| Allen Relations | 10-20 | Temporal ordering |

### Reconcile

Entity deduplication merges overlapping entities across sections and passes before synthesis.

### Step 4: Whole-Case Synthesis

Analyzes extracted entities and case text across multiple phases (2A-2E, Phase 3, Phase 4) to produce 8 additional entity types: Code Provision References, Precedent Case References, Ethical Questions, Ethical Conclusions, Canonical Decision Points, Resolution Patterns, Causal-Normative Links, and Question Emergence. The full extraction pipeline produces **17 entity types** across Steps 1-4. Step 5 presents the analyzed case as an interactive scenario but introduces no new entity types.

---

## Theoretical Foundations

The framework synthesizes three foundational works:

| Work | Contribution | Elements |
|------|--------------|----------|
| **McLaren (2003)** | Extensional definition of principles through precedents | R, Rs, P |
| **Berreby et al. (2017)** | Modular architecture for temporal ethical reasoning | S, A, E, O |
| **Tolmeijer et al. (2021)** | Essential capabilities for ethical agents | Ca |

For complete academic references with DOIs and citations, see [References](../references.md#nine-component).

---

## Related Guides

- [Running Extractions](../analysis/running-extractions.md) - Extracting concepts
- [Entity Review](../analysis/entity-review.md) - Validating extracted concepts
- [Ontology Integration](../admin-guide/ontology-integration.md) - Concept definitions
- [Academic References](../references.md) - Full citations and sources
