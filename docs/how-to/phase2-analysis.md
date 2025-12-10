# Phase 2: Case Synthesis and Analysis

Phase 2 analyzes extracted entities to identify code provisions, ethical questions and conclusions, classify transformation patterns, and extract decision points for scenario generation.

## Overview

After Phase 1 extraction completes (133+ entities typical), Phase 2 performs six-part analysis:

| Part | Name | Description | Status |
|------|------|-------------|--------|
| A | Code Provisions | Parse References section, detect mentions, link to entities | Complete |
| B | Questions & Conclusions | Extract Q/C, tag with entities, link Q to C | Complete |
| C | Cross-Section Synthesis | Build entity knowledge graph | Complete |
| D | Transformation | Classify as transfer/stalemate/oscillation/phase_lag | Complete |
| E | Decision Point Extraction | Identify key decision points for scenario generation | Complete |
| F | Pros/Cons Arguments | Generate arguments for/against each decision option | Planned |

## Starting Analysis

### Prerequisites

Before Step 4:

- Complete Phase 1 extraction (Steps 1-3)
- Review and commit entities
- All pipeline prerequisites met (lock icons cleared)

### Access Step 4

1. Navigate to Scenario Pipeline (`/scenario_pipeline/<case_id>`)
2. Click **Step 4** in the sidebar
3. Review analysis interface

## Part A: Code Provisions

The system extracts code of ethics provisions referenced in the case:

| Field | Description |
|-------|-------------|
| **Code Reference** | Citation (e.g., "NSPE Code II.1.a") |
| **Section Text** | Provision language |
| **Relevance** | How provision applies to case |

### Example Provisions

For Case 24-2:
- NSPE Code II.1.a - Competence requirement
- NSPE Code II.1.b - Practice only in areas of competence
- NSPE Code III.2.a - Faithful agent responsibility

## Part B: Questions & Conclusions

### Ethical Questions

Extracts the specific questions addressed by the board:

| Field | Description |
|-------|-------------|
| **Question Number** | Q1, Q2, etc. |
| **Question Text** | Full question as posed |
| **Entity Tags** | Referenced entities from extraction |

### Board Conclusions

Extracts the board's determinations:

| Field | Description |
|-------|-------------|
| **Question Reference** | Which question addressed |
| **Conclusion** | Board's determination |
| **Reasoning** | Supporting rationale |

### Example

For Case 24-2:
- Q1: Was it ethical for Engineer A to use AI tools without verification expertise?
- C1: Not ethical - Engineer lacked competence to verify AI output

## Part C: Cross-Section Synthesis

Builds an entity knowledge graph connecting extracted entities:

- Links entities across case sections
- Identifies principle tensions
- Maps obligation conflicts
- Uses heuristics for causal-normative linking

Visualized via Cytoscape in the Review page.

## Part D: Transformation Classification

Classifies the ethical transformation pattern based on Marchais-Roubelat and Roubelat (2015):

| Type | Description | Pattern |
|------|-------------|---------|
| **Transfer** | Clear shift from one state to another | A to B |
| **Stalemate** | Competing forces prevent resolution | A vs B |
| **Oscillation** | Alternating between states | A to B to A |
| **Phase Lag** | Delayed response to change | A ... to B |

### Example Classification

Case 24-2: **Transfer Transformation**
- Pattern: `ai_competence_boundary_violation`
- Initial state: Engineer operating within competence
- Final state: Engineer exceeding competence boundaries
- Trigger: AI technology adoption without verification capability

## Part E: Decision Point Extraction

Identifies key decision points where ethical choices must be made. These become the decision points in Step 5 scenarios.

### What Decision Points Capture

| Field | Description |
|-------|-------------|
| **Focus Description** | Brief description of the decision context |
| **Decision Question** | The ethical question being decided |
| **Involved Roles** | Professional roles involved in the decision |
| **Applicable Provisions** | NSPE Code provisions that apply |
| **Options** | Available choices at this decision point |
| **Board Resolution** | What the board determined |
| **Board Reasoning** | Why the board reached this conclusion |

### Example Decision Points

