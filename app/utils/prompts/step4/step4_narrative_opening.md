---
{
  "name": "Scenario Opening Context",
  "description": "Phase 4.3: the second-person opening paragraph of the interactive scenario, governed by 8 strict rules (no board conclusions, no editorializing, 3-6 sentences). Plain-text output; a post-hoc em-dash replacement is applied in code.",
  "phase": "4",
  "extractor_file": "app/services/narrative/scenario_seed_generator.py",
  "prompt_method": "_enhance_opening_with_llm",
  "output_schema": {
    "type": "text",
    "description": "3-6 sentence second-person opening context, approximately 500-800 characters, no commentary"
  },
  "variable_builders": {
    "case_facts": {
      "description": "Facts section text truncated to 1500 chars",
      "source": "document_sections query via ScenarioSeedGenerator._load_case_facts"
    },
    "setting_description": {
      "description": "Narrative setting description, or 'Professional context' when no setting",
      "source": "NarrativeElements.setting.description"
    },
    "primary_maker": {
      "description": "Primary decision-maker label (most frequent branch decision_maker_label, protagonist fallback); used in the header and inside rule 1",
      "source": "ScenarioBranch decision-maker counts / _identify_protagonist"
    },
    "branch_summary": {
      "description": "Indented 'n. [decision-maker] question[:150]' lines for the first 8 branches",
      "source": "ScenarioBranch list"
    },
    "style_formatting_line": {
      "description": "Shared ProEthica no-em-dash output-style clause (rule 4)",
      "source": "app/services/prompt_style.py STYLE_FORMATTING_LINE"
    }
  }
}
---
Write the opening context paragraph for an interactive professional ethics scenario.

## Case Facts
{{ case_facts }}

## Setting
{{ setting_description }}

## Primary Decision-Maker
{{ primary_maker }}

## Decision Questions the User Will Face
{{ branch_summary }}

## Rules (strict)
1. Begin with "You are {{ primary_maker }}" and write in second person.
2. Set up the factual situation BEFORE the decisions. Do not narrate what the protagonist chose or what happened as a result.
3. Include specific parties, projects, and technical details from the case facts. Do not be abstract or vague.
4. {{ style_formatting_line }}
5. Do not editorialize, flatter ("seasoned professional"), or use dramatic framing ("now sits at the center of").
6. Do not reveal the board's conclusions or how the case was resolved.
7. End with a forward-looking sentence about the decisions ahead, without naming specific choices.
8. Write 3-6 sentences, approximately 500-800 characters.

Output ONLY the opening context text, no commentary.
