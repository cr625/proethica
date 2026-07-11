---
{
  "name": "Step 4 Decision Points from Q&C Direct (Phase 3 last-resort fallback)",
  "description": "Last-resort fallback when both E1-E3 composition and the causal-link fallback produce nothing: synthesizes 3-5 decision points directly from questions, conclusions, question emergence, resolution patterns, obligations, and roles. Post-render stages (normative-status append, MCP glossary enrichment) are applied in code.",
  "phase": "3",
  "extractor_file": "app/services/decision_point_synthesizer/strategies.py",
  "prompt_method": "LLMStrategiesMixin._llm_generate_from_qc_direct",
  "output_schema": {
    "type": "array",
    "items": {
      "focus_id": "string, DPn",
      "description": "string",
      "decision_question": "string, actionable choice",
      "role_label": "string, exact role label from the prompt",
      "obligation_label": "string, exact obligation label from the prompt",
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
    "questions_block": {
      "description": "Questions Q1..Qn with optional [source] tags (max 15, text capped at 250 chars)",
      "source": "code-built in _llm_generate_from_qc_direct from the questions list"
    },
    "conclusions_block": {
      "description": "Conclusions C1..Cn with optional [source] tags (max 15, text capped at 250 chars)",
      "source": "code-built from the conclusions list"
    },
    "qe_block": {
      "description": "Question-emergence lines 'QEn (re Qk): description[:200]' (max 10)",
      "source": "code-built from the question_emergence list"
    },
    "rp_block": {
      "description": "Resolution-pattern lines 'RPn (re Ck): description[:200]' (max 10)",
      "source": "code-built from the resolution_patterns list"
    },
    "obligations_block": {
      "description": "Obligations 'On: label -- definition[:150]' (max 15)",
      "source": "code-built from TemporaryRDFStorage obligations rows"
    },
    "roles_block": {
      "description": "Roles 'Rn: label' (max 10)",
      "source": "code-built from TemporaryRDFStorage roles rows"
    },
    "toulmin_field_spec": {
      "description": "Toulmin (1958) six-category field specification shared by all decision-point prompts",
      "source": "app.services.decision_point_synthesizer.strategies.TOULMIN_FIELD_SPEC"
    }
  }
}
---
You are analyzing an ethics case to identify key decision points where ethical choices must be made.

The algorithmic composition and causal link analysis found no decision point candidates for this case.
However, the case has rich analytical data. Synthesize decision points from the following context.

ETHICAL QUESTIONS identified in the case:
{{ questions_block }}

BOARD CONCLUSIONS:
{{ conclusions_block }}

QUESTION EMERGENCE (how ethical questions arise from case facts):
{{ qe_block }}

RESOLUTION PATTERNS (how the board resolved questions):
{{ rp_block }}

OBLIGATIONS extracted from the case:
{{ obligations_block }}

ROLES in the case:
{{ roles_block }}

Based on this analysis, generate 3-5 canonical decision points. Each should represent
a moment where an agent must choose between actions with ethical implications.

For each decision point, provide:
1. A focus_id (e.g., "DP1", "DP2")
2. A description of the decision situation
3. A decision_question -- an actionable choice framed as "Should [role] do X or Y?"
4. The primary role/agent facing the decision (use exact role labels from above)
5. The relevant obligation (use exact obligation labels from above)
6. 2-3 options that DIRECTLY ANSWER the decision_question, with one marked as the Board's choice
7. Which question(s) this addresses (reference Q numbers)
8. How the board resolved it (reference C numbers)
9. The full Toulmin argument structure and backing provisions:
{{ toulmin_field_spec }}
10. intensity_score (float 0.0-1.0): moral intensity of this decision (urgency, magnitude of consequences, proximity)
11. qc_alignment_score (float 0.0-1.0): strength of alignment between this decision and the Questions/Conclusions

CRITICAL FORMATTING:
- Do NOT use em dash characters anywhere in your output. Use commas or periods instead.
- role_label must be a SHORT identifier (e.g., "Engineer A", "Firm C"). Do NOT append topic descriptions.
  BAD: "Engineer D Bid Document Material Information Inclusion" GOOD: "Engineer D"

CRITICAL COHERENCE: The decision_question and options must form a coherent decision:
- The question must present an actionable choice the named role faces.
  BAD: "Whether the obligation arose at point X" (analytical, not a choice)
  GOOD: "Should Engineer Doe submit full findings or limit disclosure to correcting false data?"
- Each option must be a direct answer to that question. Reading the question then the option,
  the option must be a plausible course of action the role could choose.
- The role_label must be the agent making the decision, not a passive party.
- is_board_choice marks the course the Board held ETHICAL; when the Board condemned the
  actual conduct, the board choice is the compliant alternative, never the condemned act.
- Options must be alternatives the case states or implies; do not invent unmentioned ones.
- board_resolution paraphrases only what the conclusions state; toulmin_claim agrees
  with the option marked is_board_choice.

CRITICAL OPTION FORMAT:
- Labels must be 3-8 words, Title Case, starting with a verb. NEVER "Option A", "Option B".
- Good labels: "Disclose Conflict to Client", "Recuse from Project", "Seek Independent Review"
- Descriptions expand on the label with 1-2 sentences of case-specific detail.
- Options must represent genuinely defensible positions, not straw-man alternatives.
- Exactly one option per decision point must have is_board_choice=true; the rest is_board_choice=false.

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
      {"option_id": "O1", "label": "Disclose Conflict to Client", "description": "Formally notify the client of the conflict of interest and recommend independent oversight", "is_board_choice": true},
      {"option_id": "O2", "label": "Recuse from Project", "description": "Withdraw from the project entirely to avoid any appearance of compromised judgment", "is_board_choice": false}
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

