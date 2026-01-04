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

**Definition**: Professional positions with associated duties, responsibilities, and decision-making authority.

Roles filter which principles and obligations apply based on professional identity. Each profession serves distinctive human goods and maintains unique normative commitments, requiring domain-specific customization. An engineer's obligation to protect public safety differs fundamentally from a lawyer's duty of zealous advocacy or a physician's commitment to patient welfare.

**Examples**:

- Engineer
- Client
- Employer
- Public Official
- Consulting Engineer

**Ontology Source**: Defined in [proethica-core.ttl](https://ontserve.ontorealm.net/ontology/proethica-core) as `proeth-core:Role`, subclass of BFO:role. Subclasses in [proethica-intermediate.ttl](https://ontserve.ontorealm.net/ontology/proethica-intermediate) include `ProfessionalRole`, `InstitutionalRole`, `StakeholderRole`.

**Key Literature**: Oakley & Cocking (2001) on role-generated obligations; Kong et al. (2020) on identity virtues; Doernberg & Truog (2023) on sphere-based roles. [Full references](/tools/references#nine-component)

---

### States (S)

**Definition**: Situational context including facts, environmental conditions, and system status.

States capture the specific circumstances that affect ethical evaluation. Identical professional actions carry different ethical weight depending on the state. Context extends beyond technical parameters to include social and cultural factors that shape ethical acceptability.

**Examples**:

- Engineer lacks AI competence
- Client has limited budget
- Project deadline is imminent
- Public safety is at risk

**Ontology Source**: Defined in [proethica-core.ttl](https://ontserve.ontorealm.net/ontology/proethica-core) as `proeth-core:State`, subclass of BFO:quality. Represents time-varying properties (fluents) that affect ethical assessment.

**Key Literature**: Jones (1991) on moral intensity; Almpani et al. (2023) on Event Calculus; Berreby et al. (2017) on fluents; Sarmiento et al. (2023) on causal chains. [Full references](/tools/references#nine-component)

---

### Resources (Rs)

**Definition**: Accumulated professional knowledge including codes, precedents, and practices.

Resources supply the established wisdom and standards of the profession. McLaren (2003) argues that professional ethical knowledge exists primarily in precedents rather than abstract rules. The meaning of fundamental ethical standards emerges through accumulated cases, not through philosophical analysis alone.

**Examples**:

- NSPE Code of Ethics II.1.a (competence requirement)
- State licensing regulations
- Industry technical standards
- Prior board decisions

**Ontology Source**: Defined in [proethica-core.ttl](https://ontserve.ontorealm.net/ontology/proethica-core) as `proeth-core:Resource`, subclass of BFO:independent continuant. Linked to IAO documents via `refersToDocument` property.

**Key Literature**: McLaren (2003) on precedents; Davis (1991) and Frankel (1989) on codes; Harris et al. (2018) on decision procedures; Anderson & Anderson (2018) on GenEth learning. [Full references](/tools/references#nine-component)

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

**Ontology Source**: Defined in [proethica-core.ttl](https://ontserve.ontorealm.net/ontology/proethica-core) as `proeth-core:Principle`, subclass of IAO:information content entity. Subclasses in [proethica-intermediate.ttl](https://ontserve.ontorealm.net/ontology/proethica-intermediate) include `FundamentalEthicalPrinciple`, `ProfessionalVirtuePrinciple`, `RelationalPrinciple`, `DomainSpecificPrinciple`.

**Key Literature**: McLaren (2003) on extensional definition; Prem (2023) on abstract nature; Taddeo et al. (2024) on constitutional interpretation. [Full references](/tools/references#nine-component)

---

### Obligations (O)

**Definition**: Specific requirements for action or restraint.

Obligations transform principles into concrete, evaluable professional requirements. Unlike principles that provide general guidance, obligations establish the specific requirements necessary for evaluation. Dennis et al. (2016) emphasize that obligations require complete specification to be computationally verifiable.

**Examples**:

- Verify AI-generated designs before certification
- Disclose conflicts of interest to clients
- Maintain confidentiality of client information
- Report safety violations to appropriate authorities

**Ontology Source**: Defined in [proethica-core.ttl](https://ontserve.ontorealm.net/ontology/proethica-core) as `proeth-core:Obligation`, subclass of IAO:information content entity. Extracted from NSPE Code provisions and case narratives.

**Key Literature**: Dennis et al. (2016) on specification requirements; Anderson & Anderson (2006, 2007, 2011) on duty quantification; Almpani et al. (2023) on dynamic priorities. [Full references](/tools/references#nine-component)

---

### Constraints (Cs)

**Definition**: Inviolable boundaries that cannot be crossed regardless of benefits.

Constraints establish hard limits on professional behavior, defining what must never be done. Systems must verify constraints before evaluating trade-offs among competing obligations. Professional ethical evaluation cannot occur without first establishing which actions fall outside acceptable boundaries.

**Examples**:

- Cannot certify work beyond competence
- Cannot misrepresent qualifications
- Cannot prioritize profit over safety
- Cannot disclose confidential information improperly

**Ontology Source**: Defined in [proethica-core.ttl](https://ontserve.ontorealm.net/ontology/proethica-core) as `proeth-core:Constraint`, subclass of IAO:information content entity. Distinguished from Obligations by expressing prohibitions rather than requirements.

**Key Literature**: Ganascia (2007) on defeasible logic; Dennis et al. (2016) on hierarchical management; Arkin (2008) on ethical governors. [Full references](/tools/references#nine-component)

---

### Capabilities (Ca)

**Definition**: Competencies spanning norm competence, situational awareness, learning, and explanation abilities.

Capabilities ensure sufficient expertise for professional practice. Tolmeijer et al. (2021) identify four essential capability types: norm competence, situational awareness, learning and adaptation, and explanation and justification. These capabilities define prescriptive requirements for systems that support professional judgment.

**Examples**:

- Can hire specialists for areas outside competence
- Can request additional time for proper review
- Can consult with ethics board
- Can decline work outside expertise

**Ontology Source**: Defined in [proethica-core.ttl](https://ontserve.ontorealm.net/ontology/proethica-core) as `proeth-core:Capability`, subclass of BFO:realizable entity. Represents what professionals *may* do (permissions).

**Key Literature**: Narvaez & Rest (1995) on Four Component Model; Tolmeijer et al. (2021) on four requirements; Berreby et al. (2017) on Action Model; Epstein & Hundert (2002) on domain-specific judgment. [Full references](/tools/references#nine-component)

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

**Key Literature**: Sarmiento et al. (2023) on volitional nature; Bonnemains et al. (2018) on multi-framework evaluation; Govindarajulu & Bringsjord (2017) on intentional status. [Full references](/tools/references#nine-component)

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

**Key Literature**: Berreby et al. (2017) on exogenous occurrences; Event Calculus formalism; Arkin (2008) on emergency overrides. [Full references](/tools/references#nine-component)

---

## Extraction Process

ProEthica extracts these nine concepts through three passes:

### Pass 1: Contextual Framework

Extracts foundational elements that establish the scenario context:

| Concept | Typical Count | Focus |
|---------|--------------|-------|
| Roles | 3-6 | Professional positions identified |
| States | 10-20 | Situational conditions |
| Resources | 15-30 | Referenced standards and codes |

### Pass 2: Normative Requirements

Extracts ethical framework elements:

| Concept | Typical Count | Focus |
|---------|--------------|-------|
| Principles | 15-25 | Abstract ethical standards |
| Obligations | 15-25 | Concrete duties |
| Constraints | 15-20 | Prohibitions and limits |
| Capabilities | 15-25 | Permissions and options |

### Pass 3: Temporal Dynamics

Extracts action and event sequences:

| Concept | Typical Count | Focus |
|---------|--------------|-------|
| Events | 3-8 | Precipitating occurrences |
| Actions | 5-12 | Professional responses |
| Relations | 10-20 | Temporal and causal links |

---

## Theoretical Foundations

The framework synthesizes three foundational works:

| Work | Contribution | Elements |
|------|--------------|----------|
| **McLaren (2003)** | Extensional definition of principles through precedents | R, Rs, P |
| **Berreby et al. (2017)** | Modular architecture for temporal ethical reasoning | S, A, E, O |
| **Tolmeijer et al. (2021)** | Essential capabilities for ethical agents | Ca, Cs |

For complete academic references with DOIs and citations, see [References](/tools/references#nine-component).

---

## Related Guides

- [Phase 1 Extraction](../how-to/phase1-extraction.md) - Extracting concepts
- [Entity Review](../how-to/entity-review.md) - Validating extracted concepts
- [Ontology Integration](../reference/ontology-integration.md) - Concept definitions
- [Academic References](/tools/references) - Full citations and sources
