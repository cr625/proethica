---
{
  "name": "Timeline Phases (Case Synthesizer)",
  "description": "Phase 4 (case_synthesizer surface, reached via step4/synthesis.py): 4-6 labeled timeline phases with 1-2 sentence descriptions and an event_type enum. STYLE line added at migration (2026-07-10 deviation).",
  "phase": "4",
  "extractor_file": "app/services/case_synthesizer/narrative.py",
  "prompt_method": "_construct_narrative_with_llm",
  "output_schema": {
    "type": "array",
    "items": {
      "phase_label": "string",
      "description": "string (1-2 sentences)",
      "event_type": "state|action|event|decision|outcome"
    }
  },
  "variable_builders": {
    "case_title": {
      "description": "Document title, or 'Case <id>' fallback",
      "source": "Document.title"
    },
    "roles": {
      "description": "Comma-joined labels of the first 5 roles",
      "source": "EntityFoundation.roles"
    },
    "states": {
      "description": "Comma-joined labels of the first 5 states",
      "source": "EntityFoundation.states"
    },
    "actions": {
      "description": "Comma-joined labels of the first 5 actions",
      "source": "EntityFoundation.actions"
    },
    "events": {
      "description": "Comma-joined labels of the first 5 events",
      "source": "EntityFoundation.events"
    },
    "decision_points": {
      "description": "Numbered decision questions of the first 4 canonical decision points",
      "source": "CanonicalDecisionPoint list (Phase 3)"
    },
    "conclusions": {
      "description": "Bulleted text[:150] of the first 2 board conclusions",
      "source": "conclusions dict list"
    },
    "style_formatting_line": {
      "description": "Shared ProEthica no-em-dash output-style clause",
      "source": "app/services/prompt_style.py STYLE_FORMATTING_LINE"
    }
  }
}
---
Create a timeline of key events for this ethics case. For each phase, write a 1-2 sentence description.

## Case: {{ case_title }}

## Extracted Entities:
- Roles: {{ roles }}
- States: {{ states }}
- Actions: {{ actions }}
- Events: {{ events }}

## Decision Points:
{{ decision_points }}

## Conclusions:
{{ conclusions }}

Generate 4-6 timeline phases. For each, output:
1. Phase label (e.g., "Initial Situation", "Conflict Emerges", "Decision Point", "Resolution")
2. Description (1-2 sentences, objective professional tone)
3. Event type: state/action/event/decision/outcome

{{ style_formatting_line }}

Output as JSON array:
```json
[
  {"phase_label": "...", "description": "...", "event_type": "state"},
  ...
]
```
