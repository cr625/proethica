---
{
  "name": "Step 4 Decision Point Refinement (Phase 3)",
  "description": "Refines top-scoring algorithmic decision-point candidates into canonical decision points, preserving entity-URI grounding and aligning with the board's Q&C (Toulmin-annotated). Batched (5 per call); target_count is computed per batch in the builder; normative-status append and first-batch-only MCP enrichment are code stages.",
  "phase": "3",
  "extractor_file": "app/services/decision_point_synthesizer/strategies.py",
  "prompt_method": "LLMStrategiesMixin._build_refinement_prompt",
  "output_schema": {
    "type": "array",
    "items": {
      "focus_id": "string, DPn",
      "source_candidate_ids": "[candidate DPn ids merged into this point]",
      "description": "string",
      "decision_question": "string",
      "role_label": "string, short identifier",
      "role_uri": "URI from candidate",
      "obligation_label": "string",
      "obligation_uri": "URI",
      "constraint_label": "string or null",
      "constraint_uri": "URI or null",
      "provision_labels": "[NSPE code section citation]",
      "provision_uris": "[URI]",
      "involved_action_uris": "[action URI]",
      "toulmin_claim": "string",
      "toulmin_data": "string",
      "toulmin_warrants": "string",
      "toulmin_qualifier": "string, '' if unconditional",
      "toulmin_rebuttals": "string",
      "addresses_questions": "[Qn reference, 0-indexed]",
      "board_resolution": "string",
      "qc_alignment_score": "float 0.0-1.0",
      "intensity_score": "float 0.0-1.0",
      "options": "[{option_id, label, description, action_uri, is_board_choice}] with exactly one is_board_choice=true"
    }
  },
  "variable_builders": {
    "case_id": {
      "description": "Numeric case id, interpolated into the task header",
      "source": "builder argument"
    },
    "candidates_block": {
      "description": "Per-candidate blocks: focus_id with Q&C alignment score, description, question, role/obligation labels with URIs, matched questions, options with chosen/alternative tags",
      "source": "code-built in _build_refinement_prompt from (EntityGroundedDecisionPoint, QCAlignmentScore) pairs"
    },
    "questions_block": {
      "description": "Q0-indexed questions with URI and Toulmin annotations (DATA/WARRANTS/REBUTTAL) joined from question_emergence via qc_refs.key_aliases normalization",
      "source": "code-built in _build_refinement_prompt; QE/RP join keys normalized through qc_refs.key_aliases"
    },
    "conclusions_block": {
      "description": "C0-indexed conclusions with URI, determinative principles, and resolution narrative joined from resolution_patterns via qc_refs.key_aliases normalization",
      "source": "code-built in _build_refinement_prompt"
    },
    "toulmin_field_spec": {
      "description": "Toulmin (1958) six-category field specification shared by all decision-point prompts",
      "source": "app.services.decision_point_synthesizer.strategies.TOULMIN_FIELD_SPEC"
    },
    "target_count": {
      "description": "Requested decision-point count for this batch, e.g. '4-6' or '2-3'; computed per batch of 5 in _llm_refine",
      "source": "builder argument (per-batch computation stays in the builder)"
    }
  }
}
---
You are synthesizing decision points for NSPE ethics case {{ case_id }}.

## TOP ALGORITHMIC CANDIDATES (Scored by Q&C Alignment)

These candidates were composed algorithmically from extracted entities and scored against the board's actual questions and conclusions:

{{ candidates_block }}

## BOARD'S QUESTIONS (with Toulmin Analysis)

These are the actual ethical questions with their Toulmin structure:

{{ questions_block }}

## BOARD'S CONCLUSIONS (with Resolution Patterns)

{{ conclusions_block }}

## TASK

Synthesize {{ target_count }} decision points that:

1. **Preserve entity grounding** - Keep URI references from candidates
2. **Align with Q&C** - Each point should address real board concerns
3. **Merge similar candidates** - Combine candidates addressing the same issue
4. **Include the full Toulmin structure** - all six categories, each respecting
   its definition:
{{ toulmin_field_spec }}
5. **Coherent question-option structure** - Options must directly answer the question

CRITICAL FORMATTING REQUIREMENT:

- Do NOT use em dash characters anywhere in your output. Use commas or periods instead.

CRITICAL ROLE LABEL REQUIREMENT:

- The role_label must be a SHORT identifier for the decision-maker: "Engineer A", "Firm C",
  "Engineers A and B", "Client", etc. Do NOT append obligation names, case descriptions,
  or topic keywords to the role_label.
  - BAD: "Engineer A Construction Observation Engineer", "Engineer H Public Hearing Testimony Completeness ZZZ Truck Stop"
  - GOOD: "Engineer A", "Engineer H"
