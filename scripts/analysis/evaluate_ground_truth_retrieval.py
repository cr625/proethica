#!/usr/bin/env python3
"""
Ground Truth Precedent Retrieval Experiment

Evaluates ProEthica's retrieval methods against expert-cited precedent cases
from the NSPE BER corpus. Board members explicitly cite prior BER decisions in
their opinions; these citations serve as ground truth for retrieval quality.

Two retrieval methods are compared:
1. Section-based: facts + discussion embeddings (monolithic text similarity)
2. Component-based: 9-component weighted aggregation (structured decomposition)

Metrics:
- Recall@K (K=5, 10, 20): fraction of cited cases appearing in top K results
- MRR: Mean Reciprocal Rank of first cited case in ranking
- Per-case breakdown with cited case positions in each ranking

Output:
- Markdown report: ground_truth_experiment_results.md
- CSV raw data: ground_truth_experiment_data.csv

Usage:
    python scripts/analysis/evaluate_ground_truth_retrieval.py
    python scripts/analysis/evaluate_ground_truth_retrieval.py --verbose
"""

import sys
import os
import csv
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, '/home/chris/onto')

from app import create_app
from app.models import Document, db
from app.services.precedent.similarity_service import PrecedentSimilarityService
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------

def get_component_embedded_case_ids():
    """Return set of case IDs that have component embeddings."""
    rows = db.session.execute(text(
        "SELECT case_id FROM case_precedent_features WHERE combined_embedding IS NOT NULL"
    )).fetchall()
    return {r[0] for r in rows}


def get_all_case_ids_with_section_embeddings():
    """Return set of case IDs that have section (facts) embeddings."""
    rows = db.session.execute(text(
        "SELECT case_id FROM case_precedent_features WHERE facts_embedding IS NOT NULL"
    )).fetchall()
    return {r[0] for r in rows}


def get_citation_graph():
    """
    Return citation data: {source_case_id: [cited_case_id, ...]}.
    Only includes cases with non-empty cited_case_ids.
    """
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
# Retrieval
# ---------------------------------------------------------------------------

def get_full_ranking(service, source_case_id, use_component, candidate_pool):
    """
    Run retrieval for source_case_id, return ranked list of (case_id, score).
    Filters results to candidate_pool for fair comparison.
    """
    # Retrieve more than we need, then filter
    results = service.find_similar_cases(
        source_case_id,
        limit=200,
        use_component_embedding=use_component
    )
    # Filter to candidate pool and rebuild ranking
    filtered = [
        (r.target_case_id, r.overall_similarity)
        for r in results
        if r.target_case_id in candidate_pool
    ]
    return filtered


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def recall_at_k(ranking, cited_ids, k):
    """Fraction of cited_ids that appear in the top k of ranking."""
    if not cited_ids:
        return 0.0
    top_k_ids = {cid for cid, _ in ranking[:k]}
    hits = len(set(cited_ids) & top_k_ids)
    return hits / len(cited_ids)


def reciprocal_rank(ranking, cited_ids):
    """1/rank of the first cited case found in the ranking. 0 if none found."""
    cited_set = set(cited_ids)
    for rank, (cid, _) in enumerate(ranking, start=1):
        if cid in cited_set:
            return 1.0 / rank
    return 0.0


def find_cited_positions(ranking, cited_ids):
    """Return dict {cited_id: rank_position} for each cited case. None if not found."""
    rank_map = {cid: rank for rank, (cid, _) in enumerate(ranking, start=1)}
    positions = {}
    for cid in cited_ids:
        positions[cid] = rank_map.get(cid, None)
    return positions


# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------

