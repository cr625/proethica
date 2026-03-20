#!/usr/bin/env python3
"""
Neutralize scenario decision point questions for interactive traversal.

Rewrites evaluative/leading questions and options into neutrally framed
versions suitable for study participants. Stores results in the Phase 4
JSON alongside the original evaluative framing.

Usage:
    python scripts/neutralize_questions.py --case-ids 7
    python scripts/neutralize_questions.py --case-ids 7 8
    python scripts/neutralize_questions.py --all
    python scripts/neutralize_questions.py --case-ids 7 --dry-run
"""

import argparse
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def neutralize_case(case_id: int, dry_run: bool = False) -> bool:
    """Run neutralization for a single case."""
    from app.models import ExtractionPrompt, db
    from app.services.scenario_generation.question_neutralizer import (
        neutralize_branches, apply_neutralization_to_seeds
    )

    prompt = ExtractionPrompt.query.filter_by(
        case_id=case_id,
        concept_type='phase4_narrative'
    ).order_by(ExtractionPrompt.created_at.desc()).first()

    if not prompt or not prompt.raw_response:
        logger.warning(f"Case {case_id}: No Phase 4 data found")
        return False

    data = json.loads(prompt.raw_response)
    seeds = data.get('scenario_seeds', {})
    branches = seeds.get('branches', [])

    if not branches:
        logger.warning(f"Case {case_id}: No branches in scenario_seeds")
        return False

    # Check if already neutralized
    already_neutral = sum(1 for b in branches if b.get('neutral_question'))
    if already_neutral == len(branches):
        logger.info(f"Case {case_id}: Already fully neutralized ({already_neutral}/{len(branches)})")
        return True

    logger.info(f"Case {case_id}: Neutralizing {len(branches)} branches...")

    # Get case context for the LLM
    from app.models import Document
    case = Document.query.get(case_id)
    case_context = case.title if case else ""

    # Run neutralization
    neutralizations = neutralize_branches(branches, case_context)

    if dry_run:
        logger.info(f"Case {case_id}: DRY RUN -- showing results:")
        for i, n in enumerate(neutralizations):
            orig_q = branches[i].get('question', '')[:60]
            new_q = n['neutral_question'][:60]
            logger.info(f"  Branch {i}:")
            logger.info(f"    Original: {orig_q}...")
            logger.info(f"    Neutral:  {new_q}...")
            for opt in n['neutral_options']:
                logger.info(f"    Option (orig {opt['original_index']}): {opt['label'][:80]}")
        return True

    # Apply to seeds and save
    apply_neutralization_to_seeds(seeds, neutralizations)
    data['scenario_seeds'] = seeds
    prompt.raw_response = json.dumps(data)
    db.session.commit()

    neutral_count = sum(1 for b in branches if b.get('neutral_question'))
    logger.info(f"Case {case_id}: Neutralized {neutral_count}/{len(branches)} branches, saved to DB")
    return True


def main():
    parser = argparse.ArgumentParser(description="Neutralize scenario questions")
    parser.add_argument('--case-ids', nargs='+', type=int, help='Case IDs to neutralize')
    parser.add_argument('--all', action='store_true', help='Neutralize all cases with Phase 4 data')
    parser.add_argument('--dry-run', action='store_true', help='Show results without saving')
    args = parser.parse_args()

    if not args.case_ids and not args.all:
        parser.print_help()
        sys.exit(1)

    from app import create_app
    app = create_app()

    with app.app_context():
        if args.all:
            from app.models import ExtractionPrompt
            prompts = ExtractionPrompt.query.filter_by(
                concept_type='phase4_narrative'
            ).with_entities(ExtractionPrompt.case_id).distinct().all()
            case_ids = [p.case_id for p in prompts]
        else:
            case_ids = args.case_ids

        success = 0
        for case_id in case_ids:
            if neutralize_case(case_id, dry_run=args.dry_run):
                success += 1

        logger.info(f"Done: {success}/{len(case_ids)} cases processed")


if __name__ == '__main__':
    main()
