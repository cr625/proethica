---
{
  "name": "Step 4 Question Emergence / Toulmin (Phase 2E)",
  "description": "Analyzes WHY each ethical question emerged using Toulmin's model, grounded in the committed entity subgraph. Questions are Q-numbered; the LLM returns question_index-keyed analyses with exact entity labels resolved to URIs post-parse.",
  "phase": "2E",
  "extractor_file": "app/services/step4_synthesis/rich_analysis.py",
  "prompt_method": "RichAnalyzer.analyze_question_batch",
  "output_schema": {
    "type": "array",
    "items": {
      "question_index": "int, 1-based Q-number within the batch",
      "data_events": "[event label]",
      "data_actions": "[action label]",
      "involves_roles": "[role label]",
      "competing_warrants": "[[obligation A label, obligation B label]]",
      "data_warrant_tension": "string, 1 sentence",
      "competing_claims": "string, 1 sentence",
      "rebuttal_conditions": "string, 1 sentence",
      "emergence_narrative": "string, 1-2 sentences",
      "confidence": "float 0.0-1.0"
    }
  },
  "variable_builders": {
    "toulmin_context": {
      "description": "Concise Toulmin argumentation framing (DATA/WARRANT/REBUTTAL); empty string when the academic-references module is unavailable",
      "source": "app.academic_references.frameworks.toulmin_argumentation.get_concise_emergence_context()"
    },
    "questions_text": {
      "description": "Batch questions numbered Q1..Qn as 'Qn. label: text' lines",
      "source": "code-built in analyze_question_batch from the questions list"
    },
    "entities_text": {
      "description": "Entity subgraph: nodes with definitions plus committed fulfills/violates/guided-by edges in label form (edge targets validated against the extracted labels)",
      "source": "format_subgraph(foundation.to_entity_dict(), _committed_edges_by_label(case_id, entity_dict))"
    },
    "facts_text": {
      "description": "The Facts section of the case, verbatim; '' when unavailable (the block is then omitted). The chronology of the emergence narrative must follow it",
      "source": "caller (analyze_question_batch facts_text) or RichAnalyzer._load_facts_text(case_id) (case 8 review lesson L5)"
    },
    "style_formatting_line": {
      "description": "Shared ProEthica no-em-dash output formatting clause",
      "source": "app.services.prompt_style.STYLE_FORMATTING_LINE"
    }
  }
}
---
Analyze WHY each ethical question emerged using Toulmin's model.

{{ toulmin_context }}
{% if facts_text %}
## CASE FACTS (the chronology of the case; the emergence narrative must follow it)
{{ facts_text }}
{% endif %}
## QUESTIONS TO ANALYZE
{{ questions_text }}

## EXTRACTED ENTITIES
{{ entities_text }}

For EACH question, use exact entity labels from the list above.{% if facts_text %} State the
triggering facts in the order the CASE FACTS give them; do not place a later event before an
earlier one.{% endif %} Output JSON:
```json
[
  {
    "question_index": 1,
    "data_events": ["event label", ...],
    "data_actions": ["action label", ...],
    "involves_roles": ["role label", ...],
    "competing_warrants": [["obligation A label", "obligation B label"]],
    "data_warrant_tension": "1 sentence on how data triggers multiple warrants",
    "competing_claims": "1 sentence on what different warrants conclude",
    "rebuttal_conditions": "1 sentence on what creates uncertainty",
    "emergence_narrative": "1-2 sentences explaining why this question arose",
    "confidence": 0.8
  }
]
```

Include all questions in this batch.

{{ style_formatting_line }}
