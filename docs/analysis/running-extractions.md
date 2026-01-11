# Running Extractions

Steps 1-3 perform multi-pass concept extraction using ontology-validated definitions via MCP queries to OntServe. This guide covers running the extraction pipeline on cases.

!!! note "Login Required"
    Running extractions requires authentication. Unauthenticated users can view completed extractions but cannot run new ones.

## Overview

Steps 1-3 extract the nine concepts. Each step has two passes:

- **Pass 1 (Facts)** - Extracts from the Facts section
- **Pass 2 (Discussion)** - Extracts from the Discussion section

| Step | Name | Concepts | Passes |
|------|------|----------|--------|
| Step 1 | Contextual Framework | Roles, States, Resources | Pass 1 (Facts), Pass 2 (Discussion) |
| Step 2 | Normative Requirements | Principles, Obligations, Constraints, Capabilities | Pass 1 (Facts), Pass 2 (Discussion) |
| Step 3 | Temporal Dynamics | Actions, Events | Pass 1 (Facts), Pass 2 (Discussion) |

## Starting Extraction

### Access the Pipeline

Navigate to any case detail page. The numbered step buttons appear at the top:

![Case Step Buttons](../assets/images/screenshots/case-step-buttons-content.png)

Steps must be processed in sequence. Completed steps display as green; incomplete steps show the step number. Click any available step to begin extraction.

## Step 1: Contextual Framework

### Pass 1 (Facts)

1. Click the **Step 1** button on the case page
2. The extraction page displays the Facts section text
3. Click individual extraction buttons:
   - **Extract Roles** - Professional positions
   - **Extract States** - Situational conditions
   - **Extract Resources** - Referenced standards

Expected entity counts:

| Concept | Description | Typical Count |
|---------|-------------|---------------|
| **Roles** | Professional positions | 3-6 entities |
| **States** | Situational conditions | 10-20 entities |
| **Resources** | Referenced standards | 15-30 entities |

### Pass 2 (Discussion)

After completing Pass 1 (Facts) extraction:

1. Click **Discussion Section** on the extraction page
2. Extract concepts from the Discussion section using the same buttons
3. Review using the Discussion toggle

## Step 2: Normative Requirements

### Pass 1 (Facts)

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

### Pass 2 (Discussion)

Click **Discussion Section** after completing Pass 1 (Facts) to extract from the Discussion section.

## Step 3: Temporal Dynamics

### Pass 1 (Facts) and Pass 2 (Discussion)

1. Click the **Step 3** button on the case page
2. Extract temporal concepts:

| Concept | Description | Typical Count |
|---------|-------------|---------------|
| **Actions** | Professional responses and decisions | 5-12 entities |
| **Events** | Precipitating occurrences | 3-8 entities |

The temporal extraction also identifies causal relationships and timeline sequences.

## Extraction Options

### Re-run Extraction

The review page includes a **Re-run** button to return to extraction and run again if results need improvement.

### Progress Tracking

During extraction, a progress indicator shows completion status. Entity counts update after each extraction completes.

## Extraction Metrics

After each step:

| Metric | Description |
|--------|-------------|
| **Total Entities** | Count of extracted entities |
| **By Type** | Breakdown by concept type |
| **New Classes** | Entities requiring new ontology classes |
| **Existing Matches** | Entities matching ontology |

## Example: Case 24-2

For NSPE Case 24-2 (AI in Engineering Practice):

**Step 1 Results**:

- Roles (4): Engineer, Client, Employer, State Board
- States (16): Engineer lacks AI competence, Project uses AI tools
- Resources (29): NSPE Code II.1.a, State licensing requirements

**Step 2 Results**:

- Principles (18): Hold paramount public safety, Practice competence
- Obligations (18): Verify AI-generated designs, Disclose limitations
- Constraints (18): Cannot certify beyond competence
- Capabilities (20): Can hire specialists, Can request extensions

**Step 3 Results**:

- Actions (7): Uses AI without verification, Certifies design
- Events (3): Client requests AI design, Board receives complaint

## Troubleshooting

### Extraction Timeout

Long cases may timeout:

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

## Related Pages

- [Entity Review](entity-review.md) - Validating and editing entities
- [Pipeline Automation](pipeline-automation.md) - Batch processing
- [Nine-Component Framework](../concepts/nine-components.md) - Understanding components
