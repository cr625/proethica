---
{
  "name": "Narrative Character Enhancement",
  "description": "Phase 4.1: one-sentence character insights for each extracted role plus a missing-character rescan of the Facts section (recovers present-case actors the role pass omitted).",
  "phase": "4",
  "extractor_file": "app/services/narrative/narrative_element_extractor.py",
  "prompt_method": "_enhance_characters_with_llm",
  "output_schema": {
    "type": "object",
    "fields": {
      "enhancements": {
        "type": "array",
        "items": {"role": "string", "description": "string", "motivation": "string"}
      },
      "missing_characters": {
        "type": "array",
        "items": {"label": "string", "role_type": "string", "description": "string", "motivation": "string"}
      }
    }
  },
  "variable_builders": {
    "facts_block": {
      "description": "Facts section text (first 2000 chars), or '(Facts section unavailable)' when the section is missing",
      "source": "document_sections query via NarrativeElementExtractor._load_case_facts"
    },
    "character_list": {
      "description": "Bulleted '- label: position' lines for the first 5 extracted characters ('Role' when no professional_position)",
      "source": "NarrativeCharacter list from the Phase 4.1 heuristic pass"
    },
    "obligations_list": {
      "description": "Bulleted labels of the first 5 case obligations",
      "source": "EntityFoundation.obligations"
    },
    "style_formatting_line": {
      "description": "Shared ProEthica no-em-dash output-style clause",
      "source": "app/services/prompt_style.py STYLE_FORMATTING_LINE"
    }
  }
}
---
Analyze these roles from an NSPE ethics case and provide brief character insights.

CASE FACTS:
{{ facts_block }}

ROLES ALREADY EXTRACTED:
{{ character_list }}

OBLIGATIONS IN THE CASE:
{{ obligations_list }}

Two tasks:

1. For each role in ROLES ALREADY EXTRACTED, provide a 1-sentence professional
   description and likely motivation.

2. MISSING-CHARACTER RESCAN. Read CASE FACTS and identify any present-case actor
   (a person, named party, or distinctly individuated role such as "Engineer B",
   "the Client", "the Contractor") who participates in the facts but is NOT already
   covered by ROLES ALREADY EXTRACTED. Do NOT invent actors, and do NOT include the
   Board of Ethical Review or generic ontology categories. Return each genuinely
   omitted actor in "missing_characters". Leave the array empty if none are missing.

{{ style_formatting_line }}

Output as JSON object:
```json
{
  "enhancements": [
    {"role": "Role label", "description": "...", "motivation": "..."}
  ],
  "missing_characters": [
    {"label": "Engineer B", "role_type": "stakeholder", "description": "...", "motivation": "..."}
  ]
}
```
