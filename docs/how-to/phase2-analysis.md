# Phase 2: Case Synthesis and Analysis

Phase 2 (Step 4) analyzes extracted entities to identify code provisions, ethical questions and conclusions, classify transformation patterns, and extract decision points for scenario generation.

![Step 4 Synthesis](../assets/images/screenshots/step4-synthesis-content.png)

## Overview

After Phase 1 extraction completes (133+ entities typical), Step 4 performs a Four-Phase Synthesis Pipeline:

| Phase | Name | Description |
|-------|------|-------------|
| Phase 1 | Entity Foundation | Prepare extracted entities for analysis |
| Phase 2 | Analytical Extraction | Extract code provisions, questions, conclusions, and transformation patterns |
| Phase 3 | Decision Point Synthesis | Identify key decision points for scenario generation |
| Phase 4 | Narrative Construction | Build case narrative linking all elements |

Each phase can be run individually or as part of the complete synthesis pipeline.

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

### Four-Phase Pipeline

The Step 4 page shows the synthesis pipeline with four phases:

1. **Phase 1 - Entity Foundation**: Click **Re-run** to prepare entity data
2. **Phase 2 - Analytical Extraction**: Click **Re-run** to extract provisions, questions, conclusions
3. **Phase 3 - Decision Point Synthesis**: Click **Analyze** to extract decision points
4. **Phase 4 - Narrative Construction**: Click **Construct** to build the case narrative, then **View Narrative** to see results

Each phase shows its LLM prompts and responses in expandable sections.

### Quick Actions

The page header provides:

- **Back to Case** - Return to case detail page
- **Re-run Synthesis** - Re-execute all phases
- **Review Results** - View synthesis outputs
- **Clear Step 4** - Remove all synthesis data to start fresh

### Review Results

After analysis, click **Review Step 4 Results** to see:

- Code provisions extracted
- Questions and conclusions with linking
- Decision points and options
- Case narrative

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