def run_experiment(service, verbose=False):
    """Run ground truth evaluation for both methods."""
    citation_graph = get_citation_graph()
    component_pool = get_component_embedded_case_ids()
    section_pool = get_all_case_ids_with_section_embeddings()

    print(f"Total cases with citations: {len(citation_graph)}")
    print(f"Cases with component embeddings: {len(component_pool)}")
    print(f"Cases with section embeddings: {len(section_pool)}")

    # -----------------------------------------------------------------------
    # Experiment 1: Head-to-head on component-embedded pool (25 cases)
    # Source cases: those in component_pool with citations where at least one
    # cited case is also in component_pool
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("EXPERIMENT 1: Head-to-head comparison (component-embedded pool)")
    print("=" * 70)

    exp1_rows = []
    exp1_section_recalls = {5: [], 10: [], 20: []}
    exp1_component_recalls = {5: [], 10: [], 20: []}
    exp1_section_mrr = []
    exp1_component_mrr = []

    for source_id in sorted(citation_graph.keys()):
        if source_id not in component_pool:
            continue
        cited_ids = citation_graph[source_id]
        resolvable = [c for c in cited_ids if c in component_pool]
        if not resolvable:
            continue

        # Both methods search same pool for fair comparison
        pool = component_pool - {source_id}
        section_ranking = get_full_ranking(service, source_id, False, pool)
        component_ranking = get_full_ranking(service, source_id, True, pool)

        s_positions = find_cited_positions(section_ranking, resolvable)
        c_positions = find_cited_positions(component_ranking, resolvable)

        for k in [5, 10, 20]:
            exp1_section_recalls[k].append(recall_at_k(section_ranking, resolvable, k))
            exp1_component_recalls[k].append(recall_at_k(component_ranking, resolvable, k))

        exp1_section_mrr.append(reciprocal_rank(section_ranking, resolvable))
        exp1_component_mrr.append(reciprocal_rank(component_ranking, resolvable))

        title = get_case_title(source_id)
        total_cited = len(cited_ids)
        resolvable_count = len(resolvable)

        for cid in resolvable:
            exp1_rows.append({
                'experiment': 1,
                'source_case_id': source_id,
                'source_title': title,
                'cited_case_id': cid,
                'cited_title': get_case_title(cid),
                'total_citations': total_cited,
                'resolvable_citations': resolvable_count,
                'section_rank': s_positions.get(cid),
                'component_rank': c_positions.get(cid),
                'pool_size': len(pool),
            })

        if verbose:
            print(f"\nCase {source_id}: {title[:50]}")
            print(f"  Citations: {total_cited} total, {resolvable_count} resolvable in pool")
            for cid in resolvable:
                s_r = s_positions.get(cid, "NOT FOUND")
                c_r = c_positions.get(cid, "NOT FOUND")
                print(f"  -> Cited {cid} ({get_case_title(cid)[:30]}): "
                      f"section={s_r}, component={c_r}")

    n1 = len(exp1_section_mrr)
    print(f"\nExp 1 source cases evaluated: {n1}")

    if n1 > 0:
        print(f"\nExp 1 Results (pool size = {len(component_pool) - 1}):")
        for k in [5, 10, 20]:
            capped_k = min(k, len(component_pool) - 1)
            s_r = sum(exp1_section_recalls[k]) / n1
            c_r = sum(exp1_component_recalls[k]) / n1
            print(f"  Recall@{k:2d}: Section={s_r:.3f}  Component={c_r:.3f}  "
                  f"(capped at {capped_k} due to pool size)")
        s_mrr = sum(exp1_section_mrr) / n1
        c_mrr = sum(exp1_component_mrr) / n1
        print(f"  MRR:       Section={s_mrr:.3f}  Component={c_mrr:.3f}")

    # -----------------------------------------------------------------------
    # Experiment 2: Section-based on full pool (118 cases)
    # Source cases: all cases with citations where at least one cited case
    # is in the section pool
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("EXPERIMENT 2: Section-based on full pool (all section-embedded cases)")
    print("=" * 70)

    exp2_rows = []
    exp2_recalls = {5: [], 10: [], 20: []}
    exp2_mrr = []

    for source_id in sorted(citation_graph.keys()):
        if source_id not in section_pool:
            continue
        cited_ids = citation_graph[source_id]
        resolvable = [c for c in cited_ids if c in section_pool]
        if not resolvable:
            continue

        pool = section_pool - {source_id}
        section_ranking = get_full_ranking(service, source_id, False, pool)

        s_positions = find_cited_positions(section_ranking, resolvable)

        for k in [5, 10, 20]:
            exp2_recalls[k].append(recall_at_k(section_ranking, resolvable, k))
        exp2_mrr.append(reciprocal_rank(section_ranking, resolvable))

        title = get_case_title(source_id)
        total_cited = len(cited_ids)
        resolvable_count = len(resolvable)

        for cid in resolvable:
            exp2_rows.append({
                'experiment': 2,
                'source_case_id': source_id,
                'source_title': title,
                'cited_case_id': cid,
                'cited_title': get_case_title(cid),
                'total_citations': total_cited,
                'resolvable_citations': resolvable_count,
                'section_rank': s_positions.get(cid),
                'component_rank': None,
                'pool_size': len(pool),
            })

        if verbose:
            print(f"\nCase {source_id}: {title[:50]}")
            print(f"  Citations: {total_cited} total, {resolvable_count} resolvable")
            for cid in resolvable:
                s_r = s_positions.get(cid, "NOT FOUND")
                print(f"  -> Cited {cid} ({get_case_title(cid)[:30]}): section={s_r}")

    n2 = len(exp2_mrr)
    print(f"\nExp 2 source cases evaluated: {n2}")

    if n2 > 0:
        print(f"\nExp 2 Results (pool size = {len(section_pool) - 1}):")
        for k in [5, 10, 20]:
            s_r = sum(exp2_recalls[k]) / n2
            print(f"  Recall@{k:2d}: Section={s_r:.3f}")
        s_mrr = sum(exp2_mrr) / n2
        print(f"  MRR:       Section={s_mrr:.3f}")

    return {
        'exp1': {
            'rows': exp1_rows,
            'n': n1,
            'section_recalls': {k: (sum(v)/n1 if n1 else 0) for k, v in exp1_section_recalls.items()},
            'component_recalls': {k: (sum(v)/n1 if n1 else 0) for k, v in exp1_component_recalls.items()},
            'section_mrr': sum(exp1_section_mrr)/n1 if n1 else 0,
            'component_mrr': sum(exp1_component_mrr)/n1 if n1 else 0,
            'per_case_section_recalls': {k: list(v) for k, v in exp1_section_recalls.items()},
            'per_case_component_recalls': {k: list(v) for k, v in exp1_component_recalls.items()},
            'per_case_section_mrr': list(exp1_section_mrr),
            'per_case_component_mrr': list(exp1_component_mrr),
            'pool_size': len(component_pool),
        },
        'exp2': {
            'rows': exp2_rows,
            'n': n2,
            'section_recalls': {k: (sum(v)/n2 if n2 else 0) for k, v in exp2_recalls.items()},
            'section_mrr': sum(exp2_mrr)/n2 if n2 else 0,
            'per_case_section_recalls': {k: list(v) for k, v in exp2_recalls.items()},
            'per_case_section_mrr': list(exp2_mrr),
            'pool_size': len(section_pool),
        },
        'component_pool': component_pool,
        'section_pool': section_pool,
        'citation_graph': citation_graph,
    }


