#!/usr/bin/env python3
"""
Three-Way Rank Correlation Analysis

For each of 119 cases, ranks all 118 candidates under three methods
(section, combined D-tuple, per-component D-tuple) and computes
pairwise Spearman ρ and Overlap@10.

Uses paper weights (0.40 embedding + 0.60 set-based) for all methods.

Output:
- rank_correlation_three_way.csv (per-case correlations)
- rank_correlation_three_way_summary.md (aggregate metrics)
"""

import os
import csv
from datetime import datetime
from scipy import stats

from app import create_app
from app.models import Document, db
from app.services.precedent.similarity_service import PrecedentSimilarityService
from sqlalchemy import text


# Paper weights: identical 6-factor formula for all methods
PAPER_WEIGHTS = {
    'embedding': 0.40,
    'provision_overlap': 0.25,
    'outcome_alignment': 0.15,
    'tag_overlap': 0.10,
    'principle_overlap': 0.10,
}


def get_embedded_case_ids():
    rows = db.session.execute(text("""
        SELECT case_id FROM case_precedent_features
        WHERE facts_embedding IS NOT NULL
          AND combined_embedding IS NOT NULL
    """)).fetchall()
    return sorted(r[0] for r in rows)


def get_case_title(case_id):
    doc = Document.query.get(case_id)
    return doc.title if doc else f"Case {case_id}"


def get_set_based_scores(service, source_id, target_id):
    sim = service.calculate_similarity(source_id, target_id, use_component_embedding=False)
    return {
        'provision_overlap': sim.component_scores.get('provision_overlap', 0),
        'outcome_alignment': sim.component_scores.get('outcome_alignment', 0),
        'tag_overlap': sim.component_scores.get('tag_overlap', 0),
        'principle_overlap': sim.component_scores.get('principle_overlap', 0),
        'facts_similarity': sim.component_scores.get('facts_similarity', 0),
        'discussion_similarity': sim.component_scores.get('discussion_similarity', 0),
    }


def paper_overall(embedding_score, sb):
    return (
        PAPER_WEIGHTS['embedding'] * embedding_score +
        PAPER_WEIGHTS['provision_overlap'] * sb['provision_overlap'] +
        PAPER_WEIGHTS['outcome_alignment'] * sb['outcome_alignment'] +
        PAPER_WEIGHTS['tag_overlap'] * sb['tag_overlap'] +
        PAPER_WEIGHTS['principle_overlap'] * sb['principle_overlap']
    )


def compute_rankings(service, source_id, candidates):
    """Compute rankings for one source case under all three methods.

    Returns dict with keys 'section', 'combined', 'component',
    each mapping to a list of (case_id, score) sorted descending.
    """
    section_scores = []
    combined_scores = []
    component_scores = []

    for target_id in candidates:
        if target_id == source_id:
            continue

        # Get shared set-based features (one call)
        sb = get_set_based_scores(service, source_id, target_id)

        # Section: facts + discussion
        section_emb = (0.15 * sb['facts_similarity'] + 0.25 * sb['discussion_similarity']) / 0.40
        section_scores.append((target_id, paper_overall(section_emb, sb)))

        # Combined: single combined_embedding cosine
        sim_row = db.session.execute(text("""
            SELECT 1 - (s.combined_embedding <=> t.combined_embedding) as sim
            FROM case_precedent_features s, case_precedent_features t
            WHERE s.case_id = :src AND t.case_id = :tgt
              AND s.combined_embedding IS NOT NULL
              AND t.combined_embedding IS NOT NULL
        """), {'src': source_id, 'tgt': target_id}).fetchone()
        combined_cosine = float(sim_row[0]) if sim_row else 0.0
        combined_scores.append((target_id, paper_overall(combined_cosine, sb)))

        # Per-component: 9 independent cosines
        comp_sim = service.calculate_similarity(
            source_id, target_id, use_component_embedding=True
        )
        comp_emb = comp_sim.component_scores.get('component_similarity', 0)
        component_scores.append((target_id, paper_overall(comp_emb, sb)))

    section_scores.sort(key=lambda x: -x[1])
    combined_scores.sort(key=lambda x: -x[1])
    component_scores.sort(key=lambda x: -x[1])

    return {
        'section': section_scores,
        'combined': combined_scores,
        'component': component_scores,
    }


def spearman_rho(ranking_a, ranking_b):
    """Compute Spearman rank correlation between two rankings."""
    # Build rank maps
    rank_a = {cid: r for r, (cid, _) in enumerate(ranking_a, 1)}
    rank_b = {cid: r for r, (cid, _) in enumerate(ranking_b, 1)}
    common = set(rank_a.keys()) & set(rank_b.keys())
    if len(common) < 3:
        return 0.0
    ranks_a = [rank_a[cid] for cid in sorted(common)]
    ranks_b = [rank_b[cid] for cid in sorted(common)]
    rho, _ = stats.spearmanr(ranks_a, ranks_b)
    return rho


def overlap_at_k(ranking_a, ranking_b, k=10):
    """Fraction of top-K items shared between two rankings."""
    top_a = {cid for cid, _ in ranking_a[:k]}
    top_b = {cid for cid, _ in ranking_b[:k]}
    if not top_a or not top_b:
        return 0.0
    return len(top_a & top_b) / k