For Case 7 (Case 24-2):

**Decision Point 1**: AI Tool Usage Decision
- Question: Should Engineer A use AI-generated outputs in design work?
- Roles: Engineer A, AI System
- Provisions: NSPE II.1.a, II.2.b
- Options:
  - Use AI outputs with independent verification (Board Choice)
  - Use AI outputs without verification
  - Decline to use AI tools
- Resolution: Engineers must verify AI outputs through independent means

**Decision Point 2**: Disclosure of AI Use
- Question: Must Engineer A disclose AI tool usage to client?
- Roles: Engineer A, Client
- Provisions: NSPE II.1.c, III.2.a
- Options:
  - Full disclosure of AI use and limitations (Board Choice)
  - Limited disclosure
  - No disclosure

### Storage Pattern

Decision points use the standard RDF storage pattern:

- **Entities**: `temporary_rdf_storage` with `extraction_type='decision_point'` and `'decision_option'`
- **Provenance**: `extraction_prompts` with `concept_type='decision_point'`
- **Ontology classes**: `DecisionPoint`, `DecisionOption` in proethica-intermediate.ttl

### Commit to OntServe

After extraction, click **Commit to OntServe** to persist decision points to the ontology.

## Part F: Pros/Cons Arguments (Planned)

For each decision option, generate balanced pro/con arguments with precedent linking. This will:

- Cite specific NSPE Code provisions
- Reference similar precedent cases
- Identify principle tensions
- Note public welfare implications

This feature is planned for implementation.

## Running Analysis

### Automatic Analysis

Click **Run Synthesis** to execute Parts A-D:

1. SSE streaming shows progress
2. Each part completes sequentially
3. Results displayed in tabbed interface

### Decision Point Extraction

Decision points are extracted separately:

1. Go to **Step 4 Review** page
2. Click **Decision Points** tab
3. Click **Extract Decision Points** button
4. Review extracted decision points and options
5. Click **Commit to OntServe** to persist

### Review Results

After analysis:

1. **Provisions** tab - Code references found
2. **Questions & Conclusions** tab - Q/C with linking
3. **Entity Graph** tab - Cytoscape visualization
4. **Raw Data** tab - JSON view
5. **Decision Points** tab - Extracted decision points

### Edit Results

You can edit analysis results:

- Modify transformation classification
- Adjust Q-C links
- Review entity graph relationships

### Commit Analysis

- Click **Save** to persist synthesis results
- Click **Commit to OntServe** in Decision Points tab for decision point entities

## Analysis Storage

Results stored using RDF storage pattern:

| extraction_type | entity_type | Description |
|-----------------|-------------|-------------|
| `code_provision_reference` | resources | NSPE code provisions |
| `ethical_question` | EthicalQuestion | Questions posed to board |
| `ethical_conclusion` | BoardConclusion | Board's conclusions |
| `decision_point` | DecisionPoint | Decision points (Part E) |
| `decision_option` | DecisionOption | Options at decision points |

Transformation data stored in `case_precedent_features` table.

## LLM Traces

Each analysis part captures:

- Prompt text sent to LLM
- Raw LLM response
- Parsed structured output
- Timestamp and model used

Access traces via the analysis interface for transparency.

## Troubleshooting

### Analysis Incomplete

If parts fail:

1. Check extraction completeness (Phase 1)
2. Verify entity commit status
3. Retry individual parts

### Transformation Unclear

If classification uncertain:

1. Review case narrative
2. Check action sequence
3. Consider manual classification

### Missing Code References

If provisions not detected:

1. Check case text includes citations
2. Verify standard citation format
3. Add manually if needed

### Decision Points Not Extracting

If extraction fails:

1. Ensure Phase 1 extraction complete
2. Check LLM API connection
3. Review extraction_prompts for errors

## Related Guides

- [Phase 1 Extraction](phase1-extraction.md) - Prerequisite extraction
- [Phase 3 Scenario](phase3-scenario.md) - Visualization
- [Transformation Types](../reference/transformation-types.md) - Classification details
- [Ontology Integration](../reference/ontology-integration.md) - OntServe connection
