---
{
  "name": "Case Insight Derivation",
  "description": "Phase 4.4: derives 3 key takeaways, 1-2 novel aspects, and 1-2 limitations of the board's reasoning from the conflicts, resolution, transformation type, and applied principles.",
  "phase": "4",
  "extractor_file": "app/services/narrative/insight_deriver.py",
  "prompt_method": "_generate_insights_with_llm",
  "output_schema": {
    "type": "object",
    "fields": {
      "takeaways": {"type": "array", "items": "string (3 one-sentence takeaways)"},
      "novel_aspects": {
        "type": "array",
        "items": {"description": "string", "why_novel": "string"}
      },
      "limitations": {
        "type": "array",
        "items": {"description": "string", "affected_area": "reasoning|scope|applicability"}
      }
    }
  },
  "variable_builders": {
    "conflicts_desc": {
      "description": "Bulleted descriptions of the first 3 narrative conflicts",
      "source": "NarrativeElements.conflicts"
    },
    "resolution_desc": {
      "description": "Resolution summary (empty string when no resolution)",
      "source": "NarrativeElements.resolution.summary"
    },
    "transformation_type": {
      "description": "Phase 2 transformation classification, or 'unknown'",
      "source": "TransformationAnalysis.transformation_type"
    },
    "principles_desc": {
      "description": "Bulleted '- label: how_applied' lines for the first 3 applied principles",
      "source": "EthicalPrincipleApplied list"
    },
    "style_formatting_line": {
      "description": "Shared ProEthica no-em-dash output-style clause",
      "source": "app/services/prompt_style.py STYLE_FORMATTING_LINE"
    }
  }
}
---
Analyze this NSPE ethics case and derive insights.

CONFLICTS:
{{ conflicts_desc }}

RESOLUTION:
{{ resolution_desc }}

TRANSFORMATION TYPE: {{ transformation_type }}

PRINCIPLES IDENTIFIED:
{{ principles_desc }}

Provide:
1. 3 key takeaways (1 sentence each)
2. 1-2 novel aspects of this case (if any)
3. 1-2 limitations in the board's reasoning (if any)

{{ style_formatting_line }}

Output as JSON:
```json
{
  "takeaways": ["...", "...", "..."],
  "novel_aspects": [{"description": "...", "why_novel": "..."}],
  "limitations": [{"description": "...", "affected_area": "reasoning|scope|applicability"}]
}
```
