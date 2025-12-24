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

Navigate to any case detail page. The numbered step buttons appear at the top of the case:

![Case Step Buttons](../assets/images/screenshots/case-step-buttons-content.png)

Steps must be processed in sequence. Completed steps display as green; incomplete steps show the step number. Click any available step to begin extraction for that pass.

### Pipeline Steps

| Step | Name | Concepts Extracted |
|------|------|-------------------|
| Step 1 | Contextual Framework | Roles, States, Resources |
| Step 2 | Normative Requirements | Principles, Obligations, Constraints, Capabilities |
| Step 3 | Temporal Dynamics | Actions, Events |
| Step 4 | Synthesis | Provisions, Questions, Decision Points, Narrative |

Each step extracts from both Facts and Discussion sections. The Discussion section becomes available after Facts extraction completes for that step.

## Pass 1: Contextual Framework

### Step 1: Facts Section

1. Click the **Step 1** button on the case page
2. The extraction page displays the Facts section text
3. Click individual extraction buttons for each concept type:
   - **Extract Roles** - Professional positions
   - **Extract States** - Situational conditions
   - **Extract Resources** - Referenced standards

After extraction completes for each type:

| Concept | Description | Typical Count |
|---------|-------------|---------------|
| **Roles** | Professional positions | 3-6 entities |
| **States** | Situational conditions | 10-20 entities |
| **Resources** | Referenced standards | 15-30 entities |

### Entity Review

Click **Review Pass 1 Entities (Facts)** to access the review page:

1. Entities displayed in cards organized by concept type
2. Available OntServe classes shown for matching
3. Remove incorrect entities using the delete button
4. Use the **Facts/Discussion** toggle to switch between sections

### Discussion Section

After completing Facts extraction:

1. Click **Discussion Section** on the extraction page
2. Extract concepts from the Discussion section using the same buttons
3. Review using **Review Pass 1 Entities** with the Discussion toggle active

## Pass 2: Normative Requirements

### Step 2: Facts Section

1. Click the **Step 2** button on the case page
2. Click individual extraction buttons:
   - **Extract Principles** - Abstract ethical standards
   - **Extract Obligations** - Concrete duties
   - **Extract Constraints** - Prohibitions and limits
   - **Extract Capabilities** - Permissions and options

Expected entity counts:

| Concept | Description | Typical Count |
|---------|-------------|---------------|
| **Principles** | Abstract ethical standards | 15-25 entities |
| **Obligations** | Concrete duties | 15-25 entities |
| **Constraints** | Prohibitions and limits | 15-20 entities |
| **Capabilities** | Permissions and options | 15-25 entities |

### Discussion Section

Click **Discussion Section** after completing Facts extraction to extract normative concepts from the Discussion section.

## Pass 3: Temporal Dynamics

### Step 3

1. Click the **Step 3** button on the case page
2. Step 3 extracts temporal concepts from the full case:

| Concept | Description | Typical Count |
|---------|-------------|---------------|
| **Actions** | Professional responses and decisions | 5-12 entities |
| **Events** | Precipitating occurrences | 3-8 entities |

The temporal extraction also identifies causal relationships and timeline sequences.

## Extraction Options

### Re-run Extraction

The review page includes a **Re-run** button to return to the extraction page and run extraction again if results need improvement.

### Progress Tracking

During extraction, a progress indicator shows completion status. Entity counts update after each extraction completes.

## Entity Quality

### Review Criteria

When reviewing extracted entities:

| Check | Description |
|-------|-------------|
| **Accuracy** | Entity correctly represents case content |
| **Completeness** | All relevant concepts captured |
| **Distinctness** | No duplicate entities |
| **Specificity** | Entities are appropriately specific |

### Managing Entities

For each entity on the review page:

- Remove incorrect entities using the delete button
- View entity details and matched ontology classes

Full entity editing after commit is planned for a future release.

### New Classes

When the LLM identifies a concept not matching existing ontology classes, it appears with a "New" badge. Click the badge to open the Entity Match Details modal:

- **Search for Alternative Match** - Search for an existing ontology class
- **Confirm Current Match** - Accept the current match status
- **Mark as New Class** - Confirm this as a new class proposal

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
- Actions (7): Uses AI without verification, Certifies design, etc.
- Events (3): Client requests AI design, Board receives complaint, etc.

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
3. Use **Re-run** to re-extract if needed

## Related Guides

- [Entity Review](entity-review.md) - Detailed entity validation
- [Nine-Concept Framework](../concepts/nine-concepts.md) - Understanding concepts
- [Phase 2 Analysis](phase2-analysis.md) - Next phase
