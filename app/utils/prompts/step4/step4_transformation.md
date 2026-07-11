---
{
  "name": "Step 4 Transformation Classification",
  "description": "Phase 2D: classifies HOW the ethical situation was transformed through the Board's resolution, per the Marchais-Roubelat & Roubelat (2015) typology. The framework context is resolved in the builder (ImportError-tolerant academic module) and passed as a variable.",
  "phase": "2D",
  "extractor_file": "app/services/case_analysis/transformation_classifier.py",
  "prompt_method": "TransformationClassifier._llm_classification",
  "output_schema": {
    "type": "object",
    "properties": {
      "transformation_type": "transfer | stalemate | oscillation | phase_lag | unclear",
      "confidence": "float 0.0-1.0",
      "reasoning": "string, 2-3 sentences grounded in the case facts and framework definitions",
      "pattern_description": "string, the transformation pattern in THIS case",
      "supporting_evidence": ["string quotes or facts"],
      "involved_roles": ["string role labels"],
      "obligation_shifts": ["string descriptions of how obligations moved"]
    }
  },
  "variable_builders": {
    "framework_context": {
      "description": "Academic transformation-classification framework text with examples",
      "source": "academic_references.frameworks.transformation_classification.get_prompt_context(include_examples=True, include_mapping=False); builtin fallback on ImportError"
    },
    "case_title": {
      "description": "Case title",
      "source": "caller or Document lookup"
    },
    "case_facts": {
      "description": "Facts section text truncated to 2000 chars; empty string selects the facts-unavailable fallback line",
      "source": "caller or doc_metadata sections_dual.facts (truncation in builder)"
    },
    "entities_context": {
      "description": "ROLES/OBLIGATIONS/KEY ACTIONS/CONSTRAINTS label lines; empty string omits the block",
      "source": "code-built from all_entities (5/5/5/3 caps) in _llm_classification"
    },
    "questions_text": {
      "description": "Q-numbered question lines with optional [type] tags, or the no-questions placeholder",
      "source": "code-built loop in _llm_classification"
    },
    "conclusions_text": {
      "description": "C-numbered conclusion lines with optional [type] tags, or the no-conclusions placeholder",
      "source": "code-built loop in _llm_classification"
    },
    "patterns_text": {
      "description": "Resolution-pattern bullet lines (first 3); empty string omits the block",
      "source": "code-built from resolution_patterns in _llm_classification"
    }
  }
}
---
{{ framework_context }}

CASE ANALYSIS: {{ case_title }}

CASE FACTS:
{% if case_facts %}{{ case_facts }}{% else %}(Facts not available - analyze based on questions and conclusions){% endif %}

{% if entities_context %}EXTRACTED ENTITIES:
{{ entities_context }}{% endif %}

ETHICAL QUESTIONS POSED TO THE BOARD:
{{ questions_text }}

BOARD'S CONCLUSIONS:
{{ conclusions_text }}

{% if patterns_text %}RESOLUTION PATTERNS:
{{ patterns_text }}{% endif %}

ANALYSIS TASK:
Based on the academic framework above and the case details, classify HOW the ethical situation
was transformed through the Board's resolution. Focus on:
1. How obligations shifted between parties
2. Whether tensions were resolved or remain
3. The temporal pattern of responsibility

Return your analysis as JSON:
{
    "transformation_type": "transfer|stalemate|oscillation|phase_lag|unclear",
    "confidence": 0.0-1.0,
    "reasoning": "2-3 sentence explanation grounded in the case facts and framework definitions",
    "pattern_description": "Specific description of the transformation pattern in THIS case",
    "supporting_evidence": ["quote or fact 1", "quote or fact 2", "quote or fact 3"],
    "involved_roles": ["role1", "role2"],
    "obligation_shifts": ["description of how obligations moved"]
}
