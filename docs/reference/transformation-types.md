# Transformation Types

This document describes the ethical transformation classification system used in Phase 2 analysis.

## Overview

ProEthica classifies ethical transformations based on the scenario dynamics framework of Marchais-Roubelat and Roubelat (2015). This framework identifies four transformation patterns that describe how ethical situations evolve.

## The Four Transformation Types

### Transfer

**Definition**: A clear shift from one ethical state to another.

**Pattern**: A → B

**Characteristics**:
- Decisive transition between states
- Clear before/after distinction
- Irreversible or difficult to reverse
- Identifiable trigger event

**Example - Case 24-2**:
```
Initial State: Engineer operating within competence
Trigger: Client requests AI-assisted design
Action: Uses AI without verification capability
Final State: Engineer exceeding competence boundaries

Classification: Transfer (ai_competence_boundary_violation)
```

**Indicators**:
- Obligation status changes (compliant → violated)
- Professional role boundaries crossed
- Clear ethical threshold passed

### Stalemate

**Definition**: Competing forces prevent resolution.

**Pattern**: A ↔ B

**Characteristics**:
- Opposing obligations in tension
- No clear resolution path
- Persistent deadlock state
- Multiple valid perspectives

**Example**:
```
Obligation A: Maintain client confidentiality
Obligation B: Report safety violations
Tension: Information reveals safety risk but is confidential

Classification: Stalemate (confidentiality_vs_safety)
```

**Indicators**:
- Multiple conflicting obligations
- Each position ethically justifiable
- Resolution requires value prioritization
- External adjudication often needed

### Oscillation

**Definition**: Alternating between states over time.

**Pattern**: A → B → A → B...

**Characteristics**:
- Cyclic pattern of states
- Recurring tension
- Temporary resolutions
- Systemic instability

**Example**:
```
State A: Engineer accepts project within scope
State B: Scope creep pushes beyond competence
Return to A: Scope reduced after concerns raised
Return to B: Client pressure expands scope again

Classification: Oscillation (scope_competence_cycle)
```

**Indicators**:
- Repeated pattern over time
- Same tensions resurface
- Temporary fixes don't hold
- Structural issues unaddressed

### Phase Lag

**Definition**: Delayed response to ethical change.

**Pattern**: A ... → B

**Characteristics**:
- Recognition lag between trigger and response
- Ethical obligations clear but action delayed
- Often involves procedural constraints
- May involve denial or avoidance

**Example**:
```
Trigger: Safety concern identified (t=0)
Recognition: Engineer acknowledges issue (t+2 weeks)
Action: Report filed (t+4 weeks)
Resolution: Corrective measures (t+8 weeks)

Classification: Phase Lag (delayed_safety_response)
```

**Indicators**:
- Significant time between trigger and action
- Multiple missed opportunities to act
- Procedural or psychological barriers
- Eventual alignment with obligations

## Classification Process

### Step 1: Identify States

Document the ethical states before and after key events:

| Element | Description |
|---------|-------------|
| Initial State | Starting ethical position |
| Trigger Events | What precipitated change |
| Intermediate States | Transitions observed |
| Final State | Ending ethical position |

### Step 2: Analyze Pattern

Compare state transitions to patterns:

| Pattern | Criteria |
|---------|----------|
| Transfer | Single clear transition |
| Stalemate | Balanced opposing forces |
| Oscillation | Cyclic repetition |
| Phase Lag | Delayed response |

### Step 3: Identify Subtype

Assign specific pattern label:

| Base Type | Example Subtypes |
|-----------|-----------------|
| Transfer | competence_violation, disclosure_failure |
| Stalemate | confidentiality_safety_conflict |
| Oscillation | scope_competence_cycle |
| Phase Lag | delayed_disclosure, recognition_lag |

## LLM Classification

### Prompt Structure

The system prompts Claude to classify:

```
Analyze the ethical transformation in this case.

Case facts: [extracted facts]
Actions taken: [identified actions]
Obligations: [relevant obligations]

Classify the transformation type:
1. Transfer - clear state change
2. Stalemate - competing forces deadlock
3. Oscillation - cyclic pattern
4. Phase Lag - delayed response

Provide:
- Classification type
- Pattern name (specific identifier)
- Justification
```

### Response Parsing

System extracts:

| Field | Example |
|-------|---------|
| `type` | transfer |
| `pattern` | ai_competence_boundary_violation |
| `justification` | "Engineer's decision to use AI..." |
| `confidence` | 0.85 |

## Storage

### Database Table

`case_transformation` stores classification:

| Column | Type | Description |
|--------|------|-------------|
| `case_id` | FK | Case reference |
| `transformation_type` | VARCHAR | One of four types |
| `pattern_name` | VARCHAR | Specific pattern |
| `initial_state` | TEXT | Starting state description |
| `final_state` | TEXT | Ending state description |
| `triggers` | JSONB | Precipitating events |
| `justification` | TEXT | Classification rationale |

### Querying

```sql
SELECT
    d.title,
    ct.transformation_type,
    ct.pattern_name
FROM case_transformation ct
JOIN documents d ON ct.case_id = d.id
WHERE ct.transformation_type = 'transfer';
```

## User Interface

### Classification Display

Phase 2 shows classification with:

- Type label (Transfer, Stalemate, etc.)
- Pattern name
- Visual indicator
- Justification text

### Editing Classification

Users can adjust:

1. Change transformation type
2. Edit pattern name
3. Modify justification
4. Add notes

## Pattern Library

### Common Transfer Patterns

| Pattern | Description |
|---------|-------------|
| `competence_boundary_violation` | Acting outside expertise |
| `disclosure_failure` | Not revealing required information |
| `conflict_acceptance` | Taking conflicted role |
| `certification_error` | Certifying improperly |

### Common Stalemate Patterns

| Pattern | Description |
|---------|-------------|
| `confidentiality_safety` | Privacy vs. safety |
| `employer_public` | Employer vs. public interest |
| `efficiency_thoroughness` | Speed vs. quality |

### Common Oscillation Patterns

| Pattern | Description |
|---------|-------------|
| `scope_competence_cycle` | Recurring scope creep |
| `deadline_quality_trade` | Repeating time/quality tension |

### Common Phase Lag Patterns

| Pattern | Description |
|---------|-------------|
| `delayed_disclosure` | Slow to reveal information |
| `recognition_lag` | Delayed acknowledgment |
| `procedural_delay` | System-caused delays |

## Theoretical Foundation

### Source

Marchais-Roubelat, A., & Roubelat, F. (2015). Designing a moving strategic foresight approach: Ontological and methodological issues of scenario design. In *Strategic Thinking in a Hospital Setting* (pp. 161-182).

### Key Concepts

The framework originates from strategic foresight and scenario analysis:

- **Scenario dynamics**: How situations evolve over time
- **State transitions**: Movement between defined conditions
- **Pattern recognition**: Identifying recurring structures

### Application to Ethics

ProEthica adapts this framework for ethical analysis:

- States = ethical positions/compliance status
- Transitions = changes in ethical standing
- Patterns = recognizable ethical dynamics

## Related Guides

- [Phase 2 Analysis](../how-to/phase2-analysis.md)
- [Nine-Concept Framework](../concepts/nine-concepts.md)
- [Precedent Discovery](../how-to/precedent-discovery.md)
