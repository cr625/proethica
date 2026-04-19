#!/usr/bin/env python3
"""
Backfill Jones (1991) moral-intensity ratings for ethical tensions in the
23-case study pool.

Problem: the Phase 4 narrative extractor historically asked the LLM for
"2-5 key tensions" with full ratings, then substring-matched those back
to the algorithmic tensions. Coverage on the study pool is ~20% as a
result (e.g., case 7 has 16 tensions but only 3 are rated).

Track A of this fix rewrites the extractor so new extractions rate every
tension. This script is Track B: it backfills the existing Phase 4 JSON
blobs for the 23 study-pool cases so the study view shows sensible
coverage without re-running Phase 4 end-to-end.

Input:  `extraction_prompts` rows where `concept_type = 'phase4_narrative'`
        and `case_id` is in STUDY_CASE_POOL_IDS.
Output: same rows, with each unrated conflict in
        `narrative_elements.conflicts` filled in via one LLM batch call
        per case. A `moral_intensity_backfilled_at` ISO timestamp is added
        to the top-level JSON for provenance.

Run: `python scripts/backfill_moral_intensity.py [--dry-run] [--case-id N]`
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Allow running from anywhere; this file lives in proethica/scripts/.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))  # for /home/chris/onto imports

from app import create_app, db
from app.models.extraction_prompt import ExtractionPrompt
from app.config.study_case_pool import STUDY_CASE_POOL_IDS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backfill_moral_intensity")


FIVE_DIMS = (
    "magnitude_of_consequences",
    "probability_of_effect",
    "temporal_immediacy",
    "proximity",
    "concentration_of_effect",
)


def is_rated(conflict: dict) -> bool:
    """A conflict is considered rated if any of the five Jones dimensions are non-null."""
    return any(conflict.get(k) for k in FIVE_DIMS)


def build_prompt(unrated: list[dict]) -> str:
    """Build a batch rating prompt for one case's unrated conflicts.

    We pass each tension's conflict_id, labels, and description so the LLM
    can rate each one and return the ratings keyed by conflict_id.
    """
    listed = "\n".join(
        f"[{c.get('conflict_id', f'tension_{i+1}')}] "
        f"{c.get('entity1_label', '?')} vs {c.get('entity2_label', '?')}"
        + (f": {c['description']}" if c.get('description') else '')
        for i, c in enumerate(unrated)
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


def rate_batch(unrated: list[dict], case_id: int) -> dict[str, dict]:
    """Call the LLM once to rate all unrated tensions for a case.

    Returns dict mapping conflict_id -> rating dict.
    """
    from app.utils.llm_utils import streaming_completion, get_llm_client
    from app.utils.llm_json_utils import parse_json_response
    from model_config import ModelConfig

    client = get_llm_client()
    if not client:
        raise RuntimeError("LLM client not available")

    prompt = build_prompt(unrated)
    log.info("  -> LLM batch rate: %d tensions, ~%d tokens in",
             len(unrated), len(prompt) // 4)

    response_text = streaming_completion(
        client,
        model=ModelConfig.get_claude_model("default"),
        max_tokens=1500,
        prompt=prompt,
        temperature=0.2,
    )
    parsed = parse_json_response(response_text, context="moral_intensity_backfill")

    if isinstance(parsed, dict):
        ratings = parsed.get("ratings") or []
    elif isinstance(parsed, list):
        ratings = parsed
    else:
        ratings = []

    by_id: dict[str, dict] = {}
    for r in ratings:
        cid = r.get("conflict_id")
        if cid:
            by_id[cid] = {k: r.get(k) for k in FIVE_DIMS if r.get(k)}
    return by_id


def backfill_case(case_id: int, dry_run: bool = False) -> dict[str, int]:
    """Load the latest phase4_narrative prompt for this case, fill intensity
    on unrated conflicts, persist back. Returns counters."""
    stats = {"total": 0, "already_rated": 0, "newly_rated": 0, "missed": 0}

    row = (
        ExtractionPrompt.query
        .filter_by(case_id=case_id, concept_type="phase4_narrative")
        .order_by(ExtractionPrompt.created_at.desc())
        .first()
    )
    if not row or not row.raw_response:
        log.warning("case %s: no phase4_narrative row", case_id)
        return stats

    try:
        data = json.loads(row.raw_response)
    except json.JSONDecodeError:
        log.error("case %s: phase4_narrative JSON failed to parse", case_id)
        return stats

    conflicts = (data.get("narrative_elements") or {}).get("conflicts") or []
    stats["total"] = len(conflicts)
    unrated = [c for c in conflicts if not is_rated(c)]
    stats["already_rated"] = stats["total"] - len(unrated)

    if not unrated:
        log.info("case %s: %d/%d already rated, skipping", case_id,
                 stats["already_rated"], stats["total"])
        return stats

    # Ensure each unrated conflict has a stable conflict_id (should already
    # be there; fall back to index-based if the extractor omitted it).
    for i, c in enumerate(unrated):
        c.setdefault("conflict_id", f"tension_{i+1}")

    if dry_run:
        log.info("case %s: DRY RUN, would rate %d/%d tensions", case_id,
                 len(unrated), stats["total"])
        return stats

    try:
        ratings_by_id = rate_batch(unrated, case_id)
    except Exception as e:
        log.error("case %s: LLM call failed: %s", case_id, e)
        return stats

    # Merge ratings into the originating conflict dicts (mutation is fine;
    # we write the whole JSON back in one shot below).
    for c in unrated:
        cid = c.get("conflict_id")
        rating = ratings_by_id.get(cid)
        if not rating:
            stats["missed"] += 1
            continue
        c.update(rating)
        stats["newly_rated"] += 1

    # Provenance marker at the top level so future readers can tell this
    # JSON was backfilled rather than produced in one pass.
    data["moral_intensity_backfilled_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    row.raw_response = json.dumps(data)
    db.session.add(row)
    db.session.commit()
    log.info("case %s: rated %d, missed %d (of %d unrated; %d already rated)",
             case_id, stats["newly_rated"], stats["missed"], len(unrated),
             stats["already_rated"])
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Count unrated tensions; do not call the LLM or write back.")
    parser.add_argument("--case-id", type=int, default=None,
                        help="Run on a single case ID instead of the whole pool.")
    args = parser.parse_args()

    case_ids = [args.case_id] if args.case_id else list(STUDY_CASE_POOL_IDS)
    log.info("Pool: %d cases (%s)", len(case_ids),
             ", ".join(str(c) for c in case_ids))

    app = create_app()
    totals = {"total": 0, "already_rated": 0, "newly_rated": 0, "missed": 0}
    with app.app_context():
        for cid in case_ids:
            log.info("--- case %s ---", cid)
            stats = backfill_case(cid, dry_run=args.dry_run)
            for k in totals:
                totals[k] += stats.get(k, 0)

    log.info("DONE. totals: %s", totals)
    return 0


if __name__ == "__main__":
    sys.exit(main())
