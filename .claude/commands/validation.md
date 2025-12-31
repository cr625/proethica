# ProEthica Validation Framework

## Agent Responsibilities

This agent maintains alignment between:
1. **Chapter 4** ([docs-internal/references/chapter4.md](docs-internal/references/chapter4.md)) - Dissertation validation methodology
2. **Implementation** - Database schema, routes, templates, and services
3. **Documentation** - [VALIDATION_FRAMEWORK_UNIFIED.md](docs-internal/VALIDATION_FRAMEWORK_UNIFIED.md)

When invoked, verify that terminology, metrics, scales, and protocols are consistent across all three.

---

## Terminology Distinction

| Operation | Term | Description |
|-----------|------|-------------|
| **Pipeline (Steps 1-4)** | "Analysis" | Extracts concepts (R, P, O, S, Rs, A, E, Ca, Cs) FROM existing case text |
| **Validation Interface** | "Ethical Determination" | Generates the judgment/conclusion the ethics board SHOULD make |

The pipeline **analyzes** what exists in a case. The validation interface **determines** what the outcome should be.

---

## Current Metrics (Chapter 4 Aligned)

All metrics use **1-7 Likert scale** (standard in argument quality research).

### RTI: Reasoning Transparency Index
Measures clarity of argumentative steps and Toulmin-based traceability (Data -> Warrant -> Claim).

**Sub-items (4):**
- `rti_premises_clear` - Are factual premises clearly stated?
- `rti_steps_explicit` - Are reasoning steps explicit and followable?
- `rti_conclusion_supported` - Is the conclusion clearly supported by prior steps?
- `rti_alternatives_acknowledged` - Are alternative interpretations acknowledged?

### PBRQ: Precedent-Based Reasoning Quality
Evaluates case-based reasoning methodology.

**Sub-items (4):**
- `pbrq_precedents_identified` - Are relevant precedent cases identified?
- `pbrq_principles_extracted` - Are transferable principles correctly extracted?
- `pbrq_adaptation_appropriate` - Is the adaptation to current facts appropriate?
- `pbrq_selection_justified` - Is the precedent selection well-justified?

### CA: Citation Accuracy
Measures factual correctness of source attribution.

**Sub-items (3):**
- `ca_code_citations_correct` - Are code provisions correctly cited?
- `ca_precedents_characterized` - Are precedent cases accurately characterized?
- `ca_citations_support_claims` - Do citations support the claims made?

### DRA: Domain Relevance Assessment
Evaluates professional practice applicability.

**Sub-items (4):**
- `dra_concerns_relevant` - Does the analysis address concerns relevant to practice?
- `dra_patterns_accepted` - Does reasoning follow accepted professional patterns?
- `dra_guidance_helpful` - Would this guidance help a practitioner?
- `dra_domain_weighted` - Are domain considerations appropriately weighted?

### Overall Preference (5-point scale)
- -2: System A strongly preferred
- -1: System A somewhat preferred
- 0: No meaningful difference
- +1: System B somewhat preferred
- +2: System B strongly preferred

---

## Alignment Verification Checklist

### Terminology Alignment
- [ ] UI uses "Ethical Determination" (not "Conclusion Prediction")
- [ ] Routes use correct docstrings
- [ ] Chapter 4 uses consistent terminology

### Metric Alignment
- [ ] Database schema has all 15 sub-item columns
- [ ] Templates show all 4 metrics with correct sub-items
- [ ] Chapter 4 describes same metrics and sub-items

### Scale Alignment
- [ ] All metrics use 1-7 Likert scale
- [ ] Preference uses 5-point scale (-2 to +2)
- [ ] IRR thresholds: 0.60 minimum, 0.70 target, 0.80 strong

### Protocol Alignment
- [ ] 10-15 evaluators
- [ ] 23 cases
- [ ] 3-4 hours total time commitment
- [ ] Orientation 45 min, Evaluation 2-3 hours, Reflection 30 min

---

## Key Files

