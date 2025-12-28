# ProEthica Validation Framework

## Overview

This document analyzes the existing validation infrastructure in ProEthica and provides a framework for conducting validation studies with two evaluator populations: engineering students (engineering ethics domain) and education students (new education domain).

## Current Infrastructure Analysis

### Database Schema

Three experiment-related tables exist in the `ai_ethical_dm` database:

| Table | Purpose | Current Records |
|-------|---------|-----------------|
| `experiment_runs` | Stores experiment configurations and status | 0 |
| `experiment_predictions` | Stores baseline and ProEthica predictions | 0 |
| `experiment_evaluations` | Stores evaluator ratings and feedback | 0 |

**Schema Details:**

```
experiment_runs:
  - id, name, description
  - config (JSON): selected_cases, use_ontology, target
  - status: created, running, completed, failed
  - created_at, updated_at, created_by

experiment_predictions:
  - id, experiment_run_id, document_id
  - condition: 'baseline' or 'proethica'
  - target: 'full', 'conclusion', 'discussion'
  - prediction_text, reasoning, prompt
  - meta_info (JSON): ontology_entities, similar_cases, validation_metrics

experiment_evaluations:
  - id, experiment_run_id, prediction_id, evaluator_id
  - Core metrics (0-10 scale): reasoning_quality, persuasiveness, coherence,
    support_quality, preference_score, alignment_score
  - Binary: accuracy, agreement
  - comments, meta_info
```

### Existing Routes and Templates

**Routes** ([app/routes/experiment.py](app/routes/experiment.py)):

| Route | Purpose |
|-------|---------|
| `/experiment/` | Dashboard with case list and statistics |
| `/experiment/quick_predict/<case_id>` | Generate single-case prediction |
| `/experiment/case_comparison/<case_id>` | Compare prediction vs original |
| `/experiment/double_blind/<case_id>` | Double-blind evaluation interface |
| `/experiment/conclusion_setup` | Create batch experiment |
| `/experiment/<id>/cases` | Select cases for experiment |
| `/experiment/<id>/run_conclusion_predictions` | Execute predictions |
| `/experiment/<id>/results` | View experiment results |
| `/experiment/evaluate_prediction/<prediction_id>` | Submit evaluation |
| `/experiment/<id>/export` | Export results as JSON |

**Templates** (13 templates in [app/templates/experiment/](app/templates/experiment/)):

- `index.html` - Main dashboard
- `double_blind_comparison.html` - Randomized A/B evaluation interface
- `evaluate_prediction.html` - Metric scoring form
- `case_comparison.html` - Side-by-side comparison
- `conclusion_setup.html`, `conclusion_run.html`, `conclusion_results.html` - Experiment workflow
- Others: cases.html, results.html, setup.html, run.html, case_results.html, conclusion_comparison.html

### Prediction Service

[app/services/experiment/prediction_service.py](app/services/experiment/prediction_service.py) provides:

1. **Baseline predictions**: LLM analysis without ontology enhancement
2. **ProEthica predictions**: LLM analysis with:
   - Ontology entity extraction per section
   - Similar case retrieval (precedent matching)
   - Structured prompts with NSPE Code references

**Key Methods:**
- `generate_conclusion_prediction(document_id, use_ontology)` - Core prediction generation
- `get_document_sections(document_id, leave_out_conclusion)` - Retrieve case sections
- `get_section_ontology_entities(document_id, sections)` - Fetch related ontology concepts
- `_validate_conclusion(conclusion, ontology_entities)` - Basic entity mention validation

### Double-Blind Evaluation Interface

The existing double-blind interface ([double_blind_comparison.html](app/templates/experiment/double_blind_comparison.html)) includes:

- Randomized system assignment (System A vs System B)
- Case context display (Facts, Issue, Discussion)
- Four evaluation criteria per system:
  - Reasoning Quality (1-7 scale)
  - Ethical Grounding (1-7 scale)
  - Practical Applicability (1-7 scale)
  - Overall Coherence (1-7 scale)
- Overall preference selection (System A / No Preference / System B)
- Comments field
- Participant ID hashing for anonymization
- Progress tracking

---

## Academic Foundation (from Chapter 4)

The original validation framework was designed for legal professionals. Key elements to adapt:

### Original Four-Metric Framework

| Metric | Description | Scale |
|--------|-------------|-------|
| **PAQ** (Precedent Application Quality) | Identification and application of relevant prior cases | 0-100 |
| **CSA** (Component Structure Assessment) | Proper identification of D = (R, P, O, S, Rs, A, E, Ca, Cs) components | 0-100 |
| **RTI** (Reasoning Transparency Index) | Clarity of argumentative steps and fact-principle-conclusion traceability | 0-100 |
| **PRA** (Professional Reasoning Alignment) | Conformance to professional analytical standards | 0-100 |

