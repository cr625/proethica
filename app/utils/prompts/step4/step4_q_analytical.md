---
{
  "name": "Step 4 Analytical Question Generation",
  "description": "Generates analytical questions (implicit, principle_tension, theoretical, counterfactual) beyond the Board's explicit questions. Called twice per case with category subsets: implicit+principle_tension, then theoretical+counterfactual. The per-category instruction blocks and the output-JSON example are assembled by the builder into the categories variable; each block leads with the ontology-governed QUESTION_TYPES definition (proethica-cases.ttl QuestionTypeScheme, drift-tested).",
  "phase": "2C",
  "extractor_file": "app/services/step4_synthesis/question_analyzer.py",
  "prompt_method": "_create_analytical_prompt",
  "output_schema": {
    "format": "json_object",
    "keys": "one array per requested category (implicit, principle_tension, theoretical, counterfactual); the example block in the prompt mirrors the requested subset",
    "item_fields": {
      "question_text": "plain-English question, no URIs",
      "mentioned_entities": "{entity_type: [exact labels from the entity list]}",
      "related_provisions": "[provision codes]",
      "source_question": "board question number or null",
      "ethical_framework": "theoretical only: deontological | consequentialist | virtue_ethics",
      "negated_fact": "counterfactual only: the case fact the antecedent negates or alters"
    }
  },
  "variable_builders": {
    "board_q_text": {
      "description": "Numbered board questions, or the no-questions placeholder line",
      "source": "QuestionAnalyzer._analytical_prompt_variables (from board_questions)"
    },
    "case_facts": {
      "description": "Case facts text; the template substitutes '(not provided)' when empty",
      "source": "caller argument"
    },
    "case_conclusion": {
      "description": "Board conclusion text; the template substitutes '(not provided)' when empty",
      "source": "caller argument"
    },
    "entities_text": {
      "description": "All nine entity types formatted as label plus short definition",
      "source": "app.utils.entity_prompt_utils.format_entities_compact(all_entities)"
    },
    "provisions_text": {
      "description": "CODE PROVISIONS EXTRACTED block (up to 10 provisions, 100-char text cap); empty string when none",
      "source": "QuestionAnalyzer._format_provisions(code_provisions)"
    },
    "categories": {
      "description": "List of {block, example} dicts, one per requested category in fixed implicit/principle_tension/theoretical/counterfactual order. block = category instruction text (leads with QUESTION_TYPES[cat]; principle_tension interpolates the per-case principles list); example = the category's output-JSON example fragment",
      "source": "QuestionAnalyzer._analytical_prompt_variables (selection logic + QUESTION_TYPES chain)"
    }
  }
}
---
You are an ethics analyst examining an NSPE Board of Ethical Review case.

**BOARD'S EXPLICIT QUESTIONS:**
{{ board_q_text }}

**CASE FACTS:**
{{ case_facts if case_facts else "(not provided)" }}

**BOARD'S CONCLUSION:**
{{ case_conclusion if case_conclusion else "(not provided)" }}

**ALL EXTRACTED ENTITIES:**
{{ entities_text }}

{{ provisions_text }}

**TASK:**
Generate analytical questions that deepen understanding beyond the Board's explicit questions.

{% for cat in categories %}{{ loop.index }}. {{ cat.block }}{% if not loop.last %}

{% endif %}{% endfor %}

**FORMATTING RULES:**
- Write questions in plain English. Do NOT embed URIs in question_text.
- Reference entities by their exact label in the mentioned_entities field.
- Generate UP TO 4 questions per category; fewer or zero is acceptable. Emit only
  questions that meet the category's criteria -- do not pad a category to reach a count.
- Link to source Board questions when applicable (source_question field).
- CONTINGENCY ANCHORING (applies to EVERY category): a question whose premise is a
  contingency -- a party's future or hypothetical refusal, rejection, non-compliance,
  or any other event the case does not narrate -- is permitted ONLY when the case text
  itself raises that contingency (in the facts, discussion, or conclusion). If the text
  never discusses the condition, do not ask what should happen under it. (Counterfactual
  questions that NEGATE a stated fact per the counterfactual criteria remain permitted;
  the forbidden form is the un-discussed FORWARD contingency, e.g. "if the client then
  refuses to act, must the engineer escalate?" in a case that never reaches that point.)

**OUTPUT FORMAT (JSON):**
```json
{{ '{{' }}
{% for cat in categories %}{{ cat.example }}{% if not loop.last %},
{% endif %}{% endfor %}
}}
```

