#!/usr/bin/env python3
"""
Backfill proethica-core v2.5.0 defeasibility edges
(competesWith, prevailsOver, defeasibleUnder) into the 117 non-72 case
ontologies whose extracted entities currently lack object-property triples
between competing obligations.

The per-case logic lives in
`app.services.extraction.defeasibility_pipeline.apply_defeasibility_edges`.
This script is the corpus-wide driver: it iterates the case TTLs in
OntServe/ontologies/, calls the pipeline helper for each, and writes a
checkpoint file so re-runs skip already-completed cases.

Usage:
    python scripts/backfill_defeasibility_edges.py [--dry-run] [--case-id N]
                                                  [--sample N] [--limit N]
                                                  [--restart]

Reference: proethica/.claude/plans/defeasibility-edge-extraction.md Phase C.
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Make the proethica package importable when run from anywhere.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))  # for /home/chris/onto


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backfill_defeasibility")


ONTOLOGIES_DIR = ROOT.parent / "OntServe" / "ontologies"
CHECKPOINT_PATH = Path(__file__).parent / ".backfill-defeasibility-checkpoint.json"


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

def load_checkpoint() -> Dict[str, Any]:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text())
    return {"completed": {}, "failed": {}, "started_at": None}


def save_checkpoint(state: Dict[str, Any]) -> None:
    CHECKPOINT_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
# Per-case driver
# ---------------------------------------------------------------------------

def backfill_one(
    case_id: int,
    extractor,
    dry_run: bool = False,
) -> Dict[str, Any]:
    from app.services.extraction.defeasibility_pipeline import (
        apply_defeasibility_edges,
        parse_case_ttl,
    )

    ttl_path = ONTOLOGIES_DIR / f"proethica-case-{case_id}.ttl"
    if not ttl_path.exists():
        return {"case_id": case_id, "status": "missing_ttl"}

    if dry_run:
        # Parse-only path: counts entities without spending an LLM call.
        entities = parse_case_ttl(ttl_path, case_id)
        log.info(
            "case %s: %d obligations, %d states, %d narrative strings",
            case_id, len(entities.obligations), len(entities.states),
            len(entities.narratives),
        )
        return {
            "case_id": case_id,
            "status": "dry_run",
            "obligations": len(entities.obligations),
            "states": len(entities.states),
            "narratives": len(entities.narratives),
        }

    result = apply_defeasibility_edges(
        case_id=case_id,
        ttl_path=ttl_path,
        extractor=extractor,
        write_back=True,
    )
    if result.get("status") == "ok":
        log.info(
            "case %s: emitted %d edges (added %d triples)",
            case_id, result["edges_emitted"], result["triples_added"],
        )
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def discover_cases() -> List[int]:
    """Return sorted list of case IDs found in OntServe/ontologies/."""
    case_ids: List[int] = []
    for f in ONTOLOGIES_DIR.glob("proethica-case-*.ttl"):
        try:
            cid = int(f.stem.split("-")[-1])
            case_ids.append(cid)
        except ValueError:
            continue
    return sorted(case_ids)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse cases and report counts; no LLM, no writes.")
    parser.add_argument("--case-id", type=int, default=None,
                        help="Run on a single case ID.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process only the first N candidate cases.")
    parser.add_argument("--sample", type=int, default=None,
                        help="Randomly sample N cases (Phase C3 dry-run).")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for --sample (default 42).")
    parser.add_argument("--skip-completed", action="store_true", default=True,
                        help="Skip cases already in checkpoint.completed.")
    parser.add_argument("--restart", action="store_true",
                        help="Ignore the checkpoint and re-run all cases.")
    parser.add_argument("--exclude-72", action="store_true", default=True,
                        help="Skip case 72 (already hand-annotated).")
    args = parser.parse_args()

    from app import create_app
    app = create_app()

    with app.app_context():
        from app.services.extraction.defeasibility_edges import DefeasibilityEdgeExtractor

        extractor = DefeasibilityEdgeExtractor()

        if args.case_id is not None:
            cases = [args.case_id]
        else:
            cases = discover_cases()
            if args.exclude_72:
                cases = [c for c in cases if c != 72]
            if args.sample:
                rng = random.Random(args.seed)
                cases = sorted(rng.sample(cases, min(args.sample, len(cases))))

        state = {"completed": {}, "failed": {}, "started_at": None}
        if not args.restart:
            state = load_checkpoint()
            if args.skip_completed:
                cases = [c for c in cases if str(c) not in state["completed"]]

        if not state.get("started_at"):
            state["started_at"] = datetime.now(timezone.utc).isoformat()

        if args.limit:
            cases = cases[: args.limit]

        log.info(
            "Backfilling %d cases (dry_run=%s, exclude_72=%s, sample=%s)",
            len(cases), args.dry_run, args.exclude_72, args.sample,
        )

        for cid in cases:
            log.info("--- case %s ---", cid)
            t0 = time.time()
            try:
                result = backfill_one(cid, extractor, dry_run=args.dry_run)
            except KeyboardInterrupt:
                log.warning("Interrupted; saving checkpoint before exit")
                save_checkpoint(state)
                return 130
            except Exception as e:
                log.exception("case %s: failed: %s", cid, e)
                state["failed"][str(cid)] = {
                    "error": str(e),
                    "at": datetime.now(timezone.utc).isoformat(),
                }
                save_checkpoint(state)
                continue

            result["elapsed_s"] = round(time.time() - t0, 2)
            log.info("  result: %s", result)

            terminal_ok = result["status"] in (
                "ok", "no_edges", "insufficient_obligations", "dry_run",
            )
            if terminal_ok:
                state["completed"][str(cid)] = result
            else:
                state["failed"][str(cid)] = result
            save_checkpoint(state)

    nok = sum(1 for r in state["completed"].values()
              if r.get("status") == "ok" and r.get("triples_added", 0) > 0)
    nempty = sum(1 for r in state["completed"].values()
                 if r.get("status") in ("no_edges", "insufficient_obligations"))
    nfail = len(state["failed"])
    log.info("DONE. ok-with-edges=%d empty=%d failed=%d", nok, nempty, nfail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