### Success Criteria from Original Framework

- Mean scores above 60 across all metrics
- Evaluator preference for ProEthica over baseline in majority of cases
- Inter-rater reliability exceeding alpha = 0.60 (Krippendorff's alpha)

### Study Protocol Elements

1. **Orientation** (1 hour): Domain primer + 2 practice cases
2. **Individual Evaluation** (2-3 hours): Double-blind comparison via web interface
3. **Reflection and Feedback** (1 hour): Structured questions on overall impressions
4. Total time: 4-5 hours per participant

---

## Proposed Validation Framework for New Evaluator Populations

### Population 1: Engineering School (Engineering Ethics)

**Evaluators**: Masters students in engineering programs

**Case Domain**: NSPE Board of Ethical Review cases (existing case base)

**Rationale**: Engineering students have:
- Domain knowledge of engineering practice contexts
- Familiarity with professional engineering codes (NSPE, discipline-specific)
- Understanding of technical decision-making constraints
- Perspective as future practitioners

**Adaptation Requirements**:
- Update orientation to assume engineering context knowledge
- Focus evaluation criteria on technical accuracy and professional applicability
- Include questions about whether reasoning aligns with their professional training

### Population 2: School of Education (Education Ethics - NEW DOMAIN)

**Evaluators**: Masters students in education programs

**Case Domain**: NEW - Education ethics cases needed

**Rationale**: Education students have:
- Domain knowledge of educational practice contexts
- Familiarity with education professional codes (NEA, state codes)
- Understanding of student welfare, academic integrity, professional boundaries
- Perspective as current or future educators

**Adaptation Requirements**:
- Develop education ethics ontology in OntServe
- Import education ethics cases (sources below)
- Create education-specific principle and obligation hierarchies
- Modify prompts for education context

### Potential Education Ethics Case Sources

1. **NEA Code of Ethics Cases** - National Education Association
2. **AASA Ethics Cases** - American Association of School Administrators
3. **NAEYC Ethics Cases** - Early childhood education
4. **State Department of Education** - Disciplinary case summaries
5. **Journal of Cases in Educational Leadership** - Academic case studies
6. **Chronicle of Higher Education** - Higher ed ethics cases

---

## Implementation Checklist

### Phase 1: Infrastructure Verification

- [ ] Verify experiment tables are migrated in production
- [ ] Test prediction generation for existing cases
- [ ] Validate double-blind interface randomization
- [ ] Test evaluation submission and storage
- [ ] Verify JSON export functionality

### Phase 2: Metric Refinement

Current metrics in database:
```
reasoning_quality, persuasiveness, coherence, support_quality,
preference_score, alignment_score, accuracy, agreement
```

Proposed alignment with Chapter 4 metrics:

| Chapter 4 Metric | Current Mapping | Notes |
|------------------|-----------------|-------|
| PAQ | preference_score + similar_cases in meta_info | Consider explicit precedent rating |
| CSA | (not directly captured) | Add component extraction accuracy |
| RTI | reasoning_quality + coherence | Combine or keep separate |
| PRA | alignment_score | Rename for clarity |

**Recommended Additions:**
- `component_accuracy` - Rate completeness of extracted components (R, P, O, S, Rs, A, E, Ca, Cs)
- `precedent_relevance` - Rate quality of precedent case citations
- `code_provision_accuracy` - Rate correctness of ethics code references
- `domain_appropriateness` - Rate fit with domain-specific professional norms

### Phase 3: Study Protocol Updates

#### For Engineering Ethics (Engineering School)

```
Orientation (45 min):
- ProEthica system overview
- 9-component framework explanation
- 2 practice cases with guided evaluation
- Q&A session

Evaluation Session (2 hours):
- 10-15 cases per evaluator
- Double-blind baseline vs ProEthica
- Metrics: RTI, PRA, Component Accuracy, Precedent Relevance
- Comments per case

Debrief (30 min):
- Overall impressions questionnaire
- Professional utility assessment
- Suggestions for improvement
```

#### For Education Ethics (School of Education)

```
Orientation (60 min):
- ProEthica system overview
- 9-component framework with education examples
- Education ethics code overview (NEA, etc.)
- 2 practice cases with guided evaluation
- Q&A session

Evaluation Session (2 hours):
- 10-15 cases per evaluator
- Double-blind baseline vs ProEthica
- Same metrics as engineering
- Comments per case

Debrief (30 min):
- Overall impressions questionnaire
- Education domain fit assessment
- Cross-domain applicability feedback
```

### Phase 4: Education Domain Development

To support education ethics validation:

1. **Ontology Extension**
   - Create education ethics ontology in OntServe
   - Define role hierarchy (Teacher, Administrator, Counselor, etc.)
   - Map NEA Code principles to ontology
   - Define education-specific obligations, constraints, capabilities

2. **Case Import**
   - Develop case import scripts for education cases
   - Parse case structure (facts, issue, analysis, conclusion)
   - Generate embeddings for similarity matching
   - Validate extraction pipeline on education cases

3. **Prompt Adaptation**
   - Create education-specific extraction prompts
   - Update conclusion prediction prompts for education context
   - Add education precedent matching

---

## Technical Implementation Notes

### Running a Validation Study

```python
# Create experiment
POST /experiment/conclusion_prediction_setup
{
    "name": "Engineering Validation Study Spring 2026",
    "description": "Masters students evaluation of ProEthica",
    "use_ontology": true
}

# Select cases
POST /experiment/<id>/cases
{
    "selected_cases": [7, 8, 60, 61, 62, ...]  # Case IDs
}

# Generate predictions (runs baseline + ProEthica)
POST /experiment/<id>/run_conclusion_predictions

# Distribute evaluation links to participants
# /experiment/double_blind/<case_id>

# Export results
GET /experiment/<id>/export
```

### Participant Management

Current system uses IP-based participant tracking (`evaluator_id = request.remote_addr`).

**Recommended Enhancement:**
- Add participant registration with anonymized ID
- Track evaluator metadata (program, year, experience level)
- Enable session persistence for multi-session evaluation

### Data Export Format

```json
{
    "experiment": {
        "id": 1,
        "name": "Validation Study",
        "config": {"selected_cases": [...]},
        "status": "completed"
    },
    "predictions": [
        {
            "document_id": 7,
            "condition": "proethica",
            "prediction_text": "...",
            "meta_info": {
                "ontology_entities": {...},
                "similar_cases": [...],
                "validation_metrics": {...}
            }
        }
    ],
    "evaluations": [
        {
            "evaluator_id": "P1234",
            "reasoning_quality": 7.5,
            "coherence": 8.0,
            ...
        }
    ]
}
```

---

## Analysis Plan

### Quantitative Analysis

1. **Descriptive Statistics**
   - Mean scores per metric per condition (baseline vs ProEthica)
   - Standard deviation and confidence intervals
   - Distribution visualization

2. **Comparative Analysis**
   - Paired t-tests or Wilcoxon signed-rank for baseline vs ProEthica
   - Effect size calculation (Cohen's d)
   - Preference proportion with binomial test

3. **Reliability Analysis**
   - Krippendorff's alpha for inter-rater reliability
   - Intraclass correlation coefficient (ICC)

4. **Cross-Domain Comparison**
   - Compare engineering vs education evaluator patterns
   - Identify domain-specific factors affecting evaluation

### Qualitative Analysis

1. **Comment Coding**
   - Thematic analysis of evaluator comments
   - Identify strengths and weaknesses patterns
   - Extract improvement suggestions

2. **Domain Expert Feedback**
   - Structured interviews with faculty advisors
   - Professional applicability assessment

---

## Pilot Study Recommendations

Before full validation:

1. **Technical Pilot** (2-3 participants)
   - Verify system functionality end-to-end
   - Test evaluation interface usability
   - Identify technical issues

2. **Protocol Pilot** (3-5 participants)
   - Test orientation effectiveness
   - Validate time estimates
   - Refine metrics and instructions

3. **Domain Pilot** (education only)
   - Test with 3-5 education cases
   - Validate education ontology coverage
   - Assess prompt adaptation quality

---

## File References

| Component | Location |
|-----------|----------|
| Experiment routes | [app/routes/experiment.py](app/routes/experiment.py) |
| Prediction service | [app/services/experiment/prediction_service.py](app/services/experiment/prediction_service.py) |
| Experiment models | [app/models/experiment.py](app/models/experiment.py) |
| Double-blind template | [app/templates/experiment/double_blind_comparison.html](app/templates/experiment/double_blind_comparison.html) |
| Evaluation template | [app/templates/experiment/evaluate_prediction.html](app/templates/experiment/evaluate_prediction.html) |
| Chapter 4 reference | [docs-internal/references/chapter4.md](docs-internal/references/chapter4.md) |
| AAAI paper | [docs-internal/references/AAAI_Demo_Paper__Camera_Ready_.pdf](docs-internal/references/AAAI_Demo_Paper__Camera_Ready_.pdf) |

---

## Next Steps

1. **Immediate**: Verify infrastructure by running test experiment on 2-3 cases
2. **Short-term**: Recruit pilot participants from engineering program
3. **Medium-term**: Develop education ethics ontology and import cases
4. **Long-term**: Conduct full validation studies in both domains

---

*Document created: December 28, 2025*
*Based on analysis of existing ProEthica validation infrastructure*
