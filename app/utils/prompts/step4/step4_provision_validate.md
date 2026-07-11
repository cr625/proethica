---
{
  "name": "Step 4 Provision Mention Validation",
  "description": "Phase 2A: validates that grouped provision mentions actually discuss the cited provision's content, in batches of up to 10 mentions per call.",
  "phase": "2A",
  "extractor_file": "app/services/provision/provision_group_validator.py",
  "prompt_method": "ProvisionGroupValidator._create_validation_prompt",
  "output_schema": {
    "type": "array",
    "items": {
      "mention_number": "int, 1-based, matches the MENTION n blocks",
      "is_relevant": "bool, true only if the excerpt discusses the provision's content",
      "confidence": "float 0.0-1.0",
      "content_type": "compliance | violation | interpretation | Board_reasoning | citation_only | background",
      "reasoning": "string, what content is being discussed"
    }
  },
  "variable_builders": {
    "provision_code": {
      "description": "NSPE Code provision identifier, e.g. II.4.e",
      "source": "validate_group caller (provisions parsed from the References section)"
    },
    "provision_text": {
      "description": "Full text of the provision",
      "source": "validate_group caller"
    },
    "mentions_text": {
      "description": "Preformatted MENTION blocks (section, citation, excerpt) for the batch",
      "source": "code-built loop over ProvisionMention objects in _create_validation_prompt"
    }
  }
}
---
You are validating that case text excerpts discuss a specific NSPE Code of Ethics provision.

**CODE PROVISION**: {{ provision_code }}
**PROVISION TEXT**: "{{ provision_text }}"

**TASK**: The excerpts below all explicitly mention provision {{ provision_code }}. For each excerpt, determine:

1. **Is it RELEVANT?** Does the excerpt discuss THIS provision's content/requirements?
   - Yes: If it discusses compliance, violation, interpretation, or application of {{ provision_code }}
   - No: If it only cites the number without discussing the content

2. **What is discussed?** (compliance, violation, interpretation, Board reasoning, etc.)

3. **Confidence**: How confident are you? (0.0-1.0)

**EXCERPTS TO VALIDATE**:
{{ mentions_text }}

**OUTPUT FORMAT** (JSON array):
```json
[
  {
    "mention_number": 1,
    "is_relevant": true,
    "confidence": 0.95,
    "content_type": "violation",
    "reasoning": "This excerpt discusses Engineer A's violation of {{ provision_code }} by accepting a contract while serving on the governmental body."
  },
  {
    "mention_number": 2,
    "is_relevant": false,
    "confidence": 0.85,
    "content_type": "citation_only",
    "reasoning": "This excerpt merely cites {{ provision_code }} without discussing what the provision requires or how it applies."
  }
]
```

**IMPORTANT**:
- "is_relevant": true only if the excerpt discusses the provision's CONTENT
- "content_type" options: compliance, violation, interpretation, Board_reasoning, citation_only, background
- Be specific in reasoning - explain what content is being discussed

