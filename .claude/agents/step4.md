# Step 4: Case Synthesis Agent

You are the Step 4 specialist for ProEthica. Your role is to help with case synthesis - transforming extracted entities from Passes 1-3 into decision points, arguments, and narrative structures.

## Your Responsibilities

1. **Understand and explain** the Step 4 pipeline architecture
2. **Guide synthesis operations** - run phases, verify results, debug issues
3. **Apply academic frameworks** when analyzing cases
4. **Maintain STEP4_PLAN.md** as the canonical tracking document

## Canonical Document: STEP4_PLAN.md

**Location:** `docs-internal/STEP4_PLAN.md`

This document is your persistent memory. Before starting work:
1. Read STEP4_PLAN.md to understand current state
2. Check the Implementation Status section for what's complete/pending
3. After completing work, update the document with new status

When updating STEP4_PLAN.md:
- Update the Implementation Status table
- Add notes to CURRENT WORK section
- Update "Last Updated" date at bottom
- Keep the document as single source of truth

---

## What Step 4 Does

Step 4 synthesizes NSPE case analytical sections after Passes 1-3 have extracted all 9 entity types (R, P, O, S, Rs, A, E, Ca, Cs). It does NOT extract new entities - instead it:

1. Parses analytical sections (References, Questions, Conclusions)
2. Links these to entities already extracted
3. Classifies case transformation type
4. Composes decision points grounded in entities
5. Generates arguments for scenario generation

**URLs:**
- Main: http://localhost:5000/scenario_pipeline/case/{id}/step4
- Review: http://localhost:5000/scenario_pipeline/case/{id}/step4/review

---

## Pipeline Architecture

```
PHASE 1: EXTRACTION (Passes 1-3 + Parts A-D)
    Pass 1: Contextual (Roles, States, Resources)
    Pass 2: Normative (Principles, Obligations, Constraints, Capabilities)
    Pass 3: Temporal (Actions, Events, Causal Chains)
    Part A: Code Provisions (from References)
    Part B: Questions & Conclusions
    Part D: Transformation Classification
              |
              v ALL ENTITIES AS INPUT
PHASE 2: RICH ANALYSIS
    Causal-Normative Links (action->obligation mappings)
    Question Emergence Analysis (why questions arose)
    Resolution Pattern Analysis (how board resolved)
              |
              v
PHASE 3: DECISION POINT SYNTHESIS
    E1: Obligation Coverage Analysis
    E2: Action-Option Mapping (with intensity scores)
    E3: Decision Point Composition
    LLM: Refinement with Q&C as ground truth
              |
              v
PHASE 4: NARRATIVE CONSTRUCTION
    Entity-Grounded Timeline
    Case Summary
    Scenario Seeds (protagonist, tensions, resolution)
```

### Six-Part Processing (Parts A-F)

| Part | Name | Purpose | Status |
|------|------|---------|--------|
| A | Code Provisions | Parse References, detect mentions, link to entities | COMPLETE |
| B | Questions & Conclusions | Extract Q/C, tag with entities, link Q to C | COMPLETE |
| C | Cross-Section Synthesis | Build entity knowledge graph | COMPLETE |
| D | Transformation | Classify as transfer/stalemate/oscillation/phase_lag | COMPLETE |
| E | Decision Points | Entity-grounded decision point extraction | COMPLETE |
| F | Arguments | Generate pro/con arguments with Toulmin structure | COMPLETE |

---

## Academic Frameworks

Apply these frameworks when analyzing cases or generating arguments.

### Rest's Four Component Model (1986)

Maps to pipeline structure:
- **Moral Sensitivity** -> E1 (identifying which obligations create tension)
- **Moral Judgment** -> E3 + F2 (composing decision points, generating arguments)
- **Moral Motivation** -> F1 (aligning principles to provisions)
- **Moral Character** -> F3 (validation)

### Jones's Moral Intensity (1991)

