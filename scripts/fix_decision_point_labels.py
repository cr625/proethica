#!/usr/bin/env python3
"""
Add short discrete labels to decision point options that only have descriptions.

Reads canonical_decision_point entities with options missing 'label' fields,
sends batches to the LLM to generate concise action-phrase labels, and updates
the rdf_json_ld in the database.

Usage:
    python scripts/fix_decision_point_labels.py              # All cases
    python scripts/fix_decision_point_labels.py --case 140   # Single case
    python scripts/fix_decision_point_labels.py --dry-run    # Preview without updating
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.utils.llm_utils import streaming_completion, get_llm_client
from app.utils.llm_json_utils import parse_json_response

MODEL = 'claude-sonnet-4-6'
from sqlalchemy import text


def get_cases_needing_labels():
    """Return list of case IDs with decision points missing labels."""
    rows = db.session.execute(text("""
        SELECT DISTINCT case_id
        FROM temporary_rdf_storage
        WHERE extraction_type = 'canonical_decision_point'
          AND (rdf_json_ld->'options'->0->>'label') IS NULL
        ORDER BY case_id
    """)).fetchall()
    return [r[0] for r in rows]


def get_decision_points(case_id):
    """Return list of (id, entity_label, rdf_json_ld) for a case's decision points."""
    rows = db.session.execute(text("""
        SELECT id, entity_label, rdf_json_ld
        FROM temporary_rdf_storage
        WHERE case_id = :cid AND extraction_type = 'canonical_decision_point'
          AND (rdf_json_ld->'options'->0->>'label') IS NULL
        ORDER BY entity_label
    """), {'cid': case_id}).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def build_label_prompt(decision_points):
    """Build a prompt asking the LLM to generate short labels for option descriptions."""
    dp_texts = []
    for i, (db_id, entity_label, data) in enumerate(decision_points):
        options = data.get('options', [])
        opt_lines = []
        for j, opt in enumerate(options):
            desc = opt.get('description', '')[:200]
            board = " [BOARD CHOICE]" if opt.get('is_board_choice') else ""
            opt_lines.append(f"    O{j+1}: {desc}{board}")

        dp_texts.append(f"  DP{i+1} (db_id={db_id}):\n" + "\n".join(opt_lines))

    prompt = f"""Generate short, discrete labels for each decision point option below.

RULES:
- Each label must be 3-8 words, Title Case, starting with a verb
- Labels must be DISCRETE CHOICES a decision-maker selects from a list
- Labels must be distinct enough to tell options apart at a glance
- Good: "Disclose Conflict to Client", "Recuse from Evaluation", "Report to State Agency"
- Bad: "Option A", long prose sentences, policy statements

Return JSON array with one object per decision point:
```json
[
  {{"db_id": 12345, "labels": ["Label for O1", "Label for O2", "Label for O3"]}},
  ...
]
```

Decision points:
{chr(10).join(dp_texts)}
"""
    return prompt


def generate_labels(decision_points):
    """Call LLM to generate labels for a batch of decision points."""
    prompt = build_label_prompt(decision_points)

    client = get_llm_client()
    response = streaming_completion(
        client=client,
        model=MODEL,
        max_tokens=4096,
        prompt=prompt,
        temperature=0.0,
    )

    results = parse_json_response(response, "decision point labels", strict=False)
    if not results:
        print(f"    WARNING: No JSON parsed from LLM response")
        return {}

    # Build db_id -> labels mapping
    label_map = {}
    for item in results:
        db_id = item.get('db_id')
        labels = item.get('labels', [])
        if db_id and labels:
            label_map[db_id] = labels

    return label_map


def apply_labels(decision_points, label_map, dry_run=False):
    """Update rdf_json_ld in the database with generated labels."""
    updated = 0
    for db_id, entity_label, data in decision_points:
        labels = label_map.get(db_id)
        if not labels:
            print(f"    SKIP {db_id}: no labels generated")
            continue

        options = data.get('options', [])
        if len(labels) != len(options):
            print(f"    SKIP {db_id}: label count ({len(labels)}) != option count ({len(options)})")
            continue

        # Add labels to options
        for opt, label in zip(options, labels):
            opt['label'] = label

        if dry_run:
            print(f"    DRY RUN {db_id}: {[l for l in labels]}")
        else:
            db.session.execute(text("""
                UPDATE temporary_rdf_storage
                SET rdf_json_ld = :data
                WHERE id = :id
            """), {'id': db_id, 'data': json.dumps(data)})
            updated += 1

    if not dry_run and updated > 0:
        db.session.commit()

    return updated


def process_case(case_id, dry_run=False):
    """Process all decision points for a single case."""
    dps = get_decision_points(case_id)
    if not dps:
        return 0

    print(f"  Case {case_id}: {len(dps)} decision points")

    # Batch in groups of 15 to stay within context limits
    BATCH_SIZE = 15
    total_updated = 0

    for batch_start in range(0, len(dps), BATCH_SIZE):
        batch = dps[batch_start:batch_start + BATCH_SIZE]
        t0 = time.time()
        label_map = generate_labels(batch)
        elapsed = time.time() - t0
        print(f"    Batch {batch_start//BATCH_SIZE + 1}: {len(label_map)}/{len(batch)} labeled in {elapsed:.0f}s")

        updated = apply_labels(batch, label_map, dry_run)
        total_updated += updated

    return total_updated


def main():
    parser = argparse.ArgumentParser(description='Fix decision point option labels')
    parser.add_argument('--case', type=int, help='Process a single case')
    parser.add_argument('--dry-run', action='store_true', help='Preview without updating')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.case:
            case_ids = [args.case]
        else:
            case_ids = get_cases_needing_labels()

        print(f"Processing {len(case_ids)} cases")
        total = 0
        for case_id in case_ids:
            updated = process_case(case_id, args.dry_run)
            total += updated

        action = "previewed" if args.dry_run else "updated"
        print(f"\nDone: {total} decision points {action}")


if __name__ == '__main__':
    main()
