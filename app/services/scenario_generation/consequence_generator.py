"""
Consequence Generator (Stage 4.3b)

Generates pre-computed consequence narratives for every option at every
decision point in a case's scenario seeds. Runs during Phase 4 extraction,
not at interactive session runtime.

Input: ScenarioSeeds with branches/options populated (from Stage 4.3)
Output: Same ScenarioSeeds with consequence_narrative, consequence_obligations,
        consequence_fluent_changes, board_rationale, and competing_obligation_labels
        populated on each option and branch.
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional

from app.utils.llm_utils import get_llm_client
from model_config import ModelConfig
from app.services.narrative.scenario_seed_generator import (
    ScenarioSeeds, ScenarioBranch, ScenarioOption
)

logger = logging.getLogger(__name__)


def generate_consequences_for_seeds(
    seeds: ScenarioSeeds,
    causal_links: List[Dict],
    resolution: Dict,
    entity_lookup: Dict,
) -> None:
    """
    Populate consequence fields on all branches and options in-place.

    One LLM call per branch (decision point). Modifies the ScenarioSeeds
    object directly -- does not return a new object.

    Args:
        seeds: ScenarioSeeds with branches already populated (Stage 4.3 output)
        causal_links: List of causal link dicts from timeline
        resolution: Resolution dict from narrative_elements
        entity_lookup: Dict mapping URIs to entity dicts (for label resolution)
    """
    client = get_llm_client()

    for branch in seeds.branches:
        # Resolve obligation URIs to labels
        branch.competing_obligation_labels = [
            entity_lookup.get(uri, {}).get("label", uri.split("#")[-1] if "#" in uri else uri)
            for uri in branch.involved_obligation_uris
        ]

        # Build prompt and call LLM
        prompt = _build_consequence_prompt(
            branch=branch,
            causal_links=causal_links,
            resolution=resolution,
        )

        try:
            response = client.messages.create(
                model=ModelConfig.get_claude_model("default"),
                max_tokens=1000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text
            parsed = _parse_consequence_response(response_text, num_options=len(branch.options))
        except Exception as e:
            logger.error(f"Consequence generation failed for {branch.branch_id}: {e}")
            parsed = _parse_consequence_response("", num_options=len(branch.options))

        # Apply parsed data to branch and options
        branch.board_rationale = parsed["board_rationale"]

        for i, opt in enumerate(branch.options):
            if i < len(parsed["options"]):
                opt_data = parsed["options"][i]
                opt.consequence_narrative = opt_data.get("consequence_narrative", "")
                opt.consequence_obligations = opt_data.get("consequence_obligations", [])
                opt.consequence_fluent_changes = opt_data.get("consequence_fluent_changes", {})

    logger.info(
        f"Generated consequences for case {seeds.case_id}: "
        f"{len(seeds.branches)} branches, "
        f"{sum(len(b.options) for b in seeds.branches)} options"
    )


def _build_consequence_prompt(
    branch: ScenarioBranch,
    causal_links: List[Dict],
    resolution: Dict,
) -> str:
    """Build the LLM prompt for consequence generation for one decision point."""

    # Filter causal links relevant to this branch's options
    option_action_uris = set()
    for opt in branch.options:
        option_action_uris.update(opt.action_uris)

    relevant_links = [
        link for link in causal_links
        if link.get("source_uri", "") in option_action_uris
        or link.get("source_label", "") in [uri.split("#")[-1] for uri in option_action_uris if "#" in uri]
    ]

    links_text = ""
    if relevant_links:
        links_text = "## Causal Links (from case analysis)\n"
        for link in relevant_links:
            links_text += (
                f"- {link.get('source_label', '?')} "
                f"--[{link.get('link_type', '?')}]--> "
                f"{link.get('target_label', '?')}\n"
            )

    resolution_text = ""
    if resolution:
        resolution_text = f"## Board Resolution\n{resolution.get('summary', '')}\n"
        for c in resolution.get("conclusions", [])[:2]:
            resolution_text += f"- {c.get('text', '')[:300]}\n"

    options_text = ""
    for i, opt in enumerate(branch.options):
        board_marker = " [BOARD'S CHOICE]" if opt.is_board_choice else ""
        options_text += f"{i+1}. {opt.label}{board_marker}\n"
        if opt.description:
            options_text += f"   {opt.description}\n"

    return f"""Generate consequence narratives for each option at this decision point in a professional engineering ethics case.

## Decision Point
Decision maker: {branch.decision_maker_label}
Question: {branch.question}
Context: {branch.context}

## Options
{options_text}

{links_text}

{resolution_text}

## Task
For each option, generate:
1. A consequence narrative (2-3 sentences describing what follows from this choice)
2. A list of obligation labels that this choice activates or implicates
3. Fluent changes: what conditions are initiated (become true) and terminated (become false)

Also generate a board_rationale (2-3 sentences explaining why the board chose as they did).

Respond in JSON:
{{
    "options": [
        {{
            "option_id": "opt_N_M",
            "consequence_narrative": "...",
            "consequence_obligations": ["Obligation Label 1", "..."],
            "consequence_fluent_changes": {{
                "initiated": ["condition_1"],
                "terminated": ["condition_2"]
            }}
        }}
    ],
    "board_rationale": "..."
}}

Return one entry per option, in the same order as listed above."""


def _parse_consequence_response(response_text: str, num_options: int) -> Dict[str, Any]:
    """
    Parse LLM response into consequence data.

    Returns dict with 'options' list and 'board_rationale' string.
    On parse failure, returns empty defaults matching num_options.
    """
    empty_option = {
        "consequence_narrative": "",
        "consequence_obligations": [],
        "consequence_fluent_changes": {},
    }
    empty_result = {
        "options": [dict(empty_option) for _ in range(num_options)],
        "board_rationale": "",
    }

    if not response_text or not response_text.strip():
        return empty_result

    try:
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if not json_match:
            return empty_result

        data = json.loads(json_match.group())
        options = data.get("options", [])

        # Pad or truncate to match expected count
        while len(options) < num_options:
            options.append(dict(empty_option))
        options = options[:num_options]

        return {
            "options": [
                {
                    "consequence_narrative": opt.get("consequence_narrative", ""),
                    "consequence_obligations": opt.get("consequence_obligations", []),
                    "consequence_fluent_changes": opt.get("consequence_fluent_changes", {}),
                }
                for opt in options
            ],
            "board_rationale": data.get("board_rationale", ""),
        }

    except (json.JSONDecodeError, TypeError, KeyError) as e:
        logger.warning(f"Failed to parse consequence response: {e}")
        return empty_result
