#!/usr/bin/env python3
"""
Ground Truth Precedent Retrieval Experiment v3: Three-Way Comparison

Compares three embedding strategies within the same multi-factor
similarity architecture (0.40 embedding + 0.60 set-based):

1. Section-based: Facts + Discussion cosine (0.15 + 0.25)
2. Combined D-tuple: Single combined_embedding cosine (0.40)
3. Per-component D-tuple: 9 independent component cosines, weighted (0.40)

All three methods share identical set-based features (provisions, outcome,
tags, principles) at 0.60 total weight. Only the embedding component differs.

Output:
- three_way_results.md (aggregate metrics, per-edge breakdown)
- three_way_per_edge.csv (per-citation-edge ranks for all methods)
- three_way_aggregate.csv (summary metrics)
"""

import os
import csv
from datetime import datetime
from collections import defaultdict

from app import create_app
from app.models import Document, db
from app.services.precedent.similarity_service import PrecedentSimilarityService
from sqlalchemy import text
import numpy as np


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------

def get_embedded_case_ids():
    """Get case IDs that have all three embedding types available."""
    rows = db.session.execute(text("""
        SELECT case_id FROM case_precedent_features
        WHERE facts_embedding IS NOT NULL
          AND combined_embedding IS NOT NULL
    """)).fetchall()
    return {r[0] for r in rows}


def get_citation_graph():
    rows = db.session.execute(text("""
        SELECT case_id, cited_case_ids
        FROM case_precedent_features
        WHERE cited_case_ids IS NOT NULL
          AND array_length(cited_case_ids, 1) > 0
    """)).fetchall()
    return {r[0]: list(r[1]) for r in rows}


def get_case_title(case_id):
    doc = Document.query.get(case_id)
    return doc.title if doc else f"Case {case_id}"


# ---------------------------------------------------------------------------
# Ranking functions
# ---------------------------------------------------------------------------

def rank_section(service, source_id, pool_ids):
    """Rank using section-based similarity (facts + discussion)."""
    results = []
    for target_id in pool_ids:
        if target_id == source_id:
            continue
        sim = service.calculate_similarity(source_id, target_id, use_component_embedding=False)
        results.append((target_id, sim.overall_similarity))
    results.sort(key=lambda x: -x[1])
    return results


def rank_per_component(service, source_id, pool_ids):
    """Rank using per-component D-tuple similarity."""
    results = []
    for target_id in pool_ids:
        if target_id == source_id:
            continue
        sim = service.calculate_similarity(source_id, target_id, use_component_embedding=True)
        results.append((target_id, sim.overall_similarity))
    results.sort(key=lambda x: -x[1])
    return results


def rank_combined(service, source_id, pool_ids):
    """Rank using combined D-tuple embedding (single vector cosine).

    Uses the same 0.40/0.60 split as the other methods, but the 0.40
    embedding portion is a single cosine between combined_embedding vectors
    rather than section-based or per-component scores.
    """
    # Get source combined embedding
    src_row = db.session.execute(text("""
        SELECT combined_embedding FROM case_precedent_features
        WHERE case_id = :case_id AND combined_embedding IS NOT NULL
    """), {'case_id': source_id}).fetchone()
    if not src_row:
        return []

    results = []
    for target_id in pool_ids:
        if target_id == source_id:
            continue

        # Compute combined_embedding cosine via pgvector
        sim_row = db.session.execute(text("""
            SELECT 1 - (s.combined_embedding <=> t.combined_embedding) as sim
            FROM case_precedent_features s, case_precedent_features t
            WHERE s.case_id = :src AND t.case_id = :tgt
              AND s.combined_embedding IS NOT NULL
              AND t.combined_embedding IS NOT NULL
        """), {'src': source_id, 'tgt': target_id}).fetchone()

        if sim_row is None:
            continue

        combined_cosine = float(sim_row[0])

        # Get set-based features using the service (same as other methods)
        sim = service.calculate_similarity(source_id, target_id, use_component_embedding=True)

        # Recompute overall score with combined cosine as embedding component
        # Same weights as COMPONENT_AWARE_WEIGHTS but with combined cosine
        weights = {'component_similarity': 0.50, 'provision_overlap': 0.30, 'tag_overlap': 0.20}
        overall = (
            weights['component_similarity'] * combined_cosine +
            weights['provision_overlap'] * sim.component_scores.get('provision_overlap', 0) +
            weights['tag_overlap'] * sim.component_scores.get('tag_overlap', 0)
        )
        results.append((target_id, overall))

    results.sort(key=lambda x: -x[1])
    return results


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def recall_at_k(ranking, cited_ids, k):
    if not cited_ids:
        return 0.0
    top_k_ids = {cid for cid, _ in ranking[:k]}
    hits = len(set(cited_ids) & top_k_ids)
    return hits / len(cited_ids)


