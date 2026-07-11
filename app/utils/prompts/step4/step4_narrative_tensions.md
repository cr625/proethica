---
{
  "name": "Ethical Tension Rating",
  "description": "Phase 4.1: rates every algorithmically detected ethical tension on the Jones (1991) moral-intensity dimensions, keyed by conflict_id, and may add up to 3 missed tensions.",
  "phase": "4",
  "extractor_file": "app/services/narrative/narrative_element_extractor.py",
  "prompt_method": "_enhance_tensions_with_llm",
  "output_schema": {
    "type": "object",
    "fields": {
      "ratings": {
        "type": "array",
        "items": {
          "conflict_id": "string (ID from EXISTING TENSIONS TO RATE)",
          "magnitude_of_consequences": "high|medium|low",
          "probability_of_effect": "high|medium|low",
          "temporal_immediacy": "immediate|near-term|long-term",
          "proximity": "direct|indirect|remote",
          "concentration_of_effect": "concentrated|diffuse"
        }
      },
      "additional": {
        "type": "array",
        "items": {
          "entity1_id": "string (URI fragment)",
          "entity1_label": "string",
          "entity1_type": "obligation|constraint",
          "entity2_id": "string (URI fragment)",
          "entity2_label": "string",
          "entity2_type": "obligation|constraint",
          "description": "string",
          "conflict_type": "obligation_vs_obligation|obligation_vs_constraint",
          "affected_roles": ["string"],
          "magnitude_of_consequences": "high|medium|low",
          "probability_of_effect": "high|medium|low",
          "temporal_immediacy": "immediate|near-term|long-term",
          "proximity": "direct|indirect|remote",
          "concentration_of_effect": "concentrated|diffuse"
        }
      }
    }
  },
  "variable_builders": {
    "obligations_list": {
      "description": "Bulleted '- [URI fragment] label' lines for the first 15 obligations",
      "source": "EntityFoundation.obligations"
    },
    "constraints_list": {
      "description": "Bulleted '- [URI fragment] label' lines for the first 15 constraints",
      "source": "EntityFoundation.constraints"
    },
    "roles_list": {
      "description": "Bulleted labels of the first 10 roles",
      "source": "EntityFoundation.roles"
    },
    "existing_tensions": {
      "description": "'[conflict_id] label1 vs label2: description' lines for ALL algorithmic tensions, or 'None identified yet'",
      "source": "NarrativeConflict list from the Phase 4.1 heuristic pass"
    },
    "style_formatting_line": {
      "description": "Shared ProEthica no-em-dash output-style clause",
      "source": "app/services/prompt_style.py STYLE_FORMATTING_LINE"
    }
  }
}
---
Analyze ethical tensions in an NSPE engineering ethics case. Each tension has an algorithmically assigned ID (e.g. tension_3). Rate every listed tension on Jones (1991) moral-intensity dimensions, and optionally add up to 3 additional tensions you judge the algorithmic pass missed.

OBLIGATIONS (duties the engineer must fulfill):
{{ obligations_list }}

CONSTRAINTS (limitations on what the engineer can do):
{{ constraints_list }}

ROLES INVOLVED:
{{ roles_list }}

EXISTING TENSIONS TO RATE (all of these):
{{ existing_tensions }}

For EACH existing tension above, return a rating keyed by its ID. For any additional tensions you identify, return them in the "additional" array with full entity details. Use these fields per Jones (1991):

- magnitude_of_consequences: high | medium | low (how serious are potential harms?)
- probability_of_effect: high | medium | low (how likely are negative outcomes?)
- temporal_immediacy: immediate | near-term | long-term (when will consequences occur?)
- proximity: direct | indirect | remote (how close is the decision-maker to the affected parties?)
- concentration_of_effect: concentrated | diffuse (are harms focused on a few parties or spread across many?)

Output JSON with this exact shape:
```json
{
  "ratings": [
    {
      "conflict_id": "tension_1",
      "magnitude_of_consequences": "high",
      "probability_of_effect": "medium",
      "temporal_immediacy": "immediate",
      "proximity": "direct",
      "concentration_of_effect": "concentrated"
    }
  ],
  "additional": [
    {
      "entity1_id": "URI fragment of first entity",
      "entity1_label": "Label of first entity",
      "entity1_type": "obligation or constraint",
      "entity2_id": "URI fragment of second entity",
      "entity2_label": "Label of second entity",
      "entity2_type": "obligation or constraint",
      "description": "Why these are in tension",
      "conflict_type": "obligation_vs_obligation or obligation_vs_constraint",
      "affected_roles": ["Role labels affected"],
      "magnitude_of_consequences": "high",
      "probability_of_effect": "medium",
      "temporal_immediacy": "immediate",
      "proximity": "direct",
      "concentration_of_effect": "concentrated"
    }
  ]
}
```

Rate every tension in EXISTING TENSIONS TO RATE. The "additional" array may be empty.

{{ style_formatting_line }}
