---
{
  "name": "Step 4 Board-Choice Verification (Phase 3 post-pass)",
  "description": "Single-purpose checker that verifies (and where needed overrides) is_board_choice on each decision point's options against the full board conclusions. Strict-JSON output; failures leave flags unchanged and are never fatal.",
  "phase": "3",
  "extractor_file": "app/services/decision_point_synthesizer/board_choice_verifier.py",
  "prompt_method": "verify_board_choices",
  "output_schema": {
    "type": "object",
    "properties": {
      "picks": "[{id: DPn, board_option_label: exact option label or null, reason: one clause}]"
    }
  },
  "variable_builders": {
    "concl_text": {
      "description": "Full board conclusions as '- <text>' bullet lines",
      "source": "code-built in verify_board_choices from the conclusions list (conclusion_text/text fields)"
    },
    "payload_json": {
      "description": "JSON array of decision points: id, decision question, option labels",
      "source": "json.dumps(payload, indent=1) built in verify_board_choices"
    }
  }
}
---
For each decision point below, identify which option is the course of action the
Board of Ethical Review held to be the ETHICAL one, based ONLY on the Board's conclusions.

Rules:
- The Board's choice is the conduct the Board endorsed or required. When the Board found
  the party's actual conduct unethical, the endorsed course is the compliant alternative,
  NEVER the condemned conduct.
- When the conclusions make no determination that selects among the options, return null.
- Return the option label EXACTLY as given.

BOARD CONCLUSIONS:
{{ concl_text }}

DECISION POINTS:
{{ payload_json }}

Return STRICT JSON only:
{"picks": [{"id": "DP1", "board_option_label": "<exact label or null>", "reason": "<one clause>"}]}
