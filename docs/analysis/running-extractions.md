# Running Extractions

Steps 1-3 perform concept extraction using ontology-validated definitions via MCP queries to OntServe. Extractions are dispatched as background tasks from the per-case pipeline dashboard, which polls their status and updates each substep card as work completes. This guide covers running the extraction pipeline on cases.

!!! note "Login Required"
    Running extractions requires authentication. Unauthenticated users can view completed extractions but cannot run new ones.

## Overview

Steps 1-3 extract the nine base concepts. Steps 1-2 extract separately from the Facts and Discussion sections. Step 3 performs a unified extraction from the full case text using LangGraph orchestration.

| Step | Name | Concepts | Extraction Mode |
|------|------|----------|----------------|
| Step 1 | Contextual Framework | Roles, States, Resources | Pass 1 (Facts), Pass 2 (Discussion) |
| Step 2 | Normative Requirements | Principles, Obligations, Constraints, Capabilities | Pass 1 (Facts), Pass 2 (Discussion) |
| Step 3 | Temporal Dynamics | Actions, Events, causal chains, temporal relations | Unified (full case text) |

After Steps 1-3, the pipeline continues with Reconcile (entity deduplication), OntServe commit, Step 4 (whole-case synthesis, seven substeps), and a second OntServe commit. Step 5 presents the fully analyzed case as an interactive scenario; it is read-only and does not require authentication. See [Pipeline Terminology](../concepts/terminology.md) for definitions and [Interactive Scenario](../viewing/interactive-scenario.md) for Step 5.

## Starting Extraction

### Access the Pipeline

Navigate to any case detail page and click the **Pipeline** button in the top action bar, or access the per-case pipeline dashboard directly at `/cases/<id>/pipeline`.

The dashboard presents the pipeline as a sequence of substep cards. Each available substep offers a **Run** button; **Run All** dispatches the remaining substeps in order. Substeps have prerequisites and unlock in sequence; completed substeps display as green. Extraction prompts come from the shared prompt template system: the templates behind each substep are viewable by anyone through the Prompt Viewer and editable by administrators through the [Prompt Editor](../admin-guide/prompt-editor.md).

## Step 1: Contextual Framework

Step 1 runs as two substeps, one per case section: Pass 1 extracts from the Facts section and Pass 2 from the Discussion section. Each pass extracts all three concept types together (Roles first, then States and Resources).

Expected entity counts:

| Concept | Description | Typical Count |
|---------|-------------|---------------|
| **Roles** | Professional positions | 3-6 entities |
| **States** | Situational conditions | 10-20 entities |
| **Resources** | Referenced standards | 15-30 entities |

## Step 2: Normative Requirements

Step 2 likewise runs as a Facts pass and a Discussion pass. Each pass extracts the four normative concept types (Principles first, then Obligations, then Constraints and Capabilities).

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

Step 3 uses LangGraph orchestration to extract from the full case text (Facts and Discussion combined) in a single unified pass, unlike Steps 1-2 which use separate passes per section. It runs as one substep on the dashboard.

The extraction produces five output types:

| Output | Description | Typical Count |
|--------|-------------|---------------|
| **Actions** | Professional responses and decisions | 5-12 entities |
| **Events** | Precipitating occurrences | 3-8 entities |
| **Causal Chains** | NESS test causal analysis | 3-6 chains |
| **Allen Relations** | OWL-Time temporal ordering | 10-20 relations |
| **Timeline** | Chronological event/action sequence | 1 timeline |

## Reconcile

After Steps 1-3, entity deduplication merges overlapping entities across sections and passes. Reconcile is its own substep card on the pipeline dashboard and runs automatically in batch mode.

## Step 4: Whole-Case Synthesis

Step 4 analyzes the full case text together with entities from Steps 1-3 and appears on the dashboard as seven individually dispatchable substeps (Code Provisions, Precedent Cases, Questions and Conclusions, Transformation, Rich Analysis, Decision Points, Narrative). See [Pipeline Terminology](../concepts/terminology.md) for phase details.

## Extraction Options

### Re-run Extraction

The entity review pages include a **Re-run Extraction** button to clear existing entities and run again if results need improvement.

### Progress Tracking

The dashboard polls substep status while tasks run, updating each card with progress, entity counts, and completion status.

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
