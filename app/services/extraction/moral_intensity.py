"""Moral-intensity (Jones 1991) per-tension extractor.

The Phase-4 narrative extractor historically asked the LLM for only "2-5 key
tensions" with full ratings, then substring-matched them back to the
algorithmically-derived tensions, leaving most tensions unrated (~20% coverage
on the study pool). This module rates EVERY tension on the five Jones (1991)
moral-intensity dimensions in one batch call.

Structurally mirrors the other focused extractors (temporal_sequence,
defeasibility_edges): a small input dataclass, a single LLM call, and a
validated dict result. Shared by:
  * the live Phase-4 post-pass (`apply_moral_intensity`, study-corrections A5), and
  * the corpus backfill driver (`docs-internal/scripts/backfill_moral_intensity.py`).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List

logger = logging.getLogger(__name__)

# The five Jones (1991) moral-intensity dimensions.
FIVE_DIMS = (
    "magnitude_of_consequences",
    "probability_of_effect",
    "temporal_immediacy",
    "proximity",
    "concentration_of_effect",
)


@dataclass
class MoralIntensityTension:
    """One ethical tension to be rated."""
    conflict_id: str
    entity1_label: str = "?"
    entity2_label: str = "?"
    description: str = ""


def is_rated(conflict: dict) -> bool:
    """True if any of the five Jones dimensions is already populated."""
    return any(conflict.get(k) for k in FIVE_DIMS)


def build_prompt(tensions: List[MoralIntensityTension]) -> str:
    listed = "\n".join(
        f"[{t.conflict_id}] {t.entity1_label} vs {t.entity2_label}"
        + (f": {t.description}" if t.description else "")
        for t in tensions
    )
    return f"""Rate each of these ethical tensions from an NSPE engineering ethics case on Jones (1991) moral-intensity dimensions.

TENSIONS TO RATE:
{listed}

For EACH tension above, use:
- magnitude_of_consequences: high | medium | low
- probability_of_effect: high | medium | low
- temporal_immediacy: immediate | near-term | long-term
- proximity: direct | indirect | remote
- concentration_of_effect: concentrated | diffuse

Output JSON with this exact shape:
```json
{{
  "ratings": [
    {{
      "conflict_id": "tension_1",
      "magnitude_of_consequences": "high",
      "probability_of_effect": "medium",
      "temporal_immediacy": "immediate",
      "proximity": "direct",
      "concentration_of_effect": "concentrated"
    }}
  ]
}}
```

Rate every tension in TENSIONS TO RATE. Do not omit any. Do not add new tensions."""


class MoralIntensityExtractor:
    """Rates every supplied tension on the five Jones dimensions in one call."""

    def __init__(self):
        self.last_prompt = None
        self.last_raw_response = None

    def extract(self, case_id: int, tensions: List[MoralIntensityTension]) -> Dict[str, dict]:
        """Return {conflict_id -> {dim: value, ...}} for the supplied tensions.

        Only non-empty dimension values are kept, so a partial LLM answer
        degrades gracefully (the caller treats an absent id as "missed").
        """
        if not tensions:
            return {}

        from app.utils.llm_utils import streaming_completion, get_llm_client
        from app.utils.llm_json_utils import parse_json_response
        from model_config import ModelConfig

        client = get_llm_client()
        if not client:
            raise RuntimeError("LLM client not available")

        prompt = build_prompt(tensions)
        self.last_prompt = prompt
        logger.info("moral-intensity rate: case %s, %d tensions", case_id, len(tensions))

        response_text = streaming_completion(
            client,
            model=ModelConfig.get_claude_model("default"),
            max_tokens=1500,
            prompt=prompt,
            temperature=0.2,
        )
        self.last_raw_response = response_text
        parsed = parse_json_response(response_text, context="moral_intensity")

        if isinstance(parsed, dict):
            ratings = parsed.get("ratings") or []
        elif isinstance(parsed, list):
            ratings = parsed
        else:
            ratings = []

        by_id: Dict[str, dict] = {}
        for r in ratings:
            cid = r.get("conflict_id")
            if cid:
                by_id[cid] = {k: r.get(k) for k in FIVE_DIMS if r.get(k)}
        return by_id
