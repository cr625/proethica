#!/usr/bin/env python3
"""
Recompute divergent_components.csv using paper-weight full-formula ranking.

The original per_component_similarity.py selected top-10 neighbors using
embedding-only ranking (9 component cosines, no set features) and freshly
generated embeddings. This script uses:
1. Pre-stored embeddings from case_precedent_features (consistent with all
   other paper experiments)
2. Paper-weight full-formula ranking (0.40 embedding + 0.60 set-based)
   for neighbor selection

Reports which neighbors changed and regenerates the CSV.
"""

import os
import csv
from datetime import datetime

import numpy as np

from app import create_app
from app.models import Document, db
from app.services.precedent.similarity_service import PrecedentSimilarityService
from app.services.precedent.case_feature_extractor import COMPONENT_WEIGHTS
from sqlalchemy import text


# Paper weights
PAPER_W = {
    'embedding': 0.40,
    'provision_overlap': 0.25,
    'outcome_alignment': 0.15,
    'tag_overlap': 0.10,
    'principle_overlap': 0.10,
}

COMPONENT_ORDER = ['R', 'P', 'O', 'S', 'Rs', 'A', 'E', 'Ca', 'Cs']

COMPONENT_LABELS = {
    'R': 'Roles', 'P': 'Principles', 'O': 'Obligations',
    'S': 'States', 'Rs': 'Resources', 'A': 'Actions',
    'E': 'Events', 'Ca': 'Capabilities', 'Cs': 'Constraints',
}


def load_all_features(service):
    """Load features for all cases with complete embeddings."""
    rows = db.session.execute(text("""
        SELECT case_id FROM case_precedent_features
        WHERE facts_embedding IS NOT NULL
          AND combined_embedding IS NOT NULL
    """)).fetchall()
    case_ids = sorted(r[0] for r in rows)
    features = {}
    for cid in case_ids:
        f = service._get_case_features(cid)
        if f is not None:
            features[cid] = f
    return features


def cosine_sim(vec1, vec2):
    if vec1 is None or vec2 is None:
        return 0.0
    v1 = np.asarray(vec1).flatten()
    v2 = np.asarray(vec2).flatten()
    if len(v1) != len(v2):
        return 0.0
    n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    return float(np.dot(v1, v2) / (n1 * n2))


def jaccard(set_a, set_b):
    if not set_a and not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union > 0 else 0.0


def outcome_alignment(a, b):
    if a is None or b is None:
        return 0.5
    if a == b:
        return 1.0
    if {a, b} == {'ethical', 'unethical'}:
        return 0.0
    return 0.5


def principle_overlap(tensions_a, tensions_b):
    if not tensions_a or not tensions_b:
        return 0.0
    def extract(tensions):
        p = set()
        for t in tensions:
            if isinstance(t, dict):
                p.add(t.get('principle1', ''))
                p.add(t.get('principle2', ''))
        p.discard('')
        return p
    return jaccard(extract(tensions_a), extract(tensions_b))


def compute_paper_weight_score(src, tgt):
    """Full-formula per-component score using paper weights.

    Returns (overall_score, component_similarity, per_component_cosines).
    """
    # Per-component embedding similarity
    weighted_sum = 0.0
    total_weight = 0.0
    per_comp = {}
    for code in COMPONENT_ORDER:
        src_emb = src.get(f'embedding_{code}')
        tgt_emb = tgt.get(f'embedding_{code}')
        if src_emb is not None and tgt_emb is not None:
            sim = cosine_sim(src_emb, tgt_emb)
            per_comp[code] = sim
            w = COMPONENT_WEIGHTS.get(code, 0.0)
            weighted_sum += w * sim
            total_weight += w
    comp_sim = weighted_sum / total_weight if total_weight > 0 else 0.0

    # Set-based features
    prov = jaccard(
        set(src.get('provisions_cited', [])),
        set(tgt.get('provisions_cited', []))
    )
    out = outcome_alignment(
        src.get('outcome_type'), tgt.get('outcome_type')
    )
    tags = jaccard(
        set(src.get('subject_tags', [])),
        set(tgt.get('subject_tags', []))
    )
    princ = principle_overlap(
        src.get('principle_tensions', []),
        tgt.get('principle_tensions', [])
    )

    # Paper formula
    overall = (
        PAPER_W['embedding'] * comp_sim +
        PAPER_W['provision_overlap'] * prov +
        PAPER_W['outcome_alignment'] * out +
        PAPER_W['tag_overlap'] * tags +
        PAPER_W['principle_overlap'] * princ
    )

    return overall, comp_sim, per_comp


def get_case_title(case_id):
    doc = Document.query.get(case_id)
    return doc.title if doc else f"Case {case_id}"