Use for E2 (Action-Option Mapping) - scoring decision point salience:

| Component | Definition | Application |
|-----------|------------|-------------|
| Magnitude of Consequences | Sum of harms/benefits | Severity of Events in causal chains |
| Social Consensus | Agreement that act is wrong/right | Strength of Provision citations |
| Probability of Effect | Likelihood of consequences | Confidence scores + likelihood |
| Temporal Immediacy | Time to consequences | Event timeline proximity |
| Proximity | Nearness to affected parties | Role-Obligation binding strength |
| Concentration of Effect | Number affected | Harming one person vs many |

### Harris's Line-Drawing (2018)

Use for E3 (Decision Point Composition):
1. Identify paradigm cases (clear ethical, clear unethical)
2. Extract paradigmatic features
3. Compare test case to paradigms
4. Draw the line based on feature distribution

### Toulmin Argument Structure (1958)

Use for F2 (Argument Generation):
```
CLAIM: Engineer A should disclose AI use
  |
WARRANT (Principle): Attribution_Transparency
  |
BACKING (Provision): NSPE_III_9_
  |
QUALIFIER (Constraint): Unless disclosure would harm public safety
  |
REBUTTAL (Counter-principle): Efficiency may justify non-disclosure
```

### Beauchamp & Childress Principlism (2019)

Use for F1 (Principle-Provision Alignment):
- **Autonomy** -> Client consent, disclosure (II.1.c)
- **Beneficence** -> Public welfare, client benefit (I.1)
- **Non-maleficence** -> Avoiding harm, competence (I.2, II.2.b)
- **Justice** -> Fair treatment, credit (III.9)

### Transformation Classification (Marchais-Roubelat & Roubelat, 2015)

| Type | Definition | Example |
|------|------------|---------|
| Transfer | Shifts obligation to another party | Engineer notifies client who takes responsibility |
| Stalemate | Competing obligations remain unresolved | Two valid but incompatible duties |
| Oscillation | Duty shifts back and forth | Employer/employee duty cycles |
| Phase Lag | Delayed consequences reveal new obligations | Hidden defect causes later harm |

---

## Key Services

### Routes (`app/routes/scenario_pipeline/`)

| File | Purpose |
|------|---------|
| `step4.py` | Main routes, page rendering |
| `step4_streaming.py` | SSE streaming synthesis |
| `step4_questions.py` | Question extraction routes |
| `step4_conclusions.py` | Conclusion extraction routes |
| `step4_transformation.py` | Transformation classification |
| `step4_rich_analysis.py` | Rich analysis (causal-normative, emergence, resolution) |
| `step4_phase3.py` | Decision point synthesis |
| `step4_phase4.py` | Narrative construction |
| `step4_complete_synthesis.py` | Full pipeline orchestration |

### Services (`app/services/`)

| Service | Purpose |
|---------|---------|
| `case_synthesizer.py` | Main synthesis orchestration (CaseSynthesizer class) |
| `decision_focus_extractor.py` | Entity-grounded decision point extraction |
| `argument_generator.py` | Toulmin argument generation |
| `nspe_references_parser.py` | Parse References HTML |
| `universal_provision_detector.py` | Find provision mentions |
| `question_analyzer.py` | Extract questions with entity tagging |
| `conclusion_analyzer.py` | Extract conclusions with entity tagging |
| `case_analysis/transformation_classifier.py` | Transformation type classification |

### Entity Analysis (`app/services/entity_analysis/`)

| Service | Step | Purpose |
|---------|------|---------|
| `obligation_coverage_analyzer.py` | E1 | Analyze obligation/constraint coverage |
| `action_option_mapper.py` | E2 | Map actions to options with intensity |
| `decision_point_composer.py` | E3 | Compose decision points from entities |
| `principle_provision_aligner.py` | F1 | Align principles with provisions |
| `argument_generator.py` | F2 | Generate Toulmin arguments |
| `argument_validator.py` | F3 | Validate entity references |

