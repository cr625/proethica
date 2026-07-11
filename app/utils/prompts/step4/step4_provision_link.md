---
{
  "name": "Step 4 Provision-to-Entity Linking",
  "description": "Phase 2A: links NSPE Code provisions to extracted case entities. ONE template fanned into up to 9 parallel per-entity-type calls; the per-type applicability sentence comes from the type_descriptions dict in the builder.",
  "phase": "2A",
  "extractor_file": "app/services/provision/code_provision_linker.py",
  "prompt_method": "CodeProvisionLinker._create_batch_linking_prompt",
  "output_schema": {
    "type": "array",
    "items": {
      "code_provision": "string, provision code exactly as listed, e.g. I.1",
      "applies_to": [
        {
          "entity_label": "string, exact entity label from the list",
          "reasoning": "string, one short sentence"
        }
      ]
    }
  },
  "variable_builders": {
    "provisions_text": {
      "description": "Numbered provision list (code + text), one per line",
      "source": "code-built loop over provisions in _create_batch_linking_prompt"
    },
    "type_label": {
      "description": "Plural display label of the entity type for this call, e.g. Roles",
      "source": "entity_groups fan-out in link_provisions_to_entities"
    },
    "entities_text": {
      "description": "Preformatted entity list with 150-char-truncated definitions",
      "source": "CodeProvisionLinker._format_entities_for_prompt"
    },
    "entity_type": {
      "description": "Singular entity type key for this call, e.g. role",
      "source": "entity_groups fan-out in link_provisions_to_entities"
    },
    "applicability": {
      "description": "Per-type applicability sentence",
      "source": "type_descriptions dict in _create_batch_linking_prompt (stays in code)"
    },
    "case_summary": {
      "description": "Brief case summary; empty string selects the default context sentence",
      "source": "caller (Case id + title)"
    }
  }
}
---
Link NSPE Code provisions to extracted {{ type_label }} entities from this engineering ethics case.

**Case Context:**
{% if case_summary %}{{ case_summary }}{% else %}Engineering professional ethics case.{% endif %}

**NSPE Code Provisions (Board-Selected):**
{{ provisions_text }}

**{{ type_label }} Entities:**
{{ entities_text }}

A provision applies to a {{ entity_type }} entity if: {{ applicability }}

For each provision, list which {{ type_label | lower }} entities it applies to (if any). Only include clear, direct connections.

Respond ONLY with a JSON array (no other text). Keep each reasoning value to a single short sentence with no special characters or line breaks.

```json
[
  {
    "code_provision": "I.1",
    "applies_to": [
      {"entity_label": "Example Entity", "reasoning": "Brief reason in one sentence"}
    ]
  }
]
```

Use exact entity labels. Omit provisions with no links to these entities.
