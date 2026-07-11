---
{
  "name": "Step 4 Board Conclusion Extraction (fallback)",
  "description": "Extracts the Board's explicit conclusions from the Conclusions section via LLM. Fallback path: used only when the imported conclusion_items are absent and the structural regex parse finds nothing. The board_conclusion_type enum (violation/compliance/no_violation/interpretation/recommendation) is stated in the prompt prose.",
  "phase": "2C",
  "extractor_file": "app/services/step4_synthesis/conclusion_analyzer.py",
  "prompt_method": "_create_board_extraction_prompt",
  "output_schema": {
    "format": "json_array",
    "item_fields": {
      "conclusion_number": "int, position in the Conclusions section",
      "conclusion_text": "verbatim conclusion text",
      "conclusion_type": "board_explicit",
      "board_conclusion_type": "violation | compliance | no_violation | interpretation | recommendation",
      "mentioned_entities": "{entity_type: [exact labels from the entity list]}",
      "cited_provisions": "[provision codes]",
      "extraction_reasoning": "brief explanation of the conclusion"
    }
  },
  "variable_builders": {
    "conclusions_text": {
      "description": "Raw Conclusions section text from the case document",
      "source": "caller argument (document section text)"
    },
    "entities_text": {
      "description": "All nine entity types formatted as label plus short definition",
      "source": "app.utils.entity_prompt_utils.format_entities_compact(all_entities)"
    },
    "provisions_text": {
      "description": "CODE PROVISIONS EXTRACTED block (up to 10 provisions, 100-char text cap); empty string when none",
      "source": "ConclusionAnalyzer._format_provisions(code_provisions)"
    }
  }
}
---
You are analyzing the Conclusions section from an NSPE Board of Ethical Review case.

**CONCLUSIONS SECTION TEXT:**
{{ conclusions_text }}

**EXTRACTED CASE ENTITIES:**
{{ entities_text }}

{{ provisions_text }}

**TASK:**
Extract ONLY the Board's explicit conclusions (their formal determinations on each question).
These are the conclusions the Board reached on the ethical issues.

For each conclusion:
1. **Conclusion Text**: The verbatim conclusion text
2. **Mentioned Entities**: Which entities from the case are referenced? Use exact labels from the list above.
3. **Cited Provisions**: Which code provisions are cited in the reasoning?
4. **Board Conclusion Type**: What kind of conclusion?
   - 'violation': Found a violation of ethics code
   - 'compliance': Found compliance with ethics code
   - 'no_violation': Found no violation occurred
   - 'interpretation': Clarifies interpretation of provision
   - 'recommendation': Recommends action
5. **Reasoning**: Brief explanation of the conclusion

**OUTPUT FORMAT (JSON):**
```json
[
  {
    "conclusion_number": 1,
    "conclusion_text": "Engineer A violated Section II.4.e by accepting the contract.",
    "conclusion_type": "board_explicit",
    "board_conclusion_type": "violation",
    "mentioned_entities": {
      "roles": ["Engineer A"],
      "actions": ["accepting the contract"]
    },
    "cited_provisions": ["II.4.e"],
    "extraction_reasoning": "The Board found a violation based on the conflict of interest."
  }
]
```

Extract ALL conclusions the Board reached. Use EXACT entity labels from the lists above.

