# Nine-Concept Framework

ProEthica employs a nine-component formal framework to capture the essential components of professional ethical analysis. This framework, defined as **D = (R, P, O, S, Rs, A, E, Ca, Cs)**, synthesizes concepts from computational ethics literature into a unified structure.

## Framework Overview

The nine concepts organize according to logical dependencies in profession-based ethical decision analysis:

```
Roles (R)
    ↓ generate
Principles (P)
    ↓ specify
Obligations (O)
    ↓ apply within
States (S) + Resources (Rs)
    ↓ precipitate
Events (E) → Actions (A)
    ↓ bounded by
Capabilities (Ca) + Constraints (Cs)
```

## The Nine Concepts

### Roles (R)

**Definition**: Professional positions that generate abstract principles.

Roles define the professional identity of individuals in an ethical scenario. Each role carries inherent responsibilities and generates specific obligations.

**Examples**:
- Engineer
- Client
- Employer
- Public Official
- Consulting Engineer

**Ontology Source**: Builds on Oakley and Cocking's (2001) role-generated obligations.

### Principles (P)

**Definition**: Abstract ethical standards derived from professional roles.

Principles are general ethical guidelines that apply across specific situations. They form the foundational layer of professional ethics codes.

**Examples**:
- Hold paramount the safety, health, and welfare of the public
- Perform services only in areas of competence
- Act as faithful agents or trustees
- Avoid deceptive acts

**Relation to Obligations**: Principles specify concrete Obligations that professionals must follow.

### Obligations (O)

**Definition**: Concrete duties derived from principles.

Obligations are specific, actionable requirements that professionals must fulfill. They form the deontic foundation of professional conduct.

**Examples**:
- Verify AI-generated designs before certification
- Disclose conflicts of interest to clients
- Maintain confidentiality of client information
- Report safety violations to appropriate authorities

**Deontic Status**: Obligations express what professionals *must* do (mandatory requirements).

### States (S)

**Definition**: Situational context and conditions within which obligations apply.

States describe the circumstances, conditions, and facts that characterize the ethical scenario. They establish the context for decision-making.

**Examples**:
- Engineer lacks AI competence
- Client has limited budget
- Project deadline is imminent
- Public safety is at risk

**Role in Analysis**: States help determine which obligations apply and how they should be prioritized.

### Resources (Rs)

**Definition**: Available knowledge, references, and informational assets.

Resources include codes of ethics, technical standards, regulatory requirements, and other materials that inform ethical decision-making.

**Examples**:
- NSPE Code of Ethics II.1.a (competence requirement)
- State licensing regulations
- Industry technical standards
- Prior board decisions

**Function**: Resources provide authoritative guidance for resolving ethical questions.

### Events (E)

**Definition**: Precipitating occurrences that require ethical response.

Events are specific happenings that trigger the need for ethical deliberation and action. They mark transitions in the scenario timeline.

**Examples**:
- Client requests AI-assisted design
- Engineer discovers safety flaw
- Competitor makes job offer
- Deadline arrives

**Temporal Nature**: Events have specific occurrence times and create before/after relationships.

### Actions (A)

**Definition**: What professionals do or could do in response to events.

Actions are deliberate behaviors taken (or not taken) by professionals. Analysis considers both actions actually taken and alternatives not pursued.

**Examples**:
- Uses AI without verification (action taken)
- Hire specialist consultant (alternative)
- Decline project (alternative)
- Request deadline extension (alternative)

**Ethical Significance**: Actions are evaluated against obligations, capabilities, and constraints.

### Capabilities (Ca)

**Definition**: What professionals can do within their competence and authority.

Capabilities describe the range of permissible and possible actions available to professionals. They establish what is within professional scope.

**Examples**:
- Can hire specialists for areas outside competence
- Can request additional time for proper review
- Can consult with ethics board
- Can decline work outside expertise

**Deontic Status**: Capabilities express what professionals *may* do (permissions).

### Constraints (Cs)

**Definition**: Limitations on professional conduct.

Constraints define boundaries that professionals cannot cross. They may arise from competence limits, ethical prohibitions, or situational factors.

**Examples**:
- Cannot certify work beyond competence
- Cannot misrepresent qualifications
- Cannot prioritize profit over safety
- Cannot disclose confidential information

**Deontic Status**: Constraints express what professionals *must not* do (prohibitions).

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

## Concept Relationships

The nine concepts form a coherent structure:

**Generation Chain**: Roles → Principles → Obligations

**Context Dependencies**: States and Resources determine which Obligations apply

**Action Framework**: Events precipitate Actions bounded by Capabilities and Constraints

**Causal Chains**: Conditions (States) can lead to Obligation violations

## Theoretical Foundations

The framework builds on established computational ethics research:

- **Modular Architecture**: Berreby, Bourgne, and Ganascia (2017) - declarative ethical reasoning
- **Role Ethics**: Oakley and Cocking (2001) - virtue ethics and professional roles
- **Case-Based Ethics**: McLaren (2003) - extensionally defining principles through cases
- **Role-Based Alignment**: Rauch et al. (2025) - decision-maker alignment through roles

## Related Guides

- [Phase 1 Extraction](../how-to/phase1-extraction.md) - Extracting concepts
- [Entity Review](../how-to/entity-review.md) - Validating extracted concepts
- [Ontology Integration](../reference/ontology-integration.md) - Concept definitions
