# Pipeline Terminology

This document defines the standardized terminology for the ProEthica extraction pipeline.

## Hierarchy

```
Pipeline
├── Step (1-5) - Major pipeline stages
│   ├── Pass (1-2) - Sub-extraction within Steps 1-3
│   │   └── Concept Types - Entity categories extracted
│   ├── Phase (2A-4) - Sub-stages within Step 4 only
│   └── View (1-3) - Interface tabs within Step 5 only
```

## Term Definitions

| Term | Scope | Definition |
|------|-------|------------|
| **Step** | Pipeline | Major pipeline stage (1-5). Each step produces distinct outputs. |
| **Pass** | Steps 1-3 | Sub-extraction within a step. Pass 1 extracts from Facts section; Pass 2 extracts from Discussion section. |
| **Phase** | Step 4 only | Sub-stages of synthesis operations. Phases 2A-2D, 3, and 4 perform different analysis tasks. |
| **View** | Step 5 only | Interface tabs for interactive scenario exploration. |

---

## Step-by-Step Breakdown

### Step 1: Contextual Framework

| Property | Value |
|----------|-------|
| Color | Blue (#3b82f6) |
| Pass 1 | Extract from Facts section |
| Pass 2 | Extract from Discussion section |

**Concepts Extracted**:

| Concept | Code | Description |
|---------|------|-------------|
| Roles | R | Professional positions and stakeholders |
| States | S | Situational conditions and circumstances |
| Resources | Rs | Referenced standards, codes, regulations |

### Step 2: Normative Framework

| Property | Value |
|----------|-------|
| Color | Purple (#8b5cf6) |
| Pass 1 | Extract from Facts section |
| Pass 2 | Extract from Discussion section |

**Concepts Extracted**:

| Concept | Code | Description |
|---------|------|-------------|
| Principles | P | Abstract ethical standards |
| Obligations | O | Concrete professional duties |
| Constraints | Cs | Prohibitions and limitations |
| Capabilities | Ca | Permissions and available options |

### Step 3: Temporal Framework

| Property | Value |
|----------|-------|
| Color | Teal (#14b8a6) |
| Pass 1 | Extract from Facts section |
| Pass 2 | Extract from Discussion section |

**Concepts Extracted**:

| Concept | Code | Description |
|---------|------|-------------|
| Actions | A | Professional responses and decisions |
| Events | E | Precipitating occurrences and triggers |

### Step 4: Synthesis and Analysis

| Property | Value |
|----------|-------|
| Color | Slate (#64748b) |
| Input | Entities from Steps 1-3 |

Step 4 operates on previously extracted entities rather than case text directly.

**Phases**:

| Phase | Name | Description |
|-------|------|-------------|
| 2A | Code Provisions | NSPE code reference extraction |
| 2B | Questions and Conclusions | Ethical questions and board conclusions |
| 2C | Transformation Analysis | Case transformation classification |
| 2D | Rich Analysis | Toulmin argumentation and causal-normative links |
| 3 | Decision Point Synthesis | E1-E3 algorithmic composition |
| 4 | Narrative Construction | Characters, timeline, moral intensity |

### Step 5: Interactive Scenario

| Property | Value |
|----------|-------|
| Input | Complete analysis from Steps 1-4 |

Transforms analyzed cases into interactive teaching scenarios.

**Views**:

| View | Name | Description |
|------|------|-------------|
| 1 | Narrative Overview | Case story with characters |
| 2 | Event Timeline | Chronological visualization |
| 3 | Decision Wizard | Step through ethical choices |

---

## Processing Order

The pipeline executes in strict order:

1. **Step 1 Pass 1** (Facts) then **Step 1 Pass 2** (Discussion)
2. **Step 2 Pass 1** (Facts) then **Step 2 Pass 2** (Discussion)
3. **Step 3 Pass 1** (Facts) then **Step 3 Pass 2** (Discussion)
4. **Step 4 Phases 2A, 2B, 2C, 2D, 3, 4**
5. **Step 5 Views 1, 2, 3**

Each Pass extracts concepts from both Facts and Discussion sections of the NSPE case. Discussion extraction becomes available after Facts extraction completes for that step.

---

## Visual Color Scheme

### Step Colors

| Step | Name | Hex | Bootstrap Equivalent |
|------|------|-----|---------------------|
| 1 | Contextual | #3b82f6 | Blue |
| 2 | Normative | #8b5cf6 | Purple |
| 3 | Temporal | #14b8a6 | Teal |
| 4 | Synthesis | #64748b | Slate |

### Entity Type Colors

| Entity | Code | Hex | Bootstrap Class |
|--------|------|-----|-----------------|
| Role | R | #0d6efd | bg-primary |
| State | S | #6f42c1 | bg-purple |
| Resource | Rs | #20c997 | bg-teal |
| Principle | P | #fd7e14 | bg-orange |
| Obligation | O | #dc3545 | bg-danger |
| Constraint | Cs | #6c757d | bg-secondary |
| Capability | Ca | #0dcaf0 | bg-info |
| Action | A | #198754 | bg-success |
| Event | E | #ffc107 | bg-warning |

---

## Related Documentation

- [Nine-Component Framework](nine-components.md) - Detailed concept definitions
- [Color Scheme](color-scheme.md) - Visual coding reference
- [Running Extractions](../analysis/running-extractions.md) - Extraction process