def mean_top10_score(ranking):
    """Average score of top-10 results."""
    if not ranking:
        return 0.0
    scores = [s for _, s in ranking[:10]]
    return sum(scores) / len(scores)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Three-way rank correlation')
    parser.add_argument('--output-dir', default=None)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        service = PrecedentSimilarityService()
        case_ids = get_embedded_case_ids()

        print(f"Three-Way Rank Correlation Analysis (paper weights)")
        print(f"=" * 60)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"Cases: {len(case_ids)}")
        print()

        rows = []
        for i, source_id in enumerate(case_ids, 1):
            print(f"  [{i}/{len(case_ids)}] Case {source_id}...")

            rankings = compute_rankings(service, source_id, case_ids)

            rho_sc = spearman_rho(rankings['section'], rankings['combined'])
            rho_sp = spearman_rho(rankings['section'], rankings['component'])
            rho_cp = spearman_rho(rankings['combined'], rankings['component'])

            o10_sc = overlap_at_k(rankings['section'], rankings['combined'])
            o10_sp = overlap_at_k(rankings['section'], rankings['component'])
            o10_cp = overlap_at_k(rankings['combined'], rankings['component'])

            rows.append({
                'case_id': source_id,
                'case_title': get_case_title(source_id),
                'rho_sec_comb': round(rho_sc, 4),
                'rho_sec_comp': round(rho_sp, 4),
                'rho_comb_comp': round(rho_cp, 4),
                'overlap10_sec_comb': round(o10_sc, 4),
                'overlap10_sec_comp': round(o10_sp, 4),
                'overlap10_comb_comp': round(o10_cp, 4),
                'mean_sim_section': round(mean_top10_score(rankings['section']), 4),
                'mean_sim_combined': round(mean_top10_score(rankings['combined']), 4),
                'mean_sim_component': round(mean_top10_score(rankings['component']), 4),
            })

        # Aggregate
        n = len(rows)
        print()
        print("=" * 60)
        print("RESULTS")
        print("=" * 60)

        pairs = [
            ('sec_comb', 'Section vs Combined'),
            ('sec_comp', 'Section vs Per-comp.'),
            ('comb_comp', 'Combined vs Per-comp.'),
        ]
        print(f"\n{'Metric':<22} ", end='')
        for _, label in pairs:
            print(f"{label:>20}", end='')
        print()

        for metric, key_prefix in [('Mean Spearman ρ', 'rho'), ('Mean Overlap@10', 'overlap10')]:
            print(f"{metric:<22} ", end='')
            for pair_key, _ in pairs:
                vals = [r[f'{key_prefix}_{pair_key}'] for r in rows]
                mean = sum(vals) / n
                print(f"{mean:>20.3f}", end='')
            print()

        print(f"\n{'Mean similarity':<22} ", end='')
        for method in ['section', 'combined', 'component']:
            vals = [r[f'mean_sim_{method}'] for r in rows]
            mean = sum(vals) / n
            print(f"{method}: {mean:.3f}  ", end='')
        print()

        # Most divergent (lowest sec vs comp ρ)
        rows_sorted = sorted(rows, key=lambda r: r['rho_sec_comp'])
        print(f"\nMost divergent cases (section vs per-component):")
        for r in rows_sorted[:5]:
            print(f"  Case {r['case_id']} (ρ={r['rho_sec_comp']:.3f}): {r['case_title'][:50]}")

        # Save
        out_dir = args.output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'docs-internal', 'conferences_submissions', 'iccbr'
        )
        os.makedirs(out_dir, exist_ok=True)

        csv_path = os.path.join(out_dir, 'rank_correlation_three_way.csv')
        fields = list(rows[0].keys())
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nCSV: {csv_path} ({len(rows)} rows)")

        # Summary markdown
        md_path = os.path.join(out_dir, 'rank_correlation_three_way_summary.md')
        lines = []
        lines.append("# Three-Way Rank Correlation Summary")
        lines.append("")
        lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"**Cases:** {n}")
        lines.append(f"**Weights:** Paper (0.40 embedding + 0.60 set-based)")
        lines.append("")

        lines.append("## Pairwise Correlations")
        lines.append("")
        lines.append("| Metric | Sec. vs Comb. | Sec. vs Comp. | Comb. vs Comp. |")
        lines.append("|--------|:-------------:|:-------------:|:--------------:|")
        for metric, key_prefix in [('Mean Spearman ρ', 'rho'), ('Mean Overlap@10', 'overlap10')]:
            vals = []
            for pair_key, _ in pairs:
                v = sum(r[f'{key_prefix}_{pair_key}'] for r in rows) / n
                vals.append(f"{v:.3f}")
            lines.append(f"| {metric} | {' | '.join(vals)} |")
        lines.append("")

        lines.append("## Mean Similarity Scores (top-10 average)")
        lines.append("")
        lines.append("| Method | Mean Score |")
        lines.append("|--------|:---------:|")
        for method in ['section', 'combined', 'component']:
            mean = sum(r[f'mean_sim_{method}'] for r in rows) / n
            lines.append(f"| {method.title()} | {mean:.3f} |")
        lines.append("")

        lines.append("## Most Divergent Cases (Section vs Per-component)")
        lines.append("")
        lines.append("| Case | ρ | Title |")
        lines.append("|------|:-:|-------|")
        for r in rows_sorted[:5]:
            lines.append(f"| {r['case_id']} | {r['rho_sec_comp']:.3f} | {r['case_title'][:50]} |")
        lines.append("")

        with open(md_path, 'w') as f:
            f.write('\n'.join(lines))
        print(f"Summary: {md_path}")


if __name__ == '__main__':
    main()
