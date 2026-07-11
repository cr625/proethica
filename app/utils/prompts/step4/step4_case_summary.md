---
{
  "name": "Case Summary (Case Synthesizer)",
  "description": "Phase 4 (case_synthesizer surface, reached via step4/synthesis.py): 2-3 sentence plain-text case summary naming the tension, the decision-maker role, and a hint at the resolution. STYLE line added at migration (2026-07-10 deviation).",
  "phase": "4",
  "extractor_file": "app/services/case_synthesizer/narrative.py",
  "prompt_method": "_construct_narrative_with_llm",
  "output_schema": {
    "type": "text",
    "description": "2-3 sentence professional, objective case summary, no additional text"
  },
  "variable_builders": {
    "case_title": {
      "description": "Document title, or 'Case <id>' fallback",
      "source": "Document.title"
    },
    "facts_text": {
      "description": "Facts section text from doc_metadata sections_dual, truncated to 1500 chars",
      "source": "Document.doc_metadata['sections_dual']['facts']"
    },
    "participants": {
      "description": "Comma-joined labels of the first 5 roles",
      "source": "EntityFoundation.roles"
    },
    "obligations": {
      "description": "Comma-joined labels of the first 5 obligations",
      "source": "EntityFoundation.obligations"
    },
    "decision_points": {
      "description": "Bulleted decision questions of the first 3 canonical decision points",
      "source": "CanonicalDecisionPoint list (Phase 3)"
    },
    "board_conclusions": {
      "description": "Bulleted text[:100] of the first 2 board conclusions",
      "source": "conclusions dict list"
    },
    "style_formatting_line": {
      "description": "Shared ProEthica no-em-dash output-style clause",
      "source": "app/services/prompt_style.py STYLE_FORMATTING_LINE"
    }
  }
}
---
Generate a concise 2-3 sentence summary of this NSPE ethics case.

## Case: {{ case_title }}

## Facts (excerpt):
{{ facts_text }}

## Key Participants:
{{ participants }}

## Obligations at stake:
{{ obligations }}

## Decision Points:
{{ decision_points }}

## Board Conclusions:
{{ board_conclusions }}

Write a professional, objective summary that:
1. Identifies the key ethical tension
2. Names the primary decision-maker role (without using "Engineer A" - describe their role)
3. Hints at the resolution

{{ style_formatting_line }}

Output ONLY the 2-3 sentence summary, no additional text.