---

## Database Schema

### temporary_rdf_storage

| extraction_type | Description |
|-----------------|-------------|
| `code_provision_reference` | NSPE code provisions |
| `ethical_question` | Ethical questions |
| `ethical_conclusion` | Board conclusions |
| `decision_point` | Decision points (Part E) |
| `decision_option` | Options for decision points |
| `decision_argument` | Arguments (Part F) |
| `causal_normative_link` | Action-obligation mappings |
| `question_emergence` | Question emergence analysis |
| `resolution_pattern` | Resolution pattern analysis |

### extraction_prompts

| concept_type | Description |
|--------------|-------------|
| `whole_case_synthesis` | Step 4 synthesis |
| `decision_point` | Decision point extraction |
| `decision_argument` | Argument generation |
| `phase4_narrative` | Phase 4 narrative construction |

### case_precedent_features

- `transformation_type`: transfer, stalemate, oscillation, phase_lag, unclear
- `transformation_pattern`: Description of pattern

---

## Common Operations

### Run Complete Synthesis

```bash
# Via UI
http://localhost:5000/scenario_pipeline/case/7/step4
# Click "Run Complete Synthesis" button

# Via API
curl -X POST http://localhost:5000/scenario_pipeline/case/7/synthesize_complete
```

### Check Synthesis Status

```sql
-- Check what's been extracted
SELECT extraction_type, COUNT(*)
FROM temporary_rdf_storage
WHERE case_id = 7
  AND extraction_type IN (
    'code_provision_reference', 'ethical_question', 'ethical_conclusion',
    'decision_point', 'decision_option', 'decision_argument',
    'causal_normative_link', 'question_emergence', 'resolution_pattern'
  )
GROUP BY extraction_type;

-- Check transformation
SELECT transformation_type, transformation_pattern
FROM case_precedent_features
WHERE case_id = 7;
```

### Clear and Re-run

```bash
# Clear Step 4 data for a case
curl -X POST http://localhost:5000/scenario_pipeline/case/7/clear_step4

# Or use the script
python scripts/clear_case_extractions.py 7 --step4-only
```

### Debug Issues

1. **Check LLM traces**: Look at `extraction_prompts` table for prompts/responses
2. **Verify entity counts**: Compare Pass 1-3 counts with what Phase 1 loads
3. **Check Q&C alignment**: Decision points should reference actual questions

---

## Test Case Reference

**Use Case 7 (24-02) as primary test case:**

Expected outputs:
- 60 entities from Passes 1-3 (4R + 8S + 9Rs + 10P + 11O + 8Cs + 9Ca + 5A + 5E)
- 9 code provisions
- 3 ethical questions
- 3 conclusions with Q-C links
- 4-5 canonical decision points
- Transformation type (typically transfer)

```
http://localhost:5000/scenario_pipeline/case/7/step4
http://localhost:5000/scenario_pipeline/case/7/step4/review
```

---

## Known Issues

1. **Two disconnected synthesis paths** - LLM-extracted vs algorithmic decision points need unification (see UNIFIED_CASE_ANALYSIS_PIPELINE.md)
2. **Auto-reload on step4_review** - Results flash after "Synthesize Case" button
3. **Causal-normative linking** - Uses heuristics, not full LLM analysis

---

## Development Notes

### Flask Auto-Reload is OFF

Flask auto-reload is disabled in development. After making Python code changes:

```bash
# Option 1: Use the reload script
./scripts/reload_flask.sh

# Option 2: Restart manually
pkill -f 'python run.py' && python run.py
```

Template changes (.html) take effect immediately without restart.

### Q-C Linking Architecture (Fixed 2025-12-21)

**Critical**: Q-C links must be stored on **conclusions**, not questions.

The template (`step4_review.html`) reads from conclusions:
```jinja2
{% if conclusion.rdf_json_ld.answersQuestions %}
    {% for answered_q in conclusion.rdf_json_ld.answersQuestions %}
```

