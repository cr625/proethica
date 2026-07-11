---
{
  "name": "Step 4 Board Question Extraction (fallback)",
  "description": "Extracts the Board's explicit questions from the Questions section via LLM. Fallback path: used only when the imported questions_list is absent and the structural regex parse finds nothing.",
  "phase": "2C",
  "extractor_file": "app/services/step4_synthesis/question_analyzer.py",
  "prompt_method": "_create_board_extraction_prompt",
  "output_schema": {
    "format": "json_array",
    "item_fields": {
      "question_number": "int, position in the Questions section",
      "question_text": "verbatim question text",
      "question_type": "board_explicit",
      "mentioned_entities": "{entity_type: [exact labels from the entity list]}",
      "related_provisions": "[provision codes]",
      "extraction_reasoning": "what the question is asking"
    }
  },
  "variable_builders": {
    "questions_text": {
      "description": "Raw Questions section text from the case document",
      "source": "caller argument (document section text)"
    },
    "entities_text": {
      "description": "All nine entity types formatted as label plus short definition",
      "source": "app.utils.entity_prompt_utils.format_entities_compact(all_entities)"
    },
    "provisions_text": {
      "description": "CODE PROVISIONS EXTRACTED block (up to 10 provisions, 100-char text cap); empty string when none",
      "source": "QuestionAnalyzer._format_provisions(code_provisions)"
    }
  }
}
---
You are analyzing the Questions section from an NSPE Board of Ethical Review case.

**QUESTIONS SECTION TEXT:**
{{ questions_text }}

**EXTRACTED CASE ENTITIES:**
{{ entities_text }}

{{ provisions_text }}

**TASK:**
Extract ONLY the Board's explicit questions (the actual questions posed to the Board).
These are the questions the case was asked to answer.

For each question:
1. **Question Text**: The verbatim question text
2. **Mentioned Entities**: Which entities from the case are referenced? Use exact labels from the list above.
3. **Related Provisions**: Which code provisions (if any) are mentioned?
4. **Reasoning**: What is this question really asking?

**OUTPUT FORMAT (JSON):**
```json
[
  {
    "question_number": 1,
    "question_text": "Was it ethical for Engineer A to accept the contract?",
    "question_type": "board_explicit",
    "mentioned_entities": {
      "roles": ["Engineer A"]
    },
    "related_provisions": ["II.4.e"],
    "extraction_reasoning": "Asks whether accepting the contract violated ethical duties."
  }
]
```

Extract ALL questions the Board was asked. Use EXACT entity labels from the lists above.

