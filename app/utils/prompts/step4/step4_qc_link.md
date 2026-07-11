---
{
  "name": "Step 4 Question-Conclusion Linking",
  "description": "Determines which conclusion answers which question (numbered lists in, JSON link records out). The links become answersQuestion edges on the committed conclusion individuals.",
  "phase": "2C",
  "extractor_file": "app/services/step4_synthesis/question_conclusion_linker.py",
  "prompt_method": "_create_linking_prompt",
  "output_schema": {
    "format": "json_array",
    "item_fields": {
      "conclusion_number": "int",
      "answers_questions": "[question numbers this conclusion answers; empty list if none]",
      "confidence": "float 0.0-1.0",
      "reasoning": "why the conclusion answers the question(s)"
    }
  },
  "variable_builders": {
    "questions_text": {
      "description": "Numbered questions, each as a **Question N:** header plus quoted text",
      "source": "QuestionConclusionLinker._linking_prompt_variables (handles dict and dataclass inputs)"
    },
    "conclusions_text": {
      "description": "Numbered conclusions, each as a **Conclusion N:** header plus quoted text and a Type line",
      "source": "QuestionConclusionLinker._linking_prompt_variables (handles dict and dataclass inputs)"
    }
  }
}
---
You are analyzing NSPE Board of Ethical Review questions and conclusions to determine which conclusion answers which question.

**QUESTIONS:**
{{ questions_text }}

**CONCLUSIONS:**
{{ conclusions_text }}

**TASK:**
For each conclusion, determine which question(s) it answers.

Consider:
- Direct answers: Conclusion explicitly addresses the question
- Partial answers: Conclusion addresses part of a multi-part question
- Implicit answers: Conclusion answers question without restating it

**OUTPUT FORMAT (JSON):**
```json
[
  {
    "conclusion_number": 1,
    "answers_questions": [1],
    "confidence": 0.95,
    "reasoning": "Conclusion 1 directly addresses Question 1 by stating whether Engineer A violated II.4.e, which is exactly what Question 1 asked."
  },
  {
    "conclusion_number": 2,
    "answers_questions": [1, 2],
    "confidence": 0.90,
    "reasoning": "Conclusion 2 addresses both Question 1 (violation determination) and Question 2 (disclosure requirement) as related issues."
  }
]
```

**IMPORTANT:**
- A conclusion can answer multiple questions
- Multiple conclusions can answer the same question
- Provide confidence (0.0-1.0) and reasoning for each link
- If a conclusion doesn't answer any question, use answers_questions: []

