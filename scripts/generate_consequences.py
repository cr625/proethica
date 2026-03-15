"""
Batch generate consequence data for existing cases.

Usage:
    python scripts/generate_consequences.py              # All cases with Phase 4 data
    python scripts/generate_consequences.py --case-ids 7 25 102  # Specific cases
    python scripts/generate_consequences.py --dry-run    # Preview without saving
"""
import argparse
import json
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, ExtractionPrompt, TemporaryRDFStorage
from app.services.scenario_generation.consequence_generator import (
    generate_consequences_for_seeds,
)
from app.services.narrative.scenario_seed_generator import (
    ScenarioSeeds, ScenarioBranch, ScenarioOption,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def load_seeds_from_json(data: dict) -> ScenarioSeeds:
    """Reconstruct ScenarioSeeds from stored JSON."""
    seeds_data = data.get('scenario_seeds', {})
    branches = []
    for b in seeds_data.get('branches', []):
        options = [
            ScenarioOption(
                option_id=o.get('option_id', ''),
                label=o.get('label', ''),
                description=o.get('description', ''),
                action_uris=o.get('action_uris', []),
                is_board_choice=o.get('is_board_choice', False),
                leads_to=o.get('leads_to'),
                consequence_narrative=o.get('consequence_narrative', ''),
                consequence_obligations=o.get('consequence_obligations', []),
                consequence_fluent_changes=o.get('consequence_fluent_changes', {}),
            )
            for o in b.get('options', [])
        ]
        branches.append(ScenarioBranch(
            branch_id=b.get('branch_id', ''),
            context=b.get('context', ''),
            question=b.get('question', ''),
            decision_point_uri=b.get('decision_point_uri', ''),
            decision_maker_uri=b.get('decision_maker_uri', ''),
            decision_maker_label=b.get('decision_maker_label', ''),
            involved_obligation_uris=b.get('involved_obligation_uris', []),
            options=options,
            board_rationale=b.get('board_rationale', ''),
            competing_obligation_labels=b.get('competing_obligation_labels', []),
        ))

    return ScenarioSeeds(
        case_id=seeds_data.get('case_id', 0),
        opening_context=seeds_data.get('opening_context', ''),
        initial_state_description=seeds_data.get('initial_state_description', ''),
        protagonist_uri=seeds_data.get('protagonist_uri', ''),
        protagonist_label=seeds_data.get('protagonist_label', ''),
        branches=branches,
        canonical_path=seeds_data.get('canonical_path', []),
        transformation_type=seeds_data.get('transformation_type', ''),
    )


def main():
    parser = argparse.ArgumentParser(description='Batch generate consequence data')
    parser.add_argument('--case-ids', nargs='+', type=int, help='Specific case IDs')
    parser.add_argument('--dry-run', action='store_true', help='Preview without saving')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        query = ExtractionPrompt.query.filter_by(concept_type='phase4_narrative')
        if args.case_ids:
            query = query.filter(ExtractionPrompt.case_id.in_(args.case_ids))

        prompts = query.order_by(ExtractionPrompt.case_id).all()
        # Deduplicate: keep latest per case_id
        seen = {}
        for p in prompts:
            if p.case_id not in seen or p.created_at > seen[p.case_id].created_at:
                seen[p.case_id] = p
        prompts = list(seen.values())

        logger.info(f"Processing {len(prompts)} cases")

        for prompt in prompts:
            try:
                data = json.loads(prompt.raw_response)
                seeds = load_seeds_from_json(data)

                if not seeds.branches:
                    logger.warning(f"Case {prompt.case_id}: no branches, skipping")
                    continue

                # Check if consequences already generated
                first_opt = seeds.branches[0].options[0] if seeds.branches[0].options else None
                if first_opt and first_opt.consequence_narrative:
                    logger.info(f"Case {prompt.case_id}: consequences already present, skipping")
                    continue

                # Load supporting data
                causal_links_raw = TemporaryRDFStorage.query.filter_by(
                    case_id=prompt.case_id, extraction_type='causal_normative_link'
                ).all()
                causal_links = [
                    link.rdf_json_ld if link.rdf_json_ld else {}
                    for link in causal_links_raw
                ]

                resolution = data.get('narrative_elements', {}).get('resolution', {})

                entity_lookup = {}
                for etype in ['Obligations', 'Principles', 'Constraints']:
                    entities = TemporaryRDFStorage.query.filter_by(
                        case_id=prompt.case_id, entity_type=etype
                    ).all()
                    for e in entities:
                        if e.entity_uri:
                            entity_lookup[e.entity_uri] = {'label': e.entity_label or ''}

                logger.info(f"Case {prompt.case_id}: {len(seeds.branches)} branches, "
                           f"{len(causal_links)} causal links")

                if args.dry_run:
                    logger.info(f"  [DRY RUN] Would generate consequences")
                    continue

                generate_consequences_for_seeds(
                    seeds=seeds,
                    causal_links=causal_links,
                    resolution=resolution,
                    entity_lookup=entity_lookup,
                )

                # Write back to JSON
                data['scenario_seeds'] = seeds.to_dict()
                prompt.raw_response = json.dumps(data)
                db.session.commit()

                logger.info(f"Case {prompt.case_id}: consequences generated and saved")

            except Exception as e:
                logger.error(f"Case {prompt.case_id}: failed - {e}")
                db.session.rollback()

        logger.info("Done")


if __name__ == '__main__':
    main()
