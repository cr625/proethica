---
{
  "name": "Step 4 Causal-Normative Reasoning (Phase 2E)",
  "description": "Per-action normative-significance reasoning over the committed Step-3 fulfills/violates/guided-by edges and causal chains. The edges are GIVEN (never re-derived); the LLM returns only action_index-keyed reasoning sentences.",
  "phase": "2E",
  "extractor_file": "app/services/step4_synthesis/rich_analysis.py",
  "prompt_method": "RichAnalyzer._analyze_causal_batch",
  "output_schema": {
    "type": "array",
    "items": {
      "action_index": "int, 1-based A-number within the batch",
      "reasoning": "string, one grounded sentence",
      "confidence": "float 0.0-1.0"
    }
  },
  "variable_builders": {
    "actions_text": {
      "description": "GIVEN block: batch actions numbered A1..An, each with its committed fulfills/violates/guided-by edge lists ('none' when absent)",
      "source": "code-built in _analyze_causal_batch from _committed_action_edges(case_id) over committed Step-3 temporal Action rows"
    },
    "causal_text": {
      "description": "Step-3 CausalChain rows as 'cause -> effect (responsible: agent)' lines; empty string renders the '(none)' placeholder",
      "source": "RichAnalyzer._causal_chains_text(case_id) DB query over temporal_dynamics_enhanced rows"
    },
    "action_count": {
      "description": "Number of actions in this batch",
      "source": "len(batch_actions)"
    },
    "style_formatting_line": {
      "description": "Shared ProEthica no-em-dash output formatting clause",
      "source": "app.services.prompt_style.STYLE_FORMATTING_LINE"
    }
  }
}
---
These ACTIONS and their normative relations were ALREADY extracted from
this engineering-ethics case. The fulfills / violates / guided-by edges below are GIVEN -- do
not change or restate them. The CAUSAL CHAINS show what each action brings about.

## ACTIONS (with their committed normative edges)
{{ actions_text }}

## CAUSAL CHAINS (Step-3 causal extraction)
{{ causal_text or '  (none)' }}

For EACH action, write ONE sentence of REASONING explaining the normative significance of the
action in its causal context: why fulfilling or violating those obligations matters given
what the action causes downstream. Explain the edges; do not list them. Reference each action
by its A-number (action_index 1 for A1). Output JSON array:
```json
[
  {"action_index": 1, "reasoning": "One grounded sentence.", "confidence": 0.8}
]
```

Include all {{ action_count }} actions.

{{ style_formatting_line }}
