# Phase 2: Case Synthesis and Analysis

Phase 2 analyzes extracted entities to identify institutional rules, map actions to normative structures, and classify ethical transformations.

## Overview

After Phase 1 extraction completes (133+ entities typical), Phase 2 performs six-part analysis:

| Part | Name | Description |
|------|------|-------------|
| A | Provisions | Extract code of ethics provisions referenced |
| B | Questions | Identify ethical questions posed |
| C | Conclusions | Extract board conclusions |
| D | Institutional Rules | Analyze principle tensions and obligation conflicts |
| E | Action-Rule Mapping | Map actions to three-rule framework |
| F | Transformation | Classify ethical transformation pattern |

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

## Part B: Ethical Questions

Extracts the specific questions addressed by the board:

| Field | Description |
|-------|-------------|
| **Question Number** | Q1, Q2, etc. |
| **Question Text** | Full question as posed |
| **Category** | Type of ethical issue |

### Example Questions

For Case 24-2:
1. Was it ethical for Engineer A to use AI tools without verification expertise?
2. Did Engineer A's conduct violate the competence requirement?

## Part C: Board Conclusions

Extracts the board's determinations:

| Field | Description |
|-------|-------------|
| **Question Reference** | Which question addressed |
| **Conclusion** | Board's determination |
| **Reasoning** | Supporting rationale |

### Example Conclusions

For Case 24-2:
- Q1: Not ethical - Engineer lacked competence to verify AI output
- Q2: Yes, violated NSPE Code II.1.a competence requirement

## Part D: Institutional Rule Analysis

Analyzes the normative structure:

### Principle Tensions

Identifies conflicts between principles:

| Tension | Principle A | Principle B | Resolution |
|---------|-------------|-------------|------------|
| Example | Efficiency | Competence | Competence prevails |
| Example | Client service | Public safety | Safety paramount |

### Obligation Conflicts

Identifies conflicting duties:

| Conflict | Obligation A | Obligation B | Resolution |
|----------|--------------|--------------|------------|
| Example | Timely delivery | Verification | Verification required |
| Example | Client loyalty | Disclosure | Disclosure required |

### Constraint Analysis

Identifies applicable constraints:

- Professional competence boundaries
- Licensing limitations
- Ethical prohibitions

## Part E: Action-Rule Mapping

Maps actions to the three-rule framework:

### Actions Taken

| Action | Obligation Addressed | Status |
|--------|---------------------|--------|
| Used AI without verification | Verify designs | VIOLATED |
| Certified work | Practice competence | VIOLATED |

### Alternatives Not Pursued

| Alternative | Why Not Taken | Would Have Addressed |
|-------------|---------------|---------------------|
| Hire specialist | Cost/time | Competence gap |
| Decline project | Client pressure | Beyond competence |
| Request extension | Deadline | Verification time |

### Three-Rule Framework

Actions mapped to:

1. **Instrumental Rules** - Technical means to achieve goals
2. **Constitutive Rules** - Define professional identity
3. **Regulative Rules** - Govern conduct within role

## Part F: Transformation Classification

Classifies the ethical transformation pattern based on Marchais-Roubelat and Roubelat (2015):

| Type | Description | Pattern |
|------|-------------|---------|
| **Transfer** | Clear shift from one state to another | A → B |
| **Stalemate** | Competing forces prevent resolution | A ↔ B |
| **Oscillation** | Alternating between states | A → B → A |
| **Phase Lag** | Delayed response to change | A ... → B |

### Example Classification

Case 24-2: **Transfer Transformation**
- Pattern: `ai_competence_boundary_violation`
- Initial state: Engineer operating within competence
- Final state: Engineer exceeding competence boundaries
- Trigger: AI technology adoption without verification capability

## Running Analysis

### Automatic Analysis

Click **Run Analysis** to execute all six parts:

1. SSE streaming shows progress
2. Each part completes sequentially
3. Results displayed in tabbed interface

### Review Results

After analysis:

1. Review provisions in Part A tab
2. Check questions in Part B tab
3. Verify conclusions in Part C tab
4. Examine tensions in Part D tab
5. Review action mappings in Part E tab
6. Confirm transformation in Part F tab

### Edit Results

You can edit analysis results:

- Modify tension characterizations
- Adjust action mappings
- Update transformation classification

### Commit Analysis

Click **Save** to persist analysis to database.

## Analysis Storage

Results stored in database tables:

| Table | Contents |
|-------|----------|
| `case_provisions` | Code references |
| `case_questions` | Ethical questions |
| `case_conclusions` | Board conclusions |
| `case_institutional_analysis` | Rules and tensions |
| `case_action_mapping` | Action-rule links |
| `case_transformation` | Transformation data |

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

## Related Guides

- [Phase 1 Extraction](phase1-extraction.md) - Prerequisite extraction
- [Phase 3 Scenario](phase3-scenario.md) - Visualization
- [Transformation Types](../reference/transformation-types.md) - Classification details
