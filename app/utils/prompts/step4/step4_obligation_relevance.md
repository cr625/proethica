---
{
  "name": "Step 4 Obligation Decision-Relevance Fallback",
  "description": "Phase 3 (E1 fallback): identifies which obligations/constraints are decision-relevant when the algorithmic coverage pass finds none. The returned indices are 1-based positions in the concatenated obligations+constraints lists; the index contract is load-bearing for the URI mapping in the parser.",
  "phase": "3",
  "extractor_file": "app/services/entity_analysis/obligation_coverage_analyzer.py",
  "prompt_method": "ObligationCoverageAnalyzer._llm_identify_decision_relevant",
  "output_schema": {
    "type": "object",
    "properties": {
      "decision_relevant_indices": "array of int, 1-based indices into the combined obligations+constraints listing",
      "reasoning": "string, brief explanation"
    }
  },
  "variable_builders": {
    "obligations_text": {
      "description": "Indexed obligation lines [n] label: definition (definitions capped at 200 chars)",
      "source": "code-built loop over ObligationAnalysis items in _llm_identify_decision_relevant"
    },
    "constraints_text": {
      "description": "Indexed constraint lines continuing the obligation numbering",
      "source": "code-built loop over ConstraintAnalysis items in _llm_identify_decision_relevant"
    },
    "questions_text": {
      "description": "Q-numbered question lines (first 5, 150-char cap)",
      "source": "code-built loop in _llm_identify_decision_relevant"
    },
    "conclusions_text": {
      "description": "C-numbered conclusion lines (first 5, 150-char cap)",
      "source": "code-built loop in _llm_identify_decision_relevant"
    }
  }
}
---
Analyze these ethical obligations and constraints from an NSPE ethics case.

OBLIGATIONS:
{{ obligations_text }}

CONSTRAINTS:
{{ constraints_text }}

QUESTIONS THE BOARD CONSIDERED:
{{ questions_text }}

BOARD'S CONCLUSIONS:
{{ conclusions_text }}

TASK: Identify which obligations/constraints are DECISION-RELEVANT - meaning they are central to the ethical dilemma and the board's analysis.

Return a JSON object with this structure:
{
  "decision_relevant_indices": [1, 3, 5],  // Indices from the lists above
  "reasoning": "Brief explanation of why these are central to the case"
}

Focus on obligations that:
1. Are directly referenced in the questions or conclusions
2. Create ethical tension or conflict
3. Require the engineer to make a difficult choice

Return ONLY the JSON object, no other text.
