---
{
  "name": "Timeline Event Enhancement",
  "description": "Phase 4.2: rewrites the first 8 timeline event descriptions into clearer 1-2 sentence narrative descriptions, returned by event number.",
  "phase": "4",
  "extractor_file": "app/services/narrative/timeline_constructor.py",
  "prompt_method": "_enhance_timeline_with_llm",
  "output_schema": {
    "type": "array",
    "items": {
      "event_number": "integer (1-based index into TIMELINE EVENTS)",
      "enhanced_description": "string"
    }
  },
  "variable_builders": {
    "event_list": {
      "description": "Numbered 'n. [phase] label: description[:100]...' lines for the first 8 timeline events",
      "source": "TimelineEvent list from the Phase 4.2 Event Calculus construction"
    },
    "style_formatting_line": {
      "description": "Shared ProEthica no-em-dash output-style clause",
      "source": "app/services/prompt_style.py STYLE_FORMATTING_LINE"
    }
  }
}
---
Enhance these timeline events from an NSPE ethics case with clearer, more narrative descriptions.

TIMELINE EVENTS:
{{ event_list }}

For each event, provide a clearer 1-2 sentence description that:
1. Uses professional but accessible language
2. Explains the significance of the event
3. Maintains objective tone

{{ style_formatting_line }}

Output as JSON array:
```json
[
  {"event_number": 1, "enhanced_description": "..."}
]
```
