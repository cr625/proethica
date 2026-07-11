---
{
  "name": "Scenario Option Label",
  "description": "Phase 4.3: one action-oriented label plus a one-sentence description for a single decision option (called once per option in a per-option loop). NON-JSON output: two prefix-parsed lines.",
  "phase": "4",
  "extractor_file": "app/services/narrative/scenario_seed_generator.py",
  "prompt_method": "_generate_option_label_llm",
  "output_schema": {
    "type": "lines",
    "format": "Exactly two lines parsed by prefix: 'LABEL: ...' and 'DESCRIPTION: ...'"
  },
  "variable_builders": {
    "question": {
      "description": "The branch decision question",
      "source": "ScenarioBranch.question"
    },
    "obligations_text": {
      "description": "Comma-joined competing obligation labels (first 3), or 'Professional engineering ethics' when none",
      "source": "DecisionMoment.competing_obligations"
    },
    "option_number": {
      "description": "1-based option number within the branch (option_index + 1)",
      "source": "per-option loop index in _generate_options"
    },
    "is_board_choice": {
      "description": "Whether this option is the board's recommended choice (renders True/False)",
      "source": "per-option loop in _generate_options"
    },
    "style_formatting_line": {
      "description": "Shared ProEthica no-em-dash output-style clause",
      "source": "app/services/prompt_style.py STYLE_FORMATTING_LINE"
    }
  }
}
---
Generate a concise option label for an ethical decision scenario.

DECISION QUESTION: {{ question }}

RELEVANT OBLIGATIONS: {{ obligations_text }}

OPTION NUMBER: {{ option_number }} of 2
IS BOARD'S RECOMMENDED CHOICE: {{ is_board_choice }}

Generate:
1. A short action-oriented label (5-10 words)
2. A brief description (1 sentence)

The label should describe what the person would DO, not just "Option 1".
For example: "Report concerns to regulatory authority" or "Maintain confidentiality with employer"

{{ style_formatting_line }}

Output format (exactly two lines):
LABEL: [your label]
DESCRIPTION: [your description]
