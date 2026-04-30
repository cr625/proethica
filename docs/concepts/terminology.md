# Pipeline Terminology

This document defines the standardized terminology for the ProEthica extraction pipeline.

## Hierarchy

```
Pipeline
├── Step (1-5) - Major pipeline stages
│   ├── Pass (1-2) - Sub-extraction within Steps 1-3
│   │   └── Concept Types - Entity categories extracted
│   ├── Reconcile - Entity deduplication between Steps 3 and 4
│   └── Phase (2A-4) - Sub-stages within Step 4 only
```

## Term Definitions

| Term | Scope | Definition |
|------|-------|------------|
| **Step** | Pipeline | Major pipeline stage (1-5). Steps 1-4 perform extraction and synthesis; Step 5 presents the analyzed case as an interactive scenario. |
| **Pass** | Steps 1-3 | Sub-extraction within a step. Pass 1 extracts from Facts section; Pass 2 extracts from Discussion section. |
| **Reconcile** | Between Steps 3-4 | Deduplication of overlapping entities across sections and passes before synthesis. |
| **Phase** | Step 4 only | Sub-stages of synthesis operations. Phases 2A-2E, 3, and 4 perform different analysis tasks. |

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

### Step 2: Normative Requirements

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

### Step 3: Temporal Dynamics

| Property | Value |
|----------|-------|
| Color | Teal (#14b8a6) |
| Extraction | Single pass using LangGraph orchestration |

Step 3 extracts from the full case text (both Facts and Discussion) as a unified temporal analysis, unlike Steps 1-2 which use separate passes.

**Concepts Extracted**:

| Concept | Code | Description |
|---------|------|-------------|
| Actions | A | Professional responses and decisions |
| Events | E | Precipitating occurrences and triggers |

The extraction also produces **causal chains** (NESS test analysis), **Allen temporal relations** (OWL-Time standard), and a **timeline** sequencing actions and events.

### Reconcile

Between Steps 3 and 4, entity deduplication resolves overlapping entities across sections and passes. Reconcile can run in auto mode (batch pipeline) or interactive mode (manual review).

### Step 4: Whole-Case Synthesis

| Property | Value |
|----------|-------|
| Color | Slate/Purple gradient |
| Input | Entities from Steps 1-3 + case text |

Step 4 operates on both previously extracted entities and case text. It produces 8 additional entity types beyond the base 9.

**Phases**:

| Phase | Name | Description | Parallelism |
|-------|------|-------------|-------------|
| 2A | Code Provisions | NSPE code reference extraction | 2A runs in parallel with 2B |
| 2B | Precedent Cases | Precedent case reference extraction | 2B runs in parallel with 2A |
| 2C | Questions and Conclusions | Ethical questions and board conclusions | After 2A |
| 2D | Transformation Analysis | Case transformation classification | 2D runs in parallel with 2E |
| 2E | Rich Analysis | Causal-normative links, question emergence, resolution patterns | 2E runs in parallel with 2D (3 sub-tasks) |
| 3 | Decision Point Synthesis | E1-E3 algorithmic composition + LLM fallback | Sequential |
| 4 | Narrative Construction | Timeline and scenario seed | Sequential |

**Step 4 Sub-navigation** (sidebar labels):

| Label | URL | Description |
|-------|-----|-------------|
| Extraction | `/step4` | Phase overview and re-run controls |
| Review | `/step4/entities` | Entity review and OntServe commit |
| Full View | `/step4/review` | Tabbed view: Entities, Flow, Provisions, Precedents, Q&C, Analysis, Decisions, Narrative |

### Step 5: Interactive Scenario

Step 5 presents a fully analyzed case (Steps 1-4 complete) as an interactive scenario through three views:

| View | Purpose |
|------|---------|
| Narrative Overview | Case story with characters, organized as a readable narrative |
| Entity Timeline | Chronological visualization of actions and events with linked entities |
| Decision Wizard | Step through ethical decision points with discovery prompts and reasoning paths |

Step 5 is open to all users without authentication. See [Interactive Scenario](../viewing/interactive-scenario.md) for view-by-view details.

---

## Processing Order

The pipeline executes in strict order:

1. **Step 1**: Pass 1 (Facts) then Pass 2 (Discussion). Within each pass: S and Rs run in parallel after R completes.
2. **Step 2**: Pass 1 (Facts) then Pass 2 (Discussion). Within each pass: P then O sequentially, then Cs and Ca run in parallel.
3. **Step 3**: Single unified extraction using LangGraph orchestration.
4. **Reconcile**: Deduplicate overlapping entities across all passes.
5. **OntServe Commit**: Commit Steps 1-3 entities to ontology.
6. **Step 4**: Phases 2A||2B, then 2C, then 2D||2E, then Phase 3, then Phase 4.
7. **OntServe Commit**: Commit Step 4 entities to ontology.

Steps 1-2 extract from both Facts and Discussion sections via separate passes. Step 3 extracts from the full case text. Step 4 synthesizes across all extracted entities and case text.

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

**Steps 1-3 (9 base concepts)**:

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

**Step 4 (8 additional entity types)**:

| Entity | Phase | Description |
|--------|-------|-------------|
| Code Provision Reference | 2A | NSPE code sections cited |
| Precedent Case Reference | 2B | BER cases referenced in discussion |
| Ethical Question | 2C | Questions posed to the Board |
| Ethical Conclusion | 2C | Board's formal determinations |
| Canonical Decision Point | Phase 3 | Points where ethical choices must be made |
| Resolution Pattern | 2E | How tensions are resolved |
| Causal-Normative Link | 2E | Connections between causes and norms |
| Question Emergence | 2E | How ethical questions arise from case facts |

---

## Related Documentation

- [Nine-Component Framework](nine-components.md) - Detailed concept definitions
- [Color Scheme](color-scheme.md) - Visual coding reference
- [Running Extractions](../analysis/running-extractions.md) - Extraction process
