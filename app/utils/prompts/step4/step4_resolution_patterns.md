---
{
  "name": "Step 4 Resolution Patterns (Phase 2E)",
  "description": "Analyzes HOW the board resolved each ethical question, expressed defeasibly (holds-when / would-not-hold-unless), grounded in the committed normative subgraph. Conclusions are C-numbered within the batch; question and provision references are by Q/P number.",
  "phase": "2E",
  "extractor_file": "app/services/step4_synthesis/rich_analysis.py",
  "prompt_method": "RichAnalyzer._analyze_resolution_batch",
  "output_schema": {
    "type": "array",
    "items": {
      "conclusion_index": "int, 1-based within the batch",
      "answers_questions": "[int Q-number]",
      "determinative_principles": "[string, up to 3]",
      "determinative_facts": "[string, up to 3]",
      "cited_provisions": "[int P-number]",
      "weighing_process": "string, 1 sentence",
      "resolution_conditions": "string, 'Holds when ...; would not hold if/unless ...'",
      "resolution_narrative": "string, 1-2 sentences",
      "confidence": "float 0.0-1.0"
    }
  },
  "variable_builders": {
    "conclusions_text": {
      "description": "Batch conclusions numbered C1..Cn as 'Cn. label: text' lines",
      "source": "code-built in _analyze_resolution_batch from the batch conclusions"
    },
    "questions_text": {
      "description": "All case questions numbered Q1..Qn, or the literal 'No questions extracted'",
      "source": "code-built in _analyze_resolution_batch from the questions list"
    },
    "provisions_text": {
      "description": "All provisions numbered P1..Pn as 'Pn. label: code - definition[:100]' lines, or the literal 'No provisions extracted'",
      "source": "code-built in _analyze_resolution_batch from the provisions list"
    },
    "norm_structure": {
      "description": "Committed normative subgraph (nodes plus fulfills/violates/guided-by edges); empty string renders the '(not available)' placeholder",
      "source": "format_subgraph(foundation.to_entity_dict(), _committed_edges_by_label(case_id)); '' when foundation is None"
    },
    "conclusion_count": {
      "description": "Number of conclusions in this batch",
      "source": "len(batch_conclusions)"
    },
    "style_formatting_line": {
      "description": "Shared ProEthica no-em-dash output formatting clause",
      "source": "app.services.prompt_style.STYLE_FORMATTING_LINE"
    }
  }
}
---
Analyze HOW the board resolved each ethical question in their conclusions.

## BOARD CONCLUSIONS (determinations made)
{{ conclusions_text }}

## ETHICAL QUESTIONS (that needed answers)
{{ questions_text }}

## CODE PROVISIONS (that could be cited)
{{ provisions_text }}

## CASE NORMATIVE STRUCTURE (already extracted -- ground the weighing in these)
{{ norm_structure or '  (not available)' }}

A board resolution is DEFEASIBLE: it holds only under the facts and conditions
that obtained in this case, and would not hold (or would reverse) if those
conditions changed. Express each resolution conditionally, not as an absolute
rule. State the activating conditions ("holds WHEN ...") and, where the board
signalled them, the defeating conditions ("would NOT hold UNLESS ..." / "absent ...").

For EACH conclusion above, analyze:
1. Which QUESTIONS does it answer? (by Q number)
2. What PRINCIPLES were determinative? (up to 3 key principles)
3. What FACTS were determinative? (up to 3 key facts)
4. What PROVISIONS were cited? (by P number)
5. How were COMPETING OBLIGATIONS weighed? (1 sentence)
6. Under WHAT CONDITIONS does this resolution hold, and what would defeat or
   reverse it? Phrase as "Holds when <conditions>; would not hold if/unless
   <defeating conditions>." (1-2 sentences)
7. A 1-2 sentence NARRATIVE explaining how the board reached this conclusion,
   framed conditionally on the determinative facts above (not as a universal rule)

Output as JSON array:
```json
[
  {
    "conclusion_index": 1,
    "answers_questions": [1, 2],
    "determinative_principles": ["principle 1", "principle 2"],
    "determinative_facts": ["fact 1", "fact 2"],
    "cited_provisions": [1, 3],
    "weighing_process": "One sentence on how competing obligations were balanced.",
    "resolution_conditions": "Holds when the engineer disclosed the conflict in writing; would not hold if the disclosure were withheld.",
    "resolution_narrative": "Given that X obtained, the board concluded Y because...",
    "confidence": 0.8
  }
]
```

Include all {{ conclusion_count }} conclusions in this batch.

{{ style_formatting_line }}