# ---------------------------------------------------------------------------
# Output: CSV
# ---------------------------------------------------------------------------

def write_csv(data, output_path):
    all_rows = data['exp1']['rows'] + data['exp2']['rows']
    if not all_rows:
        print("No rows to write.")
        return

    fieldnames = [
        'experiment', 'source_case_id', 'source_title', 'cited_case_id',
        'cited_title', 'total_citations', 'resolvable_citations',
        'section_rank', 'component_rank', 'pool_size'
    ]
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)
    print(f"CSV written: {output_path}")


# ---------------------------------------------------------------------------
# Output: Markdown report
# ---------------------------------------------------------------------------

def write_markdown(data, output_path):
    exp1 = data['exp1']
    exp2 = data['exp2']

    lines = []
    lines.append("# Ground Truth Precedent Retrieval Experiment")
    lines.append("")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"**Script:** `scripts/analysis/evaluate_ground_truth_retrieval.py`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append("NSPE Board of Ethical Review (BER) opinions frequently cite prior BER decisions ")
    lines.append("as precedent. These expert-authored citations serve as ground truth for evaluating ")
    lines.append("whether ProEthica's similarity-based retrieval methods recover cases that domain ")
    lines.append("experts consider relevant.")
    lines.append("")
    lines.append("Two retrieval methods are evaluated:")
    lines.append("1. **Section-based**: Weighted combination of facts/discussion embedding cosine ")
    lines.append("   similarity, provision overlap, outcome alignment, tag overlap, and principle overlap")
    lines.append("2. **Component-based**: Replaces section embeddings with a 9-component structured ")
    lines.append("   embedding (R, P, O, S, Rs, A, E, Ca, Cs) while retaining the same metadata factors")
    lines.append("")

    # Data summary
    lines.append("## Data Summary")
    lines.append("")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total cases in database | {len(data['section_pool'])} |")
    lines.append(f"| Cases with section embeddings | {len(data['section_pool'])} |")
    lines.append(f"| Cases with component embeddings | {len(data['component_pool'])} |")
    lines.append(f"| Cases with expert citations | {len(data['citation_graph'])} |")

    total_edges = sum(len(v) for v in data['citation_graph'].values())
    lines.append(f"| Total citation edges | {total_edges} |")
    lines.append(f"| Exp 1 source cases (citations + component embeddings) | {exp1['n']} |")
    lines.append(f"| Exp 2 source cases (citations + section embeddings) | {exp2['n']} |")
    lines.append("")

    # Experiment 1
    lines.append("## Experiment 1: Head-to-Head Comparison (Component-Embedded Pool)")
    lines.append("")
    lines.append(f"**Pool size:** {exp1['pool_size']} cases with component embeddings. ")
    lines.append(f"Both methods search the same candidate pool for fair comparison. ")
    lines.append(f"**{exp1['n']} source cases** have at least one expert-cited case in this pool.")
    lines.append("")

    if exp1['n'] > 0:
        lines.append("### Aggregate Metrics")
        lines.append("")
        lines.append("| Metric | Section-Based | Component-Based |")
        lines.append("|--------|:------------:|:---------------:|")
        for k in [5, 10, 20]:
            capped = min(k, exp1['pool_size'] - 1)
            s_val = exp1['section_recalls'][k]
            c_val = exp1['component_recalls'][k]
            note = f" (pool={capped})" if capped < k else ""
            lines.append(f"| Recall@{k}{note} | {s_val:.3f} | {c_val:.3f} |")
        lines.append(f"| MRR | {exp1['section_mrr']:.3f} | {exp1['component_mrr']:.3f} |")
        lines.append("")

        # Per-case table
        lines.append("### Per-Case Breakdown")
        lines.append("")
        lines.append("| Source | Cited | Section Rank | Component Rank | Pool |")
        lines.append("|--------|-------|:------------:|:--------------:|:----:|")
        for row in exp1['rows']:
            s_r = str(row['section_rank']) if row['section_rank'] is not None else "---"
            c_r = str(row['component_rank']) if row['component_rank'] is not None else "---"
            src = f"Case {row['source_case_id']}"
            cited = f"Case {row['cited_case_id']}"
            lines.append(f"| {src} | {cited} | {s_r} | {c_r} | {row['pool_size']} |")
        lines.append("")

        # Divergence analysis
        lines.append("### Method Divergence")
        lines.append("")
        divergences = []
        for row in exp1['rows']:
            s_r = row['section_rank']
            c_r = row['component_rank']
            if s_r is not None and c_r is not None and s_r != c_r:
                divergences.append(row)
            elif (s_r is None) != (c_r is None):
                divergences.append(row)
        if divergences:
            lines.append("Cases where the two methods diverge on recovering cited precedents:")
            lines.append("")
            for row in divergences:
                s_r = row['section_rank'] if row['section_rank'] is not None else "not found"
                c_r = row['component_rank'] if row['component_rank'] is not None else "not found"
                lines.append(f"- Case {row['source_case_id']} -> cited Case {row['cited_case_id']}: "
                             f"section rank={s_r}, component rank={c_r}")
            lines.append("")
        else:
            lines.append("No divergences found -- both methods rank cited cases identically.")
            lines.append("")
    else:
        lines.append("**No source cases had resolvable citations within the component-embedded pool.**")
        lines.append("")

    # Experiment 2
    lines.append("## Experiment 2: Section-Based on Full Pool")
    lines.append("")
    lines.append(f"**Pool size:** {exp2['pool_size']} cases with section embeddings. ")
    lines.append(f"**{exp2['n']} source cases** evaluated.")
    lines.append("")

    if exp2['n'] > 0:
        lines.append("### Aggregate Metrics")
        lines.append("")
        lines.append("| Metric | Section-Based |")
        lines.append("|--------|:------------:|")
        for k in [5, 10, 20]:
            s_val = exp2['section_recalls'][k]
            lines.append(f"| Recall@{k} | {s_val:.3f} |")
        lines.append(f"| MRR | {exp2['section_mrr']:.3f} |")
        lines.append("")

        # Per-case table for exp2
        lines.append("### Per-Case Breakdown")
        lines.append("")

        # Group by source case for readability
        by_source = defaultdict(list)
        for row in exp2['rows']:
            by_source[row['source_case_id']].append(row)

        lines.append("| Source | Title | Cited | Section Rank | Pool |")
        lines.append("|--------|-------|-------|:------------:|:----:|")
        for sid in sorted(by_source.keys()):
            rows = by_source[sid]
            title = rows[0]['source_title'][:40]
            for i, row in enumerate(rows):
                s_r = str(row['section_rank']) if row['section_rank'] is not None else "---"
                src_col = f"Case {sid}" if i == 0 else ""
                title_col = title if i == 0 else ""
                lines.append(f"| {src_col} | {title_col} | Case {row['cited_case_id']} | "
                             f"{s_r} | {row['pool_size']} |")
        lines.append("")

        # Recall distribution
        lines.append("### Recall Distribution")
        lines.append("")
        per_case_r10 = exp2['per_case_section_recalls'][10]
        if per_case_r10:
            perfect = sum(1 for r in per_case_r10 if r == 1.0)
            partial = sum(1 for r in per_case_r10 if 0 < r < 1.0)
            zero = sum(1 for r in per_case_r10 if r == 0.0)
            lines.append(f"Recall@10 distribution across {exp2['n']} source cases:")
            lines.append(f"- Perfect recall (1.0): {perfect} cases ({100*perfect/exp2['n']:.0f}%)")
            lines.append(f"- Partial recall (0 < r < 1): {partial} cases ({100*partial/exp2['n']:.0f}%)")
            lines.append(f"- Zero recall (0.0): {zero} cases ({100*zero/exp2['n']:.0f}%)")
            lines.append("")

    # Limitations
    lines.append("## Limitations and Notes")
    lines.append("")
    lines.append("1. **Citation as lower bound.** Board members cite the most salient precedents, ")
    lines.append("   not all related cases. A case that is topically similar but not cited is not ")
    lines.append("   necessarily irrelevant. These metrics underestimate true retrieval quality.")
    lines.append("")
    lines.append("2. **Component embedding coverage.** Only 25 of 118 cases have component embeddings. ")
    lines.append("   Experiment 1 evaluates on a small pool where random baseline recall@10 would be ")
    lines.append(f"   ~{min(10, exp1['pool_size']-1)}/{exp1['pool_size']-1} = "
                 f"{min(10, exp1['pool_size']-1)/(exp1['pool_size']-1):.2f} if all cited cases were in the pool. ")
    lines.append("   Generating component embeddings for all 118 cases would enable a full comparison.")
    lines.append("")
    lines.append("3. **Asymmetric citations.** If Case A cites Case B, Case B does not necessarily ")
    lines.append("   cite Case A. The citation graph is directed.")
    lines.append("")
    lines.append("4. **Unresolved citations.** Some cited case numbers could not be resolved to ")
    lines.append("   database IDs (the cited case may not have been ingested). These are excluded.")
    lines.append("")

    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"Markdown written: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Ground truth precedent retrieval experiment')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--output-dir', default=None,
                        help='Output directory (default: docs-internal/conferences_submissions/iccbr/)')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        service = PrecedentSimilarityService()

        print("Ground Truth Precedent Retrieval Experiment")
        print("=" * 70)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print()

        data = run_experiment(service, verbose=args.verbose)

        # Output
        out_dir = args.output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'docs-internal', 'conferences_submissions', 'iccbr'
        )
        os.makedirs(out_dir, exist_ok=True)

        md_path = os.path.join(out_dir, 'ground_truth_experiment_results.md')
        csv_path = os.path.join(out_dir, 'ground_truth_experiment_data.csv')

        write_csv(data, csv_path)
        write_markdown(data, md_path)


if __name__ == '__main__':
    main()