| Component | Location |
|-----------|----------|
| **Chapter 4** | [docs-internal/references/chapter4.md](docs-internal/references/chapter4.md) |
| **Unified Framework** | [docs-internal/VALIDATION_FRAMEWORK_UNIFIED.md](docs-internal/VALIDATION_FRAMEWORK_UNIFIED.md) |
| **Revision Guide** | [docs-internal/CHAPTER4_REVISION_GUIDE.md](docs-internal/CHAPTER4_REVISION_GUIDE.md) |
| Routes | [app/routes/experiment.py](app/routes/experiment.py) |
| Prediction service | [app/services/experiment/prediction_service.py](app/services/experiment/prediction_service.py) |
| Database model | [app/models/experiment.py](app/models/experiment.py) |
| Double-blind template | [app/templates/experiment/double_blind_comparison.html](app/templates/experiment/double_blind_comparison.html) |
| Dashboard | [app/templates/experiment/index.html](app/templates/experiment/index.html) |

---

## Theoretical Foundation

### Toulmin Model Mapping
The validation metrics align with Toulmin's argumentation model:

| Toulmin Component | ProEthica Framework |
|-------------------|---------------------|
| Claim (C) | Ethical conclusion |
| Data (D) | States (S), Resources (Rs) |
| Warrant (W) | Principles (P), Obligations (O) |
| Backing (B) | Resources (Rs), Precedents |
| Qualifier (Q) | Capabilities (Ca), Constraints (Cs) |
| Rebuttal (R) | Alternatives considered |

### Academic Precedent
- McLaren (2006): 8 experts, 15 cases, alpha = 0.72
- Ashley & McLaren (1995): 10-15 domain experts for CBR validation
- AI-CARE study (Lemieux et al., 2025): Double-blind comparative methodology

---

## Success Criteria

### Metric Performance
- ProEthica mean scores > 4.5 (adequate quality)
- ProEthica significantly higher than baseline on >= 2 metrics
- No metric shows ProEthica worse than baseline

### Evaluator Preference
- > 60% prefer ProEthica over baseline
- Strong preferences favor ProEthica more than baseline

### Reliability
- Krippendorff's alpha >= 0.60 for all metrics

---

## Implementation Status

### Current State (December 2025)
- [x] Double-blind interface implemented with Chapter 4 metrics
- [x] 15 sub-items across 4 metrics
- [x] 5-point preference scale with justification
- [x] Randomized system assignment
- [x] Progress tracking and validation
- [x] Terminology updated to "Ethical Determination"
- [ ] Database migration for new schema columns (pending)
- [ ] Analysis service for statistical computations (pending)
- [ ] Education domain support (future work)

### Database Schema (Target)
```sql
-- RTI sub-items (1-7 scale)
rti_premises_clear INTEGER
rti_steps_explicit INTEGER
rti_conclusion_supported INTEGER
rti_alternatives_acknowledged INTEGER

-- PBRQ sub-items (1-7 scale)
pbrq_precedents_identified INTEGER
pbrq_principles_extracted INTEGER
pbrq_adaptation_appropriate INTEGER
pbrq_selection_justified INTEGER

-- CA sub-items (1-7 scale)
ca_code_citations_correct INTEGER
ca_precedents_characterized INTEGER
ca_citations_support_claims INTEGER

-- DRA sub-items (1-7 scale)
dra_concerns_relevant INTEGER
dra_patterns_accepted INTEGER
dra_guidance_helpful INTEGER
dra_domain_weighted INTEGER

-- Preference
overall_preference INTEGER  -- -2 to +2
preference_justification TEXT
```

---

## Agent Commands

When invoked with arguments:

- `verify` - Check alignment between Chapter 4, implementation, and documentation
- `verify <file1> <file2>` - Verify specific files for consistency
- `update` - Identify and list needed updates
- `status` - Report current implementation status

---

*Last Updated: December 30, 2025*
*Aligned with Chapter 4 and VALIDATION_FRAMEWORK_UNIFIED.md*