- The role_label must be the agent who faces the decision. Do not assign a decision to a party
  who is not making the choice (e.g., do not assign a disclosure decision to the "Client"
  when it is the engineer who must decide whether to disclose).

CRITICAL COHERENCE REQUIREMENT:

The decision_question, description, and options must form a coherent decision structure:

1. The "decision_question" must be framed as an actionable choice the named role faces:
   - Format: "Should [role] [action A] or [action B]?" or "Must [role] [choice]?"
   - The question must present the core tension between competing courses of action.
   - Keep it to 1-2 sentences. Do not embed long subordinate clauses.
   - BAD: "Whether the obligation arose at point X or point Y" (analytical, not actionable)
   - BAD: "The interaction between principle X and principle Y" (abstract, no agent choosing)
   - GOOD: "Should Engineer A disclose the conflict to the client before accepting the project, or rely on internal firewalls?"

2. Each option must be a DIRECT ANSWER to the decision_question. If you read the question
   then read each option, the option must be a plausible response the named role could choose.
   - BAD: Question asks "when did the obligation arise?" but options are "Submit Report" / "Limit Disclosure"
   - GOOD: Question asks "Should Doe submit full findings or limit disclosure?" and options are
     "Submit Full Report" / "Limit Disclosure to Correcting False Data" / "Seek Ethics Guidance First"

CRITICAL OPTION REQUIREMENTS:

1. Each option MUST have a short "label" (3-8 words, Title Case, action phrase starting with a verb)
   and a longer "description" (1-2 sentences elaborating the action).
   The label is a DISCRETE CHOICE that a decision-maker selects from a list.
   - Good labels: "Disclose Conflict to Client", "Recuse from Evaluation", "Report to State Agency"
   - Bad labels: "Option A", "Proactively disclose AI tool usage and identify AI-generated sections to client before submission"
   The label must be distinct enough to distinguish options at a glance.

2. Each decision point MUST have 2-3 options that represent GENUINELY DEFENSIBLE positions.
   Do NOT create straw-man alternatives. Each option should be an action a reasonable
   professional could plausibly choose given competing pressures (time, cost, client
   relationship, scope of duty, professional judgment).

   - BAD (straw-man negation):
     O1: "Conduct rigorous line-by-line review before sealing"
     O2: "Seal without any verification"
   - GOOD (genuine tension):
     O1: "Conduct full independent technical review of all AI outputs before sealing"
     O2: "Apply standard firm QA protocols to AI outputs at the same level as conventional CAD software"
     O3: "Engage a third-party reviewer with AI expertise for safety-critical elements while applying standard review to remaining outputs"

   The non-board-choice options must represent positions with real justifications
   (efficiency, precedent, scope limitation, competing obligations) -- not simply
   omitting or refusing to perform the ethical action.

## OUTPUT FORMAT (JSON)

```json
[
  {
    "focus_id": "DP1",
    "source_candidate_ids": ["DP1", "DP3"],
    "description": "Clear description",
    "decision_question": "The key ethical question",
    "role_label": "Engineer A",
    "role_uri": "URI from candidate",
    "obligation_label": "From candidate",
    "obligation_uri": "URI",
    "constraint_label": null,
    "constraint_uri": null,
    "provision_labels": ["II.1.c"],
    "provision_uris": ["URIs"],
    "involved_action_uris": ["action URIs"],
    "toulmin_claim": "The course of action argued for",
    "toulmin_data": "The case facts appealed to (facts only)",
    "toulmin_warrants": "The general rules licensing facts to claim",
    "toulmin_qualifier": "Modal strength or attached conditions ('' if unconditional)",
    "toulmin_rebuttals": "The conditions of exception, 'would not apply if ...'",
    "addresses_questions": ["Q0", "Q1"],
    "board_resolution": "How board resolved this",
    "qc_alignment_score": 0.85,
    "intensity_score": 0.7,
    "options": [
      {"option_id": "O1", "label": "Disclose AI Usage to Client Before Submission", "description": "Proactively disclose AI tool usage and identify AI-generated sections to client before submission", "action_uri": "URI", "is_board_choice": true},
      {"option_id": "O2", "label": "Treat AI as Internal Drafting Tool", "description": "Treat AI tool as internal drafting software equivalent to CAD, disclosing only upon direct client inquiry", "action_uri": "URI", "is_board_choice": false},
      {"option_id": "O3", "label": "Disclose in Project Documentation Only", "description": "Disclose AI usage in project documentation without separate client notification, following existing firm software disclosure policy", "action_uri": "URI", "is_board_choice": false}
    ]
  }
]
```

Produce exactly {{ target_count }} decision points capturing the key ethical issues. Do NOT produce more than the requested count.