def reciprocal_rank(ranking, cited_ids):
    cited_set = set(cited_ids)
    for rank, (cid, _) in enumerate(ranking, start=1):
        if cid in cited_set:
            return 1.0 / rank
    return 0.0


def find_rank(ranking, target_id):
    for rank, (cid, _) in enumerate(ranking, start=1):
        if cid == target_id:
            return rank
    return None


def random_baseline_recall(k, pool_size, num_cited):
    if pool_size <= 0 or num_cited <= 0:
        return 0.0
    expected_hits = min(k * num_cited / pool_size, num_cited)
    return expected_hits / num_cited


def random_baseline_mrr(pool_size, num_cited):
    if pool_size <= 0 or num_cited <= 0:
        return 0.0
    total_mrr = 0.0
    prob_no_hit = 1.0
    n, c = pool_size, num_cited
    for r in range(1, n + 1):
        if n - r + 1 <= 0:
            break
        p_hit_at_r = prob_no_hit * c / (n - r + 1)
        total_mrr += (1.0 / r) * p_hit_at_r
        denom = n - (r - 1)
        numer = n - c - (r - 1)
        prob_no_hit *= numer / denom if denom > 0 and numer >= 0 else 0
    return total_mrr


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------

def run_three_way(service, verbose=False):
    citation_graph = get_citation_graph()
    pool = get_embedded_case_ids()

    print(f"Cases with all embeddings: {len(pool)}")
    print(f"Cases with citations: {len(citation_graph)}")
    total_edges = sum(len(v) for v in citation_graph.values())
    print(f"Total citation edges: {total_edges}")

    # Filter to source cases with resolvable citations in pool
    sources = {}
    for source_id in sorted(citation_graph.keys()):
        if source_id not in pool:
            continue
        cited = citation_graph[source_id]
        resolvable = [c for c in cited if c in pool]
        if resolvable:
            sources[source_id] = resolvable

    print(f"Source cases with resolvable citations: {len(sources)}")
    resolvable_edges = sum(len(v) for v in sources.values())
    print(f"Resolvable citation edges: {resolvable_edges}")
    pool_size = len(pool) - 1

    per_edge = []
    per_source = {}

    for i, (source_id, resolvable) in enumerate(sorted(sources.items()), 1):
        print(f"  [{i}/{len(sources)}] Case {source_id}...")

        section_ranking = rank_section(service, source_id, pool)
        combined_ranking = rank_combined(service, source_id, pool)
        component_ranking = rank_per_component(service, source_id, pool)

        src_data = {'resolvable': resolvable}
        for method, ranking in [('section', section_ranking),
                                ('combined', combined_ranking),
                                ('component', component_ranking)]:
            src_data[f'{method}_mrr'] = reciprocal_rank(ranking, resolvable)
            for k in [5, 10, 20]:
                src_data[f'{method}_r{k}'] = recall_at_k(ranking, resolvable, k)

        per_source[source_id] = src_data

        title = get_case_title(source_id)
        for cid in resolvable:
            s_rank = find_rank(section_ranking, cid)
            cb_rank = find_rank(combined_ranking, cid)
            cp_rank = find_rank(component_ranking, cid)
            per_edge.append({
                'source_case_id': source_id,
                'source_title': title,
                'cited_case_id': cid,
                'cited_title': get_case_title(cid),
                'section_rank': s_rank,
                'combined_rank': cb_rank,
                'component_rank': cp_rank,
                'pool_size': pool_size,
            })

    # Aggregate
    n = len(per_source)
    agg = {'n': n, 'pool_size': len(pool), 'edges': len(per_edge)}
    if n > 0:
        for method in ['section', 'combined', 'component']:
            for k in [5, 10, 20]:
                vals = [v[f'{method}_r{k}'] for v in per_source.values()]
                agg[f'{method}_r{k}'] = sum(vals) / n
            mrr_vals = [v[f'{method}_mrr'] for v in per_source.values()]
            agg[f'{method}_mrr'] = sum(mrr_vals) / n

    # Random baselines
    avg_cited = len(per_edge) / n if n > 0 else 1
    for k in [5, 10, 20]:
        agg[f'random_r{k}'] = random_baseline_recall(k, pool_size, avg_cited)
    agg['random_mrr'] = random_baseline_mrr(pool_size, avg_cited)

    return agg, per_source, per_edge


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_csv(per_edge, agg, output_dir):
    # Per-edge CSV
    edge_path = os.path.join(output_dir, 'three_way_per_edge.csv')
    fields = ['source_case_id', 'source_title', 'cited_case_id', 'cited_title',
              'section_rank', 'combined_rank', 'component_rank', 'pool_size']
    with open(edge_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(per_edge)
    print(f"Per-edge CSV: {edge_path} ({len(per_edge)} rows)")

    # Aggregate CSV
    agg_path = os.path.join(output_dir, 'three_way_aggregate.csv')
    with open(agg_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['metric', 'section', 'combined', 'component', 'random'])
        writer.writerow(['MRR',
                         f"{agg.get('section_mrr', 0):.3f}",
                         f"{agg.get('combined_mrr', 0):.3f}",
                         f"{agg.get('component_mrr', 0):.3f}",
                         f"{agg.get('random_mrr', 0):.3f}"])
        for k in [5, 10, 20]:
            writer.writerow([f'Recall@{k}',
                             f"{agg.get(f'section_r{k}', 0):.3f}",
                             f"{agg.get(f'combined_r{k}', 0):.3f}",
                             f"{agg.get(f'component_r{k}', 0):.3f}",
                             f"{agg.get(f'random_r{k}', 0):.3f}"])
    print(f"Aggregate CSV: {agg_path}")


def write_markdown(agg, per_source, per_edge, output_dir):
    md_path = os.path.join(output_dir, 'three_way_results.md')
    lines = []

    lines.append("# Three-Way Embedding Comparison Results")
    lines.append("")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Script:** `scripts/analysis/evaluate_ground_truth_v3.py`")
    lines.append("")

    lines.append("## Experimental Design")
    lines.append("")
    lines.append("All three methods share the same multi-factor scoring formula "
                 "(0.40 embedding + 0.60 set-based features). Only the 0.40 embedding "
                 "component differs:")
    lines.append("")
    lines.append("1. **Section-based**: Facts (0.15) + Discussion (0.25) cosine similarity")
    lines.append("2. **Combined D-tuple**: Single cosine between combined_embedding vectors (0.40)")
    lines.append("3. **Per-component D-tuple**: 9 independent component cosines, weighted average (0.40)")
    lines.append("")

    lines.append("## Data")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|------:|")
    lines.append(f"| Cases with all embedding types | {agg['pool_size']} |")
    lines.append(f"| Source cases with resolvable citations | {agg['n']} |")
    lines.append(f"| Total citation edges | {agg['edges']} |")
    lines.append(f"| Candidates per query | {agg['pool_size'] - 1} |")
    lines.append(f"| Average citations per source | {agg['edges'] / agg['n']:.1f} |")
    lines.append("")

    lines.append("## Aggregate Results")
    lines.append("")
    lines.append("| Metric | Section | Combined | Per-comp. | Random |")
    lines.append("|--------|:-------:|:--------:|:---------:|:------:|")
    lines.append(f"| MRR | {agg.get('section_mrr', 0):.3f} | "
                 f"{agg.get('combined_mrr', 0):.3f} | "
                 f"{agg.get('component_mrr', 0):.3f} | "
                 f"{agg.get('random_mrr', 0):.3f} |")
    for k in [5, 10, 20]:
        lines.append(f"| Recall@{k} | {agg.get(f'section_r{k}', 0):.3f} | "
                     f"{agg.get(f'combined_r{k}', 0):.3f} | "
                     f"{agg.get(f'component_r{k}', 0):.3f} | "
                     f"{agg.get(f'random_r{k}', 0):.3f} |")
    lines.append("")

    # Decomposition
    lines.append("## Improvement Decomposition")
    lines.append("")
    s_r10 = agg.get('section_r10', 0)
    cb_r10 = agg.get('combined_r10', 0)
    cp_r10 = agg.get('component_r10', 0)
    lines.append(f"| Step | Recall@10 | Delta |")
    lines.append(f"|------|:---------:|:-----:|")
    lines.append(f"| Section baseline | {s_r10:.3f} | -- |")
    lines.append(f"| + D-tuple extraction (combined) | {cb_r10:.3f} | {cb_r10 - s_r10:+.3f} |")
    lines.append(f"| + Component independence (per-comp.) | {cp_r10:.3f} | {cp_r10 - cb_r10:+.3f} |")
    lines.append(f"| Total improvement | | {cp_r10 - s_r10:+.3f} |")
    lines.append("")
    if cb_r10 > s_r10:
        pct = (cb_r10 - s_r10) / s_r10 * 100 if s_r10 > 0 else 0
        lines.append(f"D-tuple extraction accounts for {pct:.1f}% improvement in Recall@10 "
                     f"over section-based embedding.")
    lines.append("")

    # Per-edge rank comparison
    lines.append("## Per-Edge Rank Comparison")
    lines.append("")

    for m1, m2, label in [('component', 'section', 'Per-comp. vs Section'),
                          ('combined', 'section', 'Combined vs Section'),
                          ('combined', 'component', 'Combined vs Per-comp.')]:
        m1_wins = sum(1 for e in per_edge
                      if e[f'{m1}_rank'] and e[f'{m2}_rank']
                      and e[f'{m1}_rank'] < e[f'{m2}_rank'])
        m2_wins = sum(1 for e in per_edge
                      if e[f'{m1}_rank'] and e[f'{m2}_rank']
                      and e[f'{m2}_rank'] < e[f'{m1}_rank'])
        ties = sum(1 for e in per_edge
                   if e[f'{m1}_rank'] and e[f'{m2}_rank']
                   and e[f'{m1}_rank'] == e[f'{m2}_rank'])
        lines.append(f"**{label}:** {m1} wins {m1_wins}, {m2} wins {m2_wins}, tied {ties}")
        lines.append("")

    with open(md_path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"Markdown: {md_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Three-way embedding comparison')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--output-dir', default=None)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        service = PrecedentSimilarityService()

        print("Three-Way Embedding Comparison Experiment")
        print("=" * 60)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print()

        agg, per_source, per_edge = run_three_way(service, verbose=args.verbose)

        print()
        print("=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"{'Metric':<12} {'Section':>8} {'Combined':>9} {'Per-comp':>9} {'Random':>8}")
        print(f"{'MRR':<12} {agg.get('section_mrr', 0):>8.3f} {agg.get('combined_mrr', 0):>9.3f} {agg.get('component_mrr', 0):>9.3f} {agg.get('random_mrr', 0):>8.3f}")
        for k in [5, 10, 20]:
            print(f"{'Recall@' + str(k):<12} {agg.get(f'section_r{k}', 0):>8.3f} {agg.get(f'combined_r{k}', 0):>9.3f} {agg.get(f'component_r{k}', 0):>9.3f} {agg.get(f'random_r{k}', 0):>8.3f}")

        out_dir = args.output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'docs-internal', 'conferences_submissions', 'iccbr', 'results_2026-03-13'
        )
        os.makedirs(out_dir, exist_ok=True)

        write_csv(per_edge, agg, out_dir)
        write_markdown(agg, per_source, per_edge, out_dir)

        print("\nDone.")


if __name__ == '__main__':
    main()
