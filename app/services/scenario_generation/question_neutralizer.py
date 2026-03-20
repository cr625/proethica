"""
Question Neutralizer (Stage 4.3c)

Rewrites evaluative decision-point questions and leading option labels into
neutrally framed versions suitable for study participants.

The raw evaluative framing from Phase 3 ("Did Engineer A violate...") is
preserved for computational analysis. The neutralized versions are stored
as additional fields on each branch and option, used by the interactive
traversal UI.

Design principles:
- Questions should present a genuine dilemma, not a verdict
- Each option should articulate a legitimate position with real tradeoffs
- Option order is randomized so the board choice is not always first
- The substance and ethical stakes are preserved; only the framing changes
"""

import json
import logging
import random
import re
from typing import Dict, List, Any

from app.utils.llm_utils import get_llm_client
from model_config import ModelConfig

logger = logging.getLogger(__name__)


def neutralize_branches(branches: List[Dict], case_context: str = "") -> List[Dict]:
    """
    Generate neutralized question/option framing for a list of branches.

    Args:
        branches: List of branch dicts from scenario_seeds
        case_context: Brief case description for LLM context

    Returns:
        List of neutralization dicts, one per branch, each containing:
        - neutral_question: Reframed question
        - neutral_options: List of {label, description, original_index}
        - option_order: Mapping from display position to original option index
    """
    client = get_llm_client()
    results = []

    for i, branch in enumerate(branches):
        try:
            prompt = _build_neutralization_prompt(branch, case_context)
            response = client.messages.create(
                model=ModelConfig.get_claude_model("default"),
                max_tokens=1500,
                temperature=0.4,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text
            parsed = _parse_neutralization_response(response_text, branch)
        except Exception as e:
            logger.error(f"Neutralization failed for branch {i}: {e}")
            parsed = _fallback_neutralization(branch)

        results.append(parsed)
        logger.debug(f"Neutralized branch {i}: {parsed['neutral_question'][:60]}...")

    logger.info(f"Neutralized {len(results)} branches")
    return results


def apply_neutralization_to_seeds(seeds_dict: Dict, neutralizations: List[Dict]) -> Dict:
    """
    Apply neutralization results to a scenario_seeds dict.

    Adds neutral_question, neutral_options, and option_order fields to
    each branch. Does not modify existing fields.

    Args:
        seeds_dict: The scenario_seeds dict from Phase 4 JSON
        neutralizations: Output from neutralize_branches()

    Returns:
        Modified seeds_dict with neutralization fields added
    """
    branches = seeds_dict.get('branches', [])
    for i, branch in enumerate(branches):
        if i < len(neutralizations):
            n = neutralizations[i]
            branch['neutral_question'] = n['neutral_question']
            branch['neutral_options'] = n['neutral_options']
            branch['option_order'] = n['option_order']
    return seeds_dict


def _build_neutralization_prompt(branch: Dict, case_context: str) -> str:
    """Build prompt for neutralizing one decision point."""
    options = branch.get('options', [])

    options_text = ""
    for i, opt in enumerate(options):
        board = " [BOARD'S ACTUAL CHOICE]" if opt.get('is_board_choice') else ""
        options_text += f"{i+1}. {opt.get('label', '')}{board}\n"
        if opt.get('description'):
            options_text += f"   Description: {opt['description'][:200]}\n"

    obligations_text = ""
    obligations = branch.get('competing_obligation_labels', [])
    if obligations:
        obligations_text = f"Competing obligations: {', '.join(obligations)}\n"

    return f"""Rewrite this ethics case decision point for use in a research study where
participants must choose between options WITHOUT knowing which the ethics board selected.

## Current (evaluative) framing
Decision maker: {branch.get('decision_maker_label', '')}
Question: {branch.get('question', '')}
{obligations_text}
Options:
{options_text}

## Requirements
1. QUESTION: Rewrite as a concise neutral "How should X handle/approach..." dilemma
   (ONE sentence, max 25 words). Focus on the core ethical tension only.
   Do NOT recapitulate scenario facts -- participants have already read the
   narrative. Remove all evaluative language (violated, failed, breach,
   negligent, inconsistency). Do not reveal which option the board chose.
   BAD:  "How should Engineer A handle the use of an AI tool that generated
         the prose of a report submitted under seal when the client notices
         a stylistic inconsistency?" (too long, embeds facts, leading)
   GOOD: "How should Engineer A approach disclosure of AI tools used in
         preparing a client deliverable?" (concise, neutral, dilemma-focused)

2. OPTIONS: Rewrite each option as a defensible professional position.
   - Label: Short action phrase (5-12 words), no loaded terms
   - Description: Exactly ONE sentence stating the core rationale/tradeoff
   Each option must use neutral professional language and present a
   legitimate position. The non-board option should be a steelman: the
   strongest reasonable argument for that position, not a strawman.

3. Keep option substance aligned with the originals (same core action),
   but frame both sides charitably.

Respond in JSON:
{{
    "neutral_question": "How should [Actor]...",
    "options": [
        {{
            "original_index": 0,
            "label": "Short action phrase",
            "description": "One sentence rationale with tradeoff."
        }},
        {{
            "original_index": 1,
            "label": "Short action phrase",
            "description": "One sentence rationale with tradeoff."
        }}
    ]
}}

Return options in RANDOMIZED order (do not always put original option 0 first)."""


def _parse_neutralization_response(response_text: str, branch: Dict) -> Dict:
    """Parse LLM neutralization response."""
    # Extract JSON from response
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if not json_match:
        logger.warning("No JSON found in neutralization response")
        return _fallback_neutralization(branch)

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        logger.warning("Failed to parse neutralization JSON")
        return _fallback_neutralization(branch)

    neutral_question = data.get('neutral_question', '')
    raw_options = data.get('options', [])

    if not neutral_question or len(raw_options) < 2:
        return _fallback_neutralization(branch)

    # Build option_order mapping: display_position -> original_index
    neutral_options = []
    option_order = []
    for opt in raw_options:
        orig_idx = opt.get('original_index', len(neutral_options))
        neutral_options.append({
            'label': opt.get('label', ''),
            'description': opt.get('description', ''),
            'original_index': orig_idx,
        })
        option_order.append(orig_idx)

    return {
        'neutral_question': neutral_question,
        'neutral_options': neutral_options,
        'option_order': option_order,
    }


def _fallback_neutralization(branch: Dict) -> Dict:
    """
    Minimal neutralization when LLM fails: strip obvious evaluative
    prefixes and randomize option order.
    """
    question = branch.get('question', '')
    # Strip leading evaluative framing
    for prefix in ['Did ', 'Does ', 'Should ']:
        if question.startswith(prefix):
            question = 'How should ' + question[len(prefix):]
            break

    options = branch.get('options', [])
    indices = list(range(len(options)))
    random.shuffle(indices)

    neutral_options = []
    for display_pos, orig_idx in enumerate(indices):
        opt = options[orig_idx] if orig_idx < len(options) else {}
        neutral_options.append({
            'label': opt.get('label', ''),
            'description': opt.get('description', ''),
            'original_index': orig_idx,
        })

    return {
        'neutral_question': question,
        'neutral_options': neutral_options,
        'option_order': indices,
    }
