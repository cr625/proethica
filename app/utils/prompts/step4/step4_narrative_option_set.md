---
{
  "name": "Scenario Option Set",
  "description": "Phase 4.3: generates a full two-option set for a branch with no options (called per branch). Option 1 aligns with professional duty (board choice). NON-JSON output: four prefix-parsed lines.",
  "phase": "4",
  "extractor_file": "app/services/narrative/scenario_seed_generator.py",
  "prompt_method": "_generate_options_llm",
  "output_schema": {
    "type": "lines",
    "format": "Four lines parsed by prefix: 'OPTION1_LABEL: ...', 'OPTION1_DESC: ...', 'OPTION2_LABEL: ...', 'OPTION2_DESC: ...'"
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
    "style_formatting_line": {
      "description": "Shared ProEthica no-em-dash output-style clause",
      "source": "app/services/prompt_style.py STYLE_FORMATTING_LINE"
    }
  }
}
---
Generate two ethical decision options for this scenario.

DECISION QUESTION: {{ question }}

RELEVANT OBLIGATIONS: {{ obligations_text }}

Generate exactly 2 options that represent meaningful choices.
Option 1 should typically align with professional duty (mark as board choice).
Option 2 should represent an alternative approach.

{{ style_formatting_line }}

Output format:
OPTION1_LABEL: [action-oriented label, 5-10 words]
OPTION1_DESC: [1 sentence description]
OPTION2_LABEL: [action-oriented label, 5-10 words]
OPTION2_DESC: [1 sentence description]
