"""Apply Jones (1991) moral-intensity ratings to every unrated tension of a case.

Single source of truth shared by:
  * the live Phase-4 post-pass (`run_step4_task`, study-corrections A5), and
  * the corpus backfill driver (`docs-internal/scripts/backfill_moral_intensity.py`).

Loads the case's latest `phase4_narrative` ExtractionPrompt JSON, finds the
`narrative_elements.conflicts` that carry no Jones dimension, rates them in one
batch call via MoralIntensityExtractor, merges the ratings back, and writes a
`moral_intensity_backfilled_at` provenance marker. Idempotent: conflicts that
already carry a rating are skipped, so a second run rates nothing.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from app.services.extraction.moral_intensity import (
    MoralIntensityExtractor,
    MoralIntensityTension,
    is_rated,
)

logger = logging.getLogger(__name__)


def apply_moral_intensity(
    case_id: int,
    extractor: Optional[Any] = None,
    dry_run: bool = False,
) -> Dict[str, int]:
    """Rate every unrated tension in the case's phase4_narrative JSON.

    Returns counters: total, already_rated, newly_rated, missed.
    Constructs a default MoralIntensityExtractor when none is supplied.
    """
    from app.models import db
    from app.models.extraction_prompt import ExtractionPrompt

    stats = {"total": 0, "already_rated": 0, "newly_rated": 0, "missed": 0}

    row = (
        ExtractionPrompt.query
        .filter_by(case_id=case_id, concept_type="phase4_narrative")
        .order_by(ExtractionPrompt.created_at.desc())
        .first()
    )
    if not row or not row.raw_response:
        logger.warning("case %s: no phase4_narrative row", case_id)
        return stats

    try:
        data = json.loads(row.raw_response)
    except (json.JSONDecodeError, TypeError):
        logger.error("case %s: phase4_narrative JSON failed to parse", case_id)
        return stats

    conflicts = (data.get("narrative_elements") or {}).get("conflicts") or []
    stats["total"] = len(conflicts)
    unrated = [c for c in conflicts if not is_rated(c)]
    stats["already_rated"] = stats["total"] - len(unrated)

    if not unrated:
        return stats

    # Stable conflict_id so ratings can be merged back by id.
    for i, c in enumerate(unrated):
        c.setdefault("conflict_id", f"tension_{i+1}")

    if dry_run:
        return stats

    if extractor is None:
        extractor = MoralIntensityExtractor()

    tensions = [
        MoralIntensityTension(
            conflict_id=c["conflict_id"],
            entity1_label=c.get("entity1_label", "?"),
            entity2_label=c.get("entity2_label", "?"),
            description=c.get("description", "") or "",
        )
        for c in unrated
    ]

    try:
        ratings_by_id = extractor.extract(case_id=case_id, tensions=tensions)
    except Exception as e:
        logger.error("case %s: moral-intensity LLM call failed: %s", case_id, e)
        return stats

    for c in unrated:
        rating = ratings_by_id.get(c.get("conflict_id"))
        if not rating:
            stats["missed"] += 1
            continue
        c.update(rating)
        stats["newly_rated"] += 1

    data["moral_intensity_backfilled_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    row.raw_response = json.dumps(data)
    db.session.add(row)
    db.session.commit()
    logger.info("case %s: moral-intensity rated %d, missed %d (of %d unrated; %d already rated)",
                case_id, stats["newly_rated"], stats["missed"], len(unrated), stats["already_rated"])
    return stats
