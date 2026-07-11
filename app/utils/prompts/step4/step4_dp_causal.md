---
{
  "name": "Step 4 Decision Points from Causal Links (Phase 3 fallback)",
  "description": "LLM fallback when E1-E3 algorithmic composition finds no decision-point candidates: generates 3-5 canonical decision points from the stored causal-normative links plus Q/C context. Post-render stages (normative-status append, MCP glossary enrichment) are applied in code.",
  "phase": "3",
  "extractor_file": "app/services/decision_point_synthesizer/strategies.py",
  "prompt_method": "LLMStrategiesMixin._llm_generate_from_causal_links",
  "output_schema": {
    "type": "array",
    "items": {
      "focus_id": "string, DPn",
      "description": "string",
      "decision_question": "string, 1-2 sentences",
      "role_label": "string, short identifier",
      "obligation_label": "string",
      "options": "[{option_id, label, description, is_board_choice}] with exactly one is_board_choice=true",
      "addresses_questions": "[Qn reference]",
      "board_resolution": "string, paraphrase of the conclusions",
      "toulmin_claim": "string",
      "toulmin_data": "string",
      "toulmin_warrants": "string",
      "toulmin_qualifier": "string, '' if unconditional",
      "toulmin_rebuttals": "string",
      "provision_labels": "[NSPE code section citation]",
      "intensity_score": "float 0.0-1.0",
      "qc_alignment_score": "float 0.0-1.0"
    }
  },
  "variable_builders": {
    "causal_links_block": {
      "description": "Numbered causal-normative link blocks (label, action, obligation, violates, description)",
      "source": "code-built in _llm_generate_from_causal_links from TemporaryRDFStorage causal_normative_link rows"
    },
    "questions_block": {
      "description": "Questions Q1..Qn (max 10, text capped at 400 chars)",
      "source": "code-built from the questions list"
    },
    "conclusions_block": {
      "description": "Conclusions C1..Cn (max 10, full text capped at 1200 chars; the earlier 200-char cap starved grounding, 2026-07-08)",
      "source": "code-built from the conclusions list"
    },
    "toulmin_field_spec": {
      "description": "Toulmin (1958) six-category field specification shared by all decision-point prompts",
      "source": "app.services.decision_point_synthesizer.strategies.TOULMIN_FIELD_SPEC"
    }
  }
}
---
You are analyzing an ethics case to identify key decision points where ethical choices must be made.

The E1-E3 algorithmic composition found no decision point candidates. However, the case analysis has identified
the following CAUSAL-NORMATIVE LINKS (relationships between actions and obligations):

{{ causal_links_block }}

ETHICAL QUESTIONS identified in the case:
{{ questions_block }}

BOARD CONCLUSIONS:
{{ conclusions_block }}

Based on these causal links, generate 3-5 canonical decision points. Each decision point should represent
a moment where an agent must choose between actions with ethical implications.

For each decision point, provide:
1. A focus_id (e.g., "DP1", "DP2")
2. A description of the decision situation
3. A decision_question (what choice must be made?)
4. The primary role/agent facing the decision
5. The relevant obligation or constraint
6. 2-3 options available to the decision-maker, with one marked as the Board's choice
7. Which question(s) this addresses (reference Q numbers)
8. How the board resolved it (reference C numbers)
9. The full Toulmin argument structure and backing provisions:
{{ toulmin_field_spec }}
10. intensity_score (float 0.0-1.0): moral intensity of this decision (urgency, magnitude of consequences, proximity)
11. qc_alignment_score (float 0.0-1.0): strength of alignment between this decision and the Questions/Conclusions

CRITICAL FORMATTING:
- Do NOT use em dash characters anywhere in your output. Use commas or periods instead.
- role_label must be a SHORT identifier for the decision-maker (e.g., "Engineer A", "Firm C", "Engineers A and B").
  Do NOT append obligation names, case descriptions, or topic keywords to the role_label.
  BAD: "Engineer A Construction Observation Engineer" or "Engineer H Public Hearing Testimony Completeness"
  GOOD: "Engineer A" or "Engineer H"
- decision_question should be concise (1-2 sentences). Frame as "Should [role] [action]?" or "Must [role] [choice]?"
- Option labels must be short action phrases (3-8 words), NEVER "Option A", "Option B", "Option C".
- Good labels: "Disclose AI Tool Usage", "Verify Code with Expert", "Withdraw from Project"
- Bad labels: "Option A", "Option B", "Alternative Approach"
- Descriptions expand on the label with case-specific detail.
- Exactly one option per decision point must have is_board_choice=true; the rest is_board_choice=false.

GROUNDING RULES (2026-07-08 Phase-B audit; each was a judged failure mode):
- is_board_choice marks the course the Board held to be the ETHICAL one. When the Board
  found the party's actual conduct unethical, the board choice is the compliant
  alternative (e.g. "Obtain Client Consent"), NOT the conduct that occurred. Never mark
  condemned conduct as the Board's choice.
- Options must be alternatives the case states or clearly implies were available to the
  decision-maker at that moment. Do NOT invent options the case never mentions or
  contemplates, and do not split one course of action into two near-identical options.
- board_resolution must paraphrase only what the Board's conclusions state. Do not add
  interpretive elaborations, carve-outs, or rationales the conclusions do not contain.
- toulmin_claim must agree with the option marked is_board_choice: the claim IS the
  board-endorsed course restated as an assertion (or the case-supported course when the
  Board made no determination).

Return as JSON array:
```json
[
  {
    "focus_id": "DP1",
    "description": "...",
    "decision_question": "...",
    "role_label": "...",
    "obligation_label": "...",
    "options": [
      {"option_id": "O1", "label": "Disclose X to Stakeholders", "description": "Formally notify all affected stakeholders of X through written communication", "is_board_choice": true},
      {"option_id": "O2", "label": "Withhold Disclosure of X", "description": "Continue without disclosure, relying on existing contractual scope limitations", "is_board_choice": false}
    ],
    "addresses_questions": ["Q1", "Q2"],
    "board_resolution": "The board concluded that... (C1)",
    "toulmin_claim": "The course of action argued for (1 sentence)",
    "toulmin_data": "The case facts appealed to (1-2 sentences, facts only)",
    "toulmin_warrants": "The general rules licensing facts to claim (1-2 sentences)",
    "toulmin_qualifier": "Modal strength or attached conditions ('' if unconditional)",
    "toulmin_rebuttals": "The conditions of exception, 'would not apply if ...' (1-2 sentences)",
    "provision_labels": ["II.1.f", "I.1"],
    "intensity_score": 0.78,
    "qc_alignment_score": 0.82
  }
]
```