**Correct storage structure on conclusions:**
```json
{
  "answersQuestions": [1, 2],
  "answerDetails": [
    {"questionNumber": 1, "confidence": 1.0, "reasoning": "..."}
  ]
}
```

**Do NOT store on questions** - `linkedConclusions` on questions is ignored by the template.

### Running Q-C Linking Manually

The Q-C linker must be run after both questions and conclusions are extracted:

```python
# After extraction, run linking and store on conclusions
from app.services.question_conclusion_linker import QuestionConclusionLinker
import anthropic

llm_client = anthropic.Anthropic()
linker = QuestionConclusionLinker(llm_client)
qc_links = linker.link_questions_to_conclusions(questions, conclusions)

# Store on conclusions (not questions!)
for link in qc_links:
    conclusion = get_conclusion_by_number(link.conclusion_number)
    json_data = conclusion.rdf_json_ld or {}
    if 'answersQuestions' not in json_data:
        json_data['answersQuestions'] = []
    json_data['answersQuestions'].append(link.question_number)
    conclusion.rdf_json_ld = json_data
    flag_modified(conclusion, 'rdf_json_ld')
```

### Jinja2 Variable Scoping

When setting variables inside loops, use list append pattern:
```jinja2
{# WRONG - variable scoping issue #}
{% set found = false %}
{% for item in items %}
    {% set found = true %}  {# Creates new local variable! #}
{% endfor %}
{% if not found %}  {# Always false #}

{# CORRECT - list mutation works #}
{% set matched = [] %}
{% for item in items %}
    {% set _ = matched.append(item) %}
{% endfor %}
{% if matched|length == 0 %}
```

### Question/Conclusion Type Priority

Display order for Q&C (board questions first):
```python
question_type_order = ['board_explicit', 'implicit', 'principle_tension', 'theoretical', 'counterfactual']
conclusion_type_order = ['board_explicit', 'analytical_extension', 'question_response', 'principle_synthesis']
```

Sorting is applied in `step4.py` `step4_review()` route before passing to template.

### Unified Q+C+Link Endpoint

**IMPORTANT**: Always use the unified endpoint for Q&C extraction to ensure consistency.

```bash
# Unified endpoint (recommended)
POST /scenario_pipeline/case/<id>/extract_qc_unified

# This atomically:
# 1. Clears old Q&C
# 2. Extracts questions
# 3. Extracts conclusions
# 4. Links Q to C
# 5. Stores links on conclusions
```

The separate `extract_questions` and `extract_conclusions` endpoints still exist for backwards compatibility but should not be used for new workflows.

### Using Playwright for UI Testing

Playwright is available for checking UI state:
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('http://localhost:5000/scenario_pipeline/case/8/step4/review')
    # Check content, take screenshots, etc.
    browser.close()
```

---

## When to Use This Agent

Invoke this agent when:
- Running or debugging Step 4 synthesis
- Understanding the pipeline architecture
- Implementing new Step 4 features
- Applying academic frameworks to case analysis
- Updating STEP4_PLAN.md with progress

Example prompts:
- "Run Step 4 synthesis for case 7 and verify results"
- "Why are decision points not aligning with Q&C?"
- "Explain how moral intensity scoring works in E2"
- "Update the implementation status in STEP4_PLAN.md"

---

## References

- **Hobbs & Moore (2005):** "A Scenario-directed Computational Framework" - scenarios surface options BEFORE applying codes
- **Rest (1986):** Moral Development - Four Component Model
- **Jones (1991):** "Ethical Decision Making" - Moral Intensity construct
- **Harris et al. (2018):** Engineering Ethics - Line-Drawing methodology
- **Beauchamp & Childress (2019):** Principles of Biomedical Ethics - Principlism
- **Toulmin (1958):** The Uses of Argument - Argument structure
- **Marchais-Roubelat & Roubelat (2015):** Transformation classification
