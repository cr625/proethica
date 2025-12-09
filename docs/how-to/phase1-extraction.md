# Phase 1: Multi-Pass Extraction

Phase 1 performs multi-pass concept extraction using ontology-validated definitions via MCP queries to OntServe. This guide covers the three extraction passes.

## Overview

Phase 1 extracts the nine concepts across three passes:

| Pass | Name | Concepts | Section |
|------|------|----------|---------|
| Pass 1 | Contextual Framework | Roles, States, Resources | Facts |
| Pass 2 | Normative Requirements | Principles, Obligations, Constraints, Capabilities | Discussion |
| Pass 3 | Temporal Dynamics | Events, Actions, Temporal Relations | Full Case |

## Starting Extraction

### Access the Pipeline

1. Navigate to the case detail page (`/cases/<id>`)
2. Click **Analyze** button
3. You'll arrive at the Scenario Pipeline overview

### Pipeline Navigation

The left sidebar shows pipeline steps:

| Step | Description | Prerequisite |
|------|-------------|--------------|
| Step 1 | Facts extraction (Pass 1) | None |
| Step 1b | Discussion extraction (Pass 1) | Step 1 |
| Step 2 | Facts extraction (Pass 2) | Step 1b |
| Step 2b | Discussion extraction (Pass 2) | Step 2 |
| Step 3 | Temporal extraction (Pass 3) | Step 2b |
| Step 4 | Case analysis | Step 3 |
| Step 5 | Scenario visualization | Step 4 |

## Pass 1: Contextual Framework

### Step 1: Facts Section

1. Click **Step 1** in the pipeline sidebar
2. The Facts section text is displayed
3. Click **Run Extraction** to begin

The system extracts:

| Concept | Description | Typical Count |
|---------|-------------|---------------|
| **Roles** | Professional positions | 3-6 entities |
| **States** | Situational conditions | 10-20 entities |
| **Resources** | Referenced standards | 15-30 entities |

### Entity Review

After extraction completes:

1. Review extracted entities in the table
2. Available classes from OntServe shown in collapsible section
3. Edit entity labels or definitions as needed
4. Select entities to keep

### Step 1b: Discussion Section

1. After completing Step 1 review, click **Step 1b**
2. Discussion section text displayed
3. Run extraction for additional Roles, States, Resources

## Pass 2: Normative Requirements

### Step 2: Facts Section

1. Click **Step 2** (requires Step 1b complete)
2. Extract from Facts section:

| Concept | Description | Typical Count |
|---------|-------------|---------------|
| **Principles** | Abstract ethical standards | 15-25 entities |
| **Obligations** | Concrete duties | 15-25 entities |
| **Constraints** | Prohibitions and limits | 15-20 entities |
| **Capabilities** | Permissions and options | 15-25 entities |

### Step 2b: Discussion Section

Extract normative concepts from Discussion section for comprehensive coverage.

## Pass 3: Temporal Dynamics

### Step 3: Full Case

1. Click **Step 3** (requires Step 2b complete)
2. Extracts from full case content:

| Concept | Description | Typical Count |
|---------|-------------|---------------|
| **Events** | Precipitating occurrences | 3-8 entities |
| **Actions** | Professional responses | 5-12 entities |
| **Temporal Relations** | Before/after relationships | 10-20 relations |
| **Causal Chains** | Cause-effect links | 5-10 chains |

### Timeline Construction

Pass 3 builds a timeline showing:

- Event sequence
- Action responses
- Causal relationships

## Extraction Options

### Clear and Re-run

Each step includes **Clear and Re-run** to restart extraction:

- Removes previously extracted entities
- Starts fresh extraction
- Use when results need improvement

### Model Selection

The system uses Claude for extraction by default. Model selection configured via environment variables.

### Progress Tracking

During extraction:

- SSE streaming shows progress
- Progress bar indicates completion
- Entity count updates in real-time

## Entity Quality

### Review Criteria

When reviewing extracted entities:

| Check | Description |
|-------|-------------|
| **Accuracy** | Entity correctly represents case content |
| **Completeness** | All relevant concepts captured |
| **Distinctness** | No duplicate entities |
| **Specificity** | Entities are appropriately specific |

### Editing Entities

For each entity, you can:

- Edit the label (short identifier)
- Edit the definition (full description)
- Change the class assignment
- Delete if not relevant

### Approving New Classes

When LLM identifies a concept not in the ontology:

1. Entity marked as "New Class"
2. Review if genuinely novel
3. Approve to add to OntServe ontology
4. Or reassign to existing class

## Commit Entities

After review, click **Commit** to:

- Save entities to temporary storage
- Link entities with extraction session
- Enable Step 4 analysis

Entities remain in temporary storage until explicitly committed to OntServe ontology.

## Extraction Metrics

After each pass, metrics show:

| Metric | Description |
|--------|-------------|
| **Total Entities** | Count of extracted entities |
| **By Type** | Breakdown by concept type |
| **New Classes** | Entities requiring new ontology classes |
| **Existing Matches** | Entities matching ontology |

## Example: Case 24-2

For NSPE Case 24-2 (AI in Engineering Practice):

**Pass 1 Results**:
- Roles (4): Engineer, Client, Employer, State Board
- States (16): Engineer lacks AI competence, Project uses AI tools, etc.
- Resources (29): NSPE Code II.1.a, State licensing requirements, etc.

**Pass 2 Results**:
- Principles (18): Hold paramount public safety, Practice competence, etc.
- Obligations (18): Verify AI-generated designs, Disclose limitations, etc.
- Constraints (18): Cannot certify beyond competence, etc.
- Capabilities (20): Can hire specialists, Can request extensions, etc.

**Pass 3 Results**:
- Events (3): Client requests AI design, etc.
- Actions (7): Uses AI without verification, etc.
- Relations (12): Request before decision, etc.
- Chains (6): Lacks competence leads to violation, etc.

## Troubleshooting

### Extraction Timeout

Long cases may timeout. Solutions:

1. Check LLM API status
2. Retry extraction
3. Contact administrator if persistent

### Missing OntServe Connection

If "Available Classes" shows empty:

1. Verify OntServe MCP is running
2. Check connection status in header
3. Restart OntServe if needed

### Duplicate Entities

LLM may extract duplicates:

1. Review carefully during entity review
2. Delete duplicates manually
3. Use Clear and Re-run for fresh extraction

## Related Guides

- [Entity Review](entity-review.md) - Detailed entity validation
- [Nine-Concept Framework](../concepts/nine-concepts.md) - Understanding concepts
- [Phase 2 Analysis](phase2-analysis.md) - Next phase
