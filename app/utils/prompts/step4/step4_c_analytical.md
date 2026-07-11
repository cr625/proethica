---
{
  "name": "Step 4 Analytical Conclusion Generation",
  "description": "Generates analytical conclusions (analytical_extension, question_response, principle_synthesis) beyond the Board's explicit conclusions. Called three times per case, one category per batch. The per-category instruction blocks (static strings, unlike the question side) and the output-JSON example are assembled by the builder into the categories variable.",
  "phase": "2C",
  "extractor_file": "app/services/step4_synthesis/conclusion_analyzer.py",
  "prompt_method": "_create_analytical_prompt",
  "output_schema": {
    "format": "json_object",
    "keys": "one array per requested category (analytical_extension, question_response, principle_synthesis); the example block in the prompt mirrors the requested subset",
    "item_fields": {
      "conclusion_text": "plain-English conclusion, no URIs",
      "mentioned_entities": "{entity_type: [exact labels from the entity list]}",
      "cited_provisions": "[provision codes]",
      "source_conclusion": "board conclusion number or null",
      "related_analytical_questions": "[analytical question numbers]"
    }
  },
  "variable_builders": {
    "board_c_text": {
      "description": "Numbered board conclusions with [board_conclusion_type] tags, or the no-conclusions placeholder line",
      "source": "ConclusionAnalyzer._analytical_prompt_variables (from board_conclusions)"
    },
    "board_q_text": {
      "description": "Q-numbered board questions, or the no-questions placeholder line",
      "source": "ConclusionAnalyzer._analytical_prompt_variables (from board_questions)"
    },
    "analytical_text": {
      "description": "Analytical questions grouped by type with Q-numbers; the template substitutes '(none provided)' when empty",
      "source": "ConclusionAnalyzer._analytical_prompt_variables (from analytical_questions)"
    },
    "case_facts": {
      "description": "Case facts text; the template substitutes '(not provided)' when empty",
      "source": "caller argument"
    },
    "entities_text": {
      "description": "All nine entity types formatted as label plus short definition",
      "source": "app.utils.entity_prompt_utils.format_entities_compact(all_entities)"
    },
    "provisions_text": {
      "description": "CODE PROVISIONS EXTRACTED block (up to 10 provisions, 100-char text cap); empty string when none",
      "source": "ConclusionAnalyzer._format_provisions(code_provisions)"
    },
    "categories": {
      "description": "List of {block, example} dicts, one per requested category in fixed analytical_extension/question_response/principle_synthesis order. block = category instruction text; example = the category's output-JSON example fragment",
      "source": "ConclusionAnalyzer._analytical_prompt_variables (selection logic)"
    }
  }
}
---
You are an ethics analyst examining an NSPE Board of Ethical Review case.

**BOARD'S EXPLICIT CONCLUSIONS:**
{{ board_c_text }}

**BOARD'S QUESTIONS:**
{{ board_q_text }}

**ANALYTICAL QUESTIONS (generated):**
{{ analytical_text if analytical_text else "(none provided)" }}

**CASE FACTS:**
{{ case_facts if case_facts else "(not provided)" }}

**ALL EXTRACTED ENTITIES:**
{{ entities_text }}

{{ provisions_text }}

**TASK:**
Generate analytical conclusions that deepen understanding beyond the Board's explicit conclusions.

{% for cat in categories %}{{ loop.index }}. {{ cat.block }}{% if not loop.last %}

{% endif %}{% endfor %}

**FORMATTING RULES:**
- Write conclusions in plain English. Do NOT embed URIs in conclusion_text.
- Reference entities by their exact label in the mentioned_entities field.
- Generate 1-3 conclusions per category.
- Link to source_conclusion (Board conclusion number) when extending Board's reasoning.
- Link to related_analytical_questions (question numbers) when responding to them.

**OUTPUT FORMAT (JSON):**
```json
{{ '{{' }}
{% for cat in categories %}{{ cat.example }}{% if not loop.last %},
{% endif %}{% endfor %}
}}
```