def get_entity_counts(case_id):
    """Count entities per component from temporary_rdf_storage."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage
    from app.services.precedent.case_feature_extractor import (
        EXTRACTION_TYPE_TO_COMPONENT, ENTITY_TYPE_TO_COMPONENT
    )
    entities = TemporaryRDFStorage.query.filter_by(case_id=case_id).all()
    counts = {comp: 0 for comp in COMPONENT_ORDER}
    for entity in entities:
        comp_code = None
        if entity.extraction_type in EXTRACTION_TYPE_TO_COMPONENT:
            comp_code = EXTRACTION_TYPE_TO_COMPONENT[entity.extraction_type]
        elif entity.extraction_type == 'temporal_dynamics_enhanced':
            if entity.entity_type:
                comp_code = ENTITY_TYPE_TO_COMPONENT.get(
                    entity.entity_type.lower()
                )
        if comp_code:
            counts[comp_code] = counts.get(comp_code, 0) + 1
    return counts


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Recompute divergent_components.csv with paper weights'
    )
    parser.add_argument(
        '--cases', type=str, default='19,105,141',
        help='Divergent case IDs (default: 19,105,141)'
    )
    parser.add_argument('--output-dir', default=None)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        service = PrecedentSimilarityService()

        print("Recompute Divergent Components (Paper Weights)")
        print("=" * 60)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print()

        # Load all features
        print("Loading case features...")
        features = load_all_features(service)
        pool_ids = sorted(features.keys())
        print(f"Loaded {len(features)} cases")

        source_ids = [int(c.strip()) for c in args.cases.split(',')]

        # Load original neighbor lists for comparison
        base_dir = os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        )
        orig_csv = os.path.join(
            base_dir, 'docs-internal', 'iccbr-experiments',
            'divergent_components.csv'
        )
        original_neighbors = {}
        if os.path.exists(orig_csv):
            with open(orig_csv) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sid = int(row['source_id'])
                    tid = int(row['target_id'])
                    original_neighbors.setdefault(sid, []).append(tid)

        all_rows = []

        for source_id in source_ids:
            src = features[source_id]
            title = get_case_title(source_id)
            entity_counts = get_entity_counts(source_id)
            total_entities = sum(entity_counts.values())
            components_present = sum(
                1 for code in COMPONENT_ORDER
                if src.get(f'embedding_{code}') is not None
            )

            print(f"\nCase {source_id}: {title}")
            print(f"  {components_present}/9 components, {total_entities} entities")

            # Rank all candidates by paper-weight full formula
            rankings = []
            for target_id in pool_ids:
                if target_id == source_id:
                    continue
                overall, comp_sim, per_comp = compute_paper_weight_score(
                    src, features[target_id]
                )
                rankings.append({
                    'target_id': target_id,
                    'overall': overall,
                    'comp_sim': comp_sim,
                    'per_comp': per_comp,
                })

            rankings.sort(key=lambda x: -x['overall'])
            top10 = rankings[:10]

            new_neighbors = [r['target_id'] for r in top10]
            orig = original_neighbors.get(source_id, [])

            # Report discrepancy
            new_set = set(new_neighbors)
            orig_set = set(orig)
            added = new_set - orig_set
            removed = orig_set - new_set
            shared = new_set & orig_set

            print(f"  Paper-weight top-10: {new_neighbors}")
            print(f"  Original top-10:     {orig}")
            print(
                f"  Overlap: {len(shared)}/10 | "
                f"Added: {added or 'none'} | "
                f"Removed: {removed or 'none'}"
            )

            # Print per-component breakdown
            print(f"\n  {'Rank':<5} {'Case':<6} {'Overall':>8} {'CompSim':>8}", end='')
            for comp in COMPONENT_ORDER:
                print(f" {comp:>5}", end='')
            print()

            for rank, r in enumerate(top10, 1):
                line = (
                    f"  {rank:<5} {r['target_id']:<6} "
                    f"{r['overall']:>8.4f} {r['comp_sim']:>8.4f}"
                )
                for comp in COMPONENT_ORDER:
                    val = r['per_comp'].get(comp)
                    line += f" {val:>5.3f}" if val is not None else f" {'--':>5}"
                print(line)

                all_rows.append({
                    'source_id': source_id,
                    'source_title': title,
                    'target_id': r['target_id'],
                    'target_title': get_case_title(r['target_id']),
                    'rank': rank,
                    'weighted_similarity': round(r['comp_sim'], 4),
                    **{
                        f'sim_{comp}': round(r['per_comp'][comp], 4)
                        if comp in r['per_comp'] else ''
                        for comp in COMPONENT_ORDER
                    },
                })

            # Component stats
            print(f"\n  Component stats (top-10):")
            print(f"  {'Component':<14} {'Mean':>6} {'StdDev':>7} {'Min':>6} {'Max':>6} {'Weight':>7}")
            comp_vals = {comp: [] for comp in COMPONENT_ORDER}
            for r in top10:
                for comp in COMPONENT_ORDER:
                    v = r['per_comp'].get(comp)
                    if v is not None:
                        comp_vals[comp].append(v)

            stats_by_std = []
            for comp in COMPONENT_ORDER:
                vals = comp_vals[comp]
                if len(vals) >= 2:
                    stats_by_std.append((
                        comp, np.mean(vals), np.std(vals),
                        np.min(vals), np.max(vals)
                    ))
            stats_by_std.sort(key=lambda x: x[2], reverse=True)

            for comp, mean, std, mn, mx in stats_by_std:
                print(
                    f"  {COMPONENT_LABELS[comp]:<14} {mean:>6.3f} {std:>7.3f} "
                    f"{mn:>6.3f} {mx:>6.3f} {COMPONENT_WEIGHTS[comp]:>7.2f}"
                )

        # Write CSV
        out_dir = args.output_dir or os.path.join(
            base_dir, 'docs-internal', 'iccbr-experiments'
        )
        csv_path = os.path.join(out_dir, 'divergent_components.csv')
        fields = [
            'source_id', 'source_title', 'target_id', 'target_title',
            'rank', 'weighted_similarity',
        ] + [f'sim_{comp}' for comp in COMPONENT_ORDER]

        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(all_rows)

        print(f"\nCSV: {csv_path} ({len(all_rows)} rows)")

        # Also update the original location
        final_dir = os.path.join(
            base_dir, 'docs-internal', 'conferences_submissions', 'iccbr',
            'results_2026-03-13_final'
        )
        final_path = os.path.join(final_dir, 'divergent_components.csv')
        with open(final_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(all_rows)

        print(f"Also updated: {final_path}")
        print("\nDone.")


if __name__ == '__main__':
    main()
