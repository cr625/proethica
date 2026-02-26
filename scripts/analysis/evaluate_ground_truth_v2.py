#!/usr/bin/env python3
"""
Ground Truth Precedent Retrieval Experiment v2

Rerun of the original ground truth experiment with updated citation data
and expanded component embedding pool (28 cases, up from 25).

Changes from v1:
- All 25 Phase 1 citations fully resolved (fixes: Case 13, 88 normalization; Case 96-8 ingested)
- 3 additional cases with component embeddings (73, 88, 130)
- Expanded divergence analysis for Experiment 1
- Strong/weak retrieval examples with explanations for Experiment 2
- Random baselines computed analytically

Output:
- ground_truth_experiment_results_v2.md
- ground_truth_experiment_data_v2.csv
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
    rows = db.session.execute(text(
        "SELECT case_id FROM case_precedent_features WHERE combined_embedding IS NOT NULL"
    )).fetchall()
    return {r[0] for r in rows}


def get_section_embedded_case_ids():
    rows = db.session.execute(text(
        "SELECT case_id FROM case_precedent_features WHERE facts_embedding IS NOT NULL"
    )).fetchall()
    return {r[0] for r in rows}


def get_citation_graph():
    rows = db.session.execute(text("""
        SELECT case_id, cited_case_ids
        FROM case_precedent_features
        WHERE cited_case_ids IS NOT NULL
          AND array_length(cited_case_ids, 1) > 0
    """)).fetchall()
    return {r[0]: list(r[1]) for r in rows}


def get_total_documents():
    return db.session.execute(text("SELECT COUNT(*) FROM documents")).scalar()


def get_case_title(case_id):
    doc = Document.query.get(case_id)
    return doc.title if doc else f"Case {case_id}"


# ---------------------------------------------------------------------------
# Retrieval: compute pairwise rankings within a pool
# ---------------------------------------------------------------------------

def rank_pool(service, source_case_id, pool_ids, use_component):
    """
    Compute similarity of source to every other case in pool_ids.
    Returns list of (case_id, score) sorted descending.
    """
    results = []
    for target_id in pool_ids:
        if target_id == source_case_id:
            continue
        sim = service.calculate_similarity(
            source_case_id, target_id,
            use_component_embedding=use_component
        )
        results.append((target_id, sim.overall_similarity))
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


def find_cited_positions(ranking, cited_ids):
    rank_map = {cid: rank for rank, (cid, _) in enumerate(ranking, start=1)}
    return {cid: rank_map.get(cid) for cid in cited_ids}


def random_baseline_recall(k, pool_size, num_cited):
    """Expected recall@k for random ranking. Hypergeometric mean / num_cited."""
    if pool_size <= 0 or num_cited <= 0:
        return 0.0
    # E[hits] = k * num_cited / pool_size, capped at num_cited
    expected_hits = min(k * num_cited / pool_size, num_cited)
    return expected_hits / num_cited


def random_baseline_mrr(pool_size, num_cited):
    """Expected MRR for random ranking with num_cited positives in pool_size candidates."""
    if pool_size <= 0 or num_cited <= 0:
        return 0.0
    # P(first hit at rank r) = C(pool-cited, r-1) * cited / C(pool, r) * pool
    # Approximation: E[1/R] where R ~ min of num_cited uniform draws from 1..pool_size
    # For simplicity: MRR ~ H(pool_size) * num_cited / pool_size (harmonic approx)
    # Better: MRR = sum_{r=1}^{pool_size} (1/r) * P(first_hit_at_r)
    # Use exact computation
    total = 0.0
    prob_no_hit_before = 1.0
    n = pool_size
    c = num_cited
    for r in range(1, n + 1):
        # P(hit at position r | no hit before r)
        remaining_positives = c  # we track this below
        remaining_total = n - (r - 1)
        if remaining_total <= 0:
            break
        p_hit = min(c, remaining_total) / remaining_total if remaining_total > 0 else 0
        # Actually, let's use a simpler approximation
        break
    # Simple approximation: E[MRR] ~ (num_cited / pool_size) * H(pool_size)
    # where H(n) = sum(1/i for i in 1..n)
    # But a better known result: for c positives among n items,
    # E[1/min_rank] = sum_{k=0}^{n-c} (-1)^k * C(n-c,k) / (k+1) * C(n,k+1)^{-1} ... complex
    # Use Monte Carlo-free approximation:
    # E[MRR] = (c/n) * sum_{r=1}^{n} (1/r) * ((n-c)/(n))^{r-1} ... geometric approx
    # Simplest correct approach for small n: iterate
    # P(first positive at rank r) = C(n-c, r-1) / C(n, r-1) * c / (n - r + 1)
    # = product_{i=0}^{r-2} (n-c-i)/(n-i) * c/(n-r+1)
    total_mrr = 0.0
    prob_no_hit = 1.0
    for r in range(1, n + 1):
        if n - r + 1 <= 0:
            break
        p_hit_at_r = prob_no_hit * c / (n - r + 1)
        total_mrr += (1.0 / r) * p_hit_at_r
        prob_no_hit *= (n - c - (r - 1)) / (n - (r - 1)) if (n - (r - 1)) > 0 and (n - c - (r - 1)) >= 0 else 0
    return total_mrr


# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------

def run_experiments(service, verbose=False):
    citation_graph = get_citation_graph()
    component_pool = get_component_embedded_case_ids()
    section_pool = get_section_embedded_case_ids()
    total_docs = get_total_documents()

    print(f"Total documents in DB: {total_docs}")
    print(f"Cases with section embeddings: {len(section_pool)}")
    print(f"Cases with component embeddings: {len(component_pool)}")
    print(f"Cases with citations: {len(citation_graph)}")
    total_edges = sum(len(v) for v in citation_graph.values())
    print(f"Total citation edges: {total_edges}")

    # ===================================================================
    # EXPERIMENT 1: Head-to-head on component pool
    # ===================================================================
    print("\n" + "=" * 70)
    print("EXPERIMENT 1: Head-to-head (component pool)")
    print("=" * 70)

    exp1_rows = []
    exp1_per_source = {}  # source_id -> {section_recalls, component_recalls, ...}

    source_count = 0
    for source_id in sorted(citation_graph.keys()):
        if source_id not in component_pool:
            continue
        cited_ids = citation_graph[source_id]
        resolvable = [c for c in cited_ids if c in component_pool]
        if not resolvable:
            continue

        source_count += 1
        pool = component_pool  # rank_pool excludes source internally
        pool_size = len(component_pool) - 1

        print(f"  Computing Case {source_id} ({source_count})...")

        section_ranking = rank_pool(service, source_id, pool, use_component=False)
        component_ranking = rank_pool(service, source_id, pool, use_component=True)

        s_positions = find_cited_positions(section_ranking, resolvable)
        c_positions = find_cited_positions(component_ranking, resolvable)

        per_source = {
            'section_recalls': {},
            'component_recalls': {},
            'section_mrr': reciprocal_rank(section_ranking, resolvable),
            'component_mrr': reciprocal_rank(component_ranking, resolvable),
            'resolvable': resolvable,
            'total_cited': len(cited_ids),
        }
        for k in [5, 10, 20]:
            per_source['section_recalls'][k] = recall_at_k(section_ranking, resolvable, k)
            per_source['component_recalls'][k] = recall_at_k(component_ranking, resolvable, k)
        exp1_per_source[source_id] = per_source

        title = get_case_title(source_id)
        for cid in resolvable:
            exp1_rows.append({
                'experiment': 1,
                'source_case_id': source_id,
                'source_title': title,
                'cited_case_id': cid,
                'cited_title': get_case_title(cid),
                'total_citations': len(cited_ids),
                'resolvable_citations': len(resolvable),
                'section_rank': s_positions.get(cid),
                'component_rank': c_positions.get(cid),
                'pool_size': pool_size,
            })

        if verbose:
            print(f"    {title[:50]}")
            for cid in resolvable:
                print(f"      -> {cid}: s={s_positions.get(cid)}, c={c_positions.get(cid)}")

    n1 = len(exp1_per_source)
    print(f"\nExp 1: {n1} source cases, {len(exp1_rows)} citation edges")

    # Aggregate exp1
    exp1_agg = {'n': n1, 'pool_size': len(component_pool)}
    if n1 > 0:
        for method in ['section', 'component']:
            for k in [5, 10, 20]:
                vals = [v[f'{method}_recalls'][k] for v in exp1_per_source.values()]
                exp1_agg[f'{method}_recall_{k}'] = sum(vals) / n1
            mrr_vals = [v[f'{method}_mrr'] for v in exp1_per_source.values()]
            exp1_agg[f'{method}_mrr'] = sum(mrr_vals) / n1

        for k in [5, 10, 20]:
            print(f"  Recall@{k}: S={exp1_agg[f'section_recall_{k}']:.3f}  C={exp1_agg[f'component_recall_{k}']:.3f}")
        print(f"  MRR:     S={exp1_agg['section_mrr']:.3f}  C={exp1_agg['component_mrr']:.3f}")

    # ===================================================================
    # EXPERIMENT 2: Section-based on full pool
    # ===================================================================
    print("\n" + "=" * 70)
    print("EXPERIMENT 2: Section-based (full pool)")
    print("=" * 70)

    exp2_rows = []
    exp2_per_source = {}

    source_count = 0
    for source_id in sorted(citation_graph.keys()):
        if source_id not in section_pool:
            continue
        cited_ids = citation_graph[source_id]
        resolvable = [c for c in cited_ids if c in section_pool]
        if not resolvable:
            continue

        source_count += 1
        pool_size = len(section_pool) - 1

        print(f"  Computing Case {source_id} ({source_count})...")

        section_ranking = rank_pool(service, source_id, section_pool, use_component=False)
        s_positions = find_cited_positions(section_ranking, resolvable)

        per_source = {
            'section_recalls': {},
            'section_mrr': reciprocal_rank(section_ranking, resolvable),
            'resolvable': resolvable,
            'total_cited': len(cited_ids),
        }
        for k in [5, 10, 20]:
            per_source['section_recalls'][k] = recall_at_k(section_ranking, resolvable, k)
        exp2_per_source[source_id] = per_source

        title = get_case_title(source_id)
        for cid in resolvable:
            exp2_rows.append({
                'experiment': 2,
                'source_case_id': source_id,
                'source_title': title,
                'cited_case_id': cid,
                'cited_title': get_case_title(cid),
                'total_citations': len(cited_ids),
                'resolvable_citations': len(resolvable),
                'section_rank': s_positions.get(cid),
                'component_rank': None,
                'pool_size': pool_size,
            })

    n2 = len(exp2_per_source)
    print(f"\nExp 2: {n2} source cases, {len(exp2_rows)} citation edges")

    exp2_agg = {'n': n2, 'pool_size': len(section_pool)}
    if n2 > 0:
        for k in [5, 10, 20]:
            vals = [v['section_recalls'][k] for v in exp2_per_source.values()]
            exp2_agg[f'section_recall_{k}'] = sum(vals) / n2
        mrr_vals = [v['section_mrr'] for v in exp2_per_source.values()]
        exp2_agg['section_mrr'] = sum(mrr_vals) / n2

        for k in [5, 10, 20]:
            print(f"  Recall@{k}: {exp2_agg[f'section_recall_{k}']:.3f}")
        print(f"  MRR:     {exp2_agg['section_mrr']:.3f}")

    return {
        'exp1_rows': exp1_rows,
        'exp1_per_source': exp1_per_source,
        'exp1_agg': exp1_agg,
        'exp2_rows': exp2_rows,
        'exp2_per_source': exp2_per_source,
        'exp2_agg': exp2_agg,
        'component_pool': component_pool,
        'section_pool': section_pool,
        'citation_graph': citation_graph,
        'total_docs': total_docs,
    }


# ---------------------------------------------------------------------------
# Output: CSV
# ---------------------------------------------------------------------------

def write_csv(data, output_path):
    all_rows = data['exp1_rows'] + data['exp2_rows']
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
    print(f"CSV written: {output_path} ({len(all_rows)} rows)")


# ---------------------------------------------------------------------------
# Output: Markdown
# ---------------------------------------------------------------------------

def write_markdown(data, output_path):
    exp1_agg = data['exp1_agg']
    exp2_agg = data['exp2_agg']
    exp1_per = data['exp1_per_source']
    exp2_per = data['exp2_per_source']
    citation_graph = data['citation_graph']

    lines = []
    lines.append("# Ground Truth Precedent Retrieval Experiment (v2)")
    lines.append("")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"**Script:** `scripts/analysis/evaluate_ground_truth_v2.py`")
    lines.append("")

    # -------------------------------------------------------------------
    # 1. Data summary
    # -------------------------------------------------------------------
    lines.append("## 1. Data Summary")
    lines.append("")
    total_edges = sum(len(v) for v in citation_graph.values())
    exp1_edges = len(data['exp1_rows'])
    exp2_edges = len(data['exp2_rows'])

    lines.append("| Metric | Count |")
    lines.append("|--------|------:|")
    lines.append(f"| Total cases in database | {data['total_docs']} |")
    lines.append(f"| Cases with section embeddings | {len(data['section_pool'])} |")
    lines.append(f"| Cases with component embeddings | {len(data['component_pool'])} |")
    lines.append(f"| Cases with expert citations (any) | {len(citation_graph)} |")
    lines.append(f"| Total citation edges (all cases) | {total_edges} |")
    lines.append(f"| Exp 1 source cases | {exp1_agg['n']} |")
    lines.append(f"| Exp 1 citation edges (resolvable in pool) | {exp1_edges} |")
    lines.append(f"| Exp 2 source cases | {exp2_agg['n']} |")
    lines.append(f"| Exp 2 citation edges (resolvable in pool) | {exp2_edges} |")
    lines.append("")

    # -------------------------------------------------------------------
    # 2. Experiment 1: Aggregate metrics
    # -------------------------------------------------------------------
    lines.append("## 2. Experiment 1: Head-to-Head Comparison")
    lines.append("")
    pool1 = exp1_agg['pool_size']
    lines.append(f"Pool: {pool1} cases with component embeddings. "
                 f"Both methods search the same {pool1 - 1}-candidate pool. "
                 f"{exp1_agg['n']} source cases with at least one cited case in the pool.")
    lines.append("")

    if exp1_agg['n'] > 0:
        lines.append("### Aggregate Metrics")
        lines.append("")
        lines.append("| Metric | Section-Based | Component-Based |")
        lines.append("|--------|:------------:|:---------------:|")
        for k in [5, 10, 20]:
            capped = min(k, pool1 - 1)
            s = exp1_agg.get(f'section_recall_{k}', 0)
            c = exp1_agg.get(f'component_recall_{k}', 0)
            label = f"Recall@{k}" if k <= capped else f"Recall@{k} (capped at {capped})"
            lines.append(f"| {label} | {s:.3f} | {c:.3f} |")
        lines.append(f"| MRR | {exp1_agg.get('section_mrr', 0):.3f} | {exp1_agg.get('component_mrr', 0):.3f} |")
        lines.append("")

        # -------------------------------------------------------------------
        # 3. Experiment 1: Per-case breakdown
        # -------------------------------------------------------------------
        lines.append("### Per-Case Breakdown")
        lines.append("")
        lines.append("| Source | Cited | Section Rank | Component Rank | Pool | Winner |")
        lines.append("|--------|-------|:------------:|:--------------:|:----:|--------|")
        for row in data['exp1_rows']:
            s_r = row['section_rank']
            c_r = row['component_rank']
            s_str = str(s_r) if s_r is not None else "---"
            c_str = str(c_r) if c_r is not None else "---"
            if s_r is not None and c_r is not None:
                if s_r < c_r:
                    winner = "section"
                elif c_r < s_r:
                    winner = "component"
                else:
                    winner = "tie"
            else:
                winner = "---"
            lines.append(f"| Case {row['source_case_id']} | Case {row['cited_case_id']} | "
                         f"{s_str} | {c_str} | {row['pool_size']} | {winner} |")
        lines.append("")

        # -------------------------------------------------------------------
        # 4. Experiment 1: Divergence analysis
        # -------------------------------------------------------------------
        lines.append("### Divergence Analysis (Top-10 Threshold)")
        lines.append("")
        lines.append("Cases where the two methods disagree on whether a cited case appears in the top 10.")
        lines.append("")

        component_wins = []
        section_wins = []
        both_miss = []
        both_hit = []

        for row in data['exp1_rows']:
            s_r = row['section_rank']
            c_r = row['component_rank']
            s_in = s_r is not None and s_r <= 10
            c_in = c_r is not None and c_r <= 10
            entry = f"Case {row['source_case_id']} -> Case {row['cited_case_id']} (s={s_r}, c={c_r})"
            if c_in and not s_in:
                component_wins.append(entry)
            elif s_in and not c_in:
                section_wins.append(entry)
            elif not s_in and not c_in:
                both_miss.append(entry)
            else:
                both_hit.append(entry)

        lines.append(f"| Category | Count |")
        lines.append(f"|----------|------:|")
        lines.append(f"| Both methods recover in top 10 | {len(both_hit)} |")
        lines.append(f"| Component-wins (component <=10, section >10) | {len(component_wins)} |")
        lines.append(f"| Section-wins (section <=10, component >10) | {len(section_wins)} |")
        lines.append(f"| Both miss (neither in top 10) | {len(both_miss)} |")
        lines.append("")

        if component_wins:
            lines.append("**Component-wins:**")
            for e in component_wins:
                lines.append(f"- {e}")
            lines.append("")
        if section_wins:
            lines.append("**Section-wins:**")
            for e in section_wins:
                lines.append(f"- {e}")
            lines.append("")
        if both_miss:
            lines.append("**Both-miss:**")
            for e in both_miss:
                lines.append(f"- {e}")
            lines.append("")

    # -------------------------------------------------------------------
    # 5. Experiment 2: Aggregate metrics
    # -------------------------------------------------------------------
    lines.append("## 3. Experiment 2: Section-Based on Full Pool")
    lines.append("")
    pool2 = exp2_agg['pool_size']
    lines.append(f"Pool: {pool2} cases with section embeddings ({pool2 - 1} candidates per source). "
                 f"{exp2_agg['n']} source cases evaluated.")
    lines.append("")

    if exp2_agg['n'] > 0:
        lines.append("### Aggregate Metrics")
        lines.append("")
        lines.append("| Metric | Section-Based |")
        lines.append("|--------|:------------:|")
        for k in [5, 10, 20]:
            s = exp2_agg.get(f'section_recall_{k}', 0)
            lines.append(f"| Recall@{k} | {s:.3f} |")
        lines.append(f"| MRR | {exp2_agg.get('section_mrr', 0):.3f} |")
        lines.append("")

        # -------------------------------------------------------------------
        # 6. Experiment 2: Per-case breakdown
        # -------------------------------------------------------------------
        lines.append("### Per-Case Breakdown")
        lines.append("")

        by_source = defaultdict(list)
        for row in data['exp2_rows']:
            by_source[row['source_case_id']].append(row)

        lines.append("| Source | Title | Cited | Section Rank | Pool |")
        lines.append("|--------|-------|-------|:------------:|:----:|")
        for sid in sorted(by_source.keys()):
            rows = by_source[sid]
            title = rows[0]['source_title'][:45]
            for i, row in enumerate(rows):
                s_r = str(row['section_rank']) if row['section_rank'] is not None else "---"
                src_col = f"Case {sid}" if i == 0 else ""
                title_col = title if i == 0 else ""
                lines.append(f"| {src_col} | {title_col} | Case {row['cited_case_id']} | "
                             f"{s_r} | {row['pool_size']} |")
        lines.append("")

        # -------------------------------------------------------------------
        # 7. Recall@10 distribution
        # -------------------------------------------------------------------
        lines.append("### Recall@10 Distribution")
        lines.append("")
        r10_vals = [v['section_recalls'][10] for v in exp2_per.values()]
        perfect = sum(1 for r in r10_vals if r == 1.0)
        partial = sum(1 for r in r10_vals if 0 < r < 1.0)
        zero = sum(1 for r in r10_vals if r == 0.0)
        n2 = exp2_agg['n']
        lines.append(f"| Category | Count | Fraction |")
        lines.append(f"|----------|------:|---------:|")
        lines.append(f"| Perfect (1.0) | {perfect} | {perfect/n2:.1%} |")
        lines.append(f"| Partial (0 < r < 1) | {partial} | {partial/n2:.1%} |")
        lines.append(f"| Zero (0.0) | {zero} | {zero/n2:.1%} |")
        lines.append("")

    # -------------------------------------------------------------------
    # 8. Random baselines
    # -------------------------------------------------------------------
    lines.append("## 4. Random Baselines")
    lines.append("")
    lines.append("Expected performance of a random ranking, computed analytically.")
    lines.append("")

    # Exp 1 baseline
    if exp1_agg['n'] > 0:
        pool1_candidates = pool1 - 1
        # Average number of resolvable citations per source in Exp 1
        avg_cited_1 = len(data['exp1_rows']) / exp1_agg['n'] if exp1_agg['n'] > 0 else 1

        lines.append(f"**Experiment 1** (pool = {pool1_candidates} candidates, "
                     f"avg {avg_cited_1:.1f} cited per source):")
        lines.append("")
        lines.append("| Metric | Random Baseline |")
        lines.append("|--------|:--------------:|")
        for k in [5, 10, 20]:
            capped = min(k, pool1_candidates)
            rb = random_baseline_recall(capped, pool1_candidates, avg_cited_1)
            lines.append(f"| Recall@{k} | {rb:.3f} |")
        rb_mrr = random_baseline_mrr(pool1_candidates, avg_cited_1)
        lines.append(f"| MRR | {rb_mrr:.3f} |")
        lines.append("")

    # Exp 2 baseline
    if exp2_agg['n'] > 0:
        pool2_candidates = pool2 - 1
        avg_cited_2 = len(data['exp2_rows']) / exp2_agg['n'] if exp2_agg['n'] > 0 else 1

        lines.append(f"**Experiment 2** (pool = {pool2_candidates} candidates, "
                     f"avg {avg_cited_2:.1f} cited per source):")
        lines.append("")
        lines.append("| Metric | Random Baseline |")
        lines.append("|--------|:--------------:|")
        for k in [5, 10, 20]:
            rb = random_baseline_recall(k, pool2_candidates, avg_cited_2)
            lines.append(f"| Recall@{k} | {rb:.3f} |")
        rb_mrr = random_baseline_mrr(pool2_candidates, avg_cited_2)
        lines.append(f"| MRR | {rb_mrr:.3f} |")
        lines.append("")

    # -------------------------------------------------------------------
    # 9. Interpretation
    # -------------------------------------------------------------------
    lines.append("## 5. Interpretation")
    lines.append("")

    # Experiment 1 interpretation
    if exp1_agg['n'] > 0:
        lines.append("### Experiment 1: Component vs Section Head-to-Head")
        lines.append("")

        s10 = exp1_agg.get('section_recall_10', 0)
        c10 = exp1_agg.get('component_recall_10', 0)
        s_mrr = exp1_agg.get('section_mrr', 0)
        c_mrr = exp1_agg.get('component_mrr', 0)

        if c10 > s10:
            lines.append(f"Component-based retrieval outperforms section-based at Recall@10 "
                         f"({c10:.3f} vs {s10:.3f}), recovering a larger fraction of expert-cited "
                         f"cases within the top 10 results.")
        elif s10 > c10:
            lines.append(f"Section-based retrieval outperforms component-based at Recall@10 "
                         f"({s10:.3f} vs {c10:.3f}).")
        else:
            lines.append(f"Both methods achieve identical Recall@10 ({s10:.3f}).")

        if c_mrr > s_mrr:
            lines.append(f" Component-based MRR ({c_mrr:.3f}) exceeds section-based ({s_mrr:.3f}), "
                         f"indicating that the first relevant cited case tends to appear at a higher "
                         f"rank in the component ranking.")
        elif s_mrr > c_mrr:
            lines.append(f" Section-based MRR ({s_mrr:.3f}) exceeds component-based ({c_mrr:.3f}).")
        lines.append("")

        # Count wins
        s_win = sum(1 for r in data['exp1_rows']
                    if r['section_rank'] is not None and r['component_rank'] is not None
                    and r['section_rank'] < r['component_rank'])
        c_win = sum(1 for r in data['exp1_rows']
                    if r['section_rank'] is not None and r['component_rank'] is not None
                    and r['component_rank'] < r['section_rank'])
        tie = sum(1 for r in data['exp1_rows']
                  if r['section_rank'] is not None and r['component_rank'] is not None
                  and r['section_rank'] == r['component_rank'])
        lines.append(f"Per-citation rank comparison: component ranks the cited case higher in "
                     f"{c_win} of {len(data['exp1_rows'])} edges, section in {s_win}, tied in {tie}.")
        lines.append("")

        n_comp_wins = len(component_wins)
        n_sec_wins = len(section_wins)
        n_both_miss = len(both_miss)
        lines.append(f"At the top-10 threshold: {n_comp_wins} citation edges are recovered by "
                     f"component but not section, {n_sec_wins} by section but not component, "
                     f"and {n_both_miss} are missed by both methods.")
        lines.append("")

    # Experiment 2 interpretation
    if exp2_agg['n'] > 0:
        lines.append("### Experiment 2: Section-Based Full-Pool Performance")
        lines.append("")
        s10_2 = exp2_agg.get('section_recall_10', 0)
        s_mrr_2 = exp2_agg.get('section_mrr', 0)

        # Random baselines for comparison
        pool2c = pool2 - 1
        avg_c2 = len(data['exp2_rows']) / n2
        rb10 = random_baseline_recall(10, pool2c, avg_c2)
        rb_mrr2 = random_baseline_mrr(pool2c, avg_c2)

        lift_r10 = s10_2 / rb10 if rb10 > 0 else float('inf')
        lift_mrr = s_mrr_2 / rb_mrr2 if rb_mrr2 > 0 else float('inf')

        lines.append(f"Section-based Recall@10 = {s10_2:.3f} against a {pool2c}-candidate pool, "
                     f"representing a {lift_r10:.1f}x lift over the random baseline ({rb10:.3f}). "
                     f"MRR = {s_mrr_2:.3f} ({lift_mrr:.1f}x over random {rb_mrr2:.3f}).")
        lines.append("")
        lines.append(f"Of {n2} source cases, {perfect} ({perfect/n2:.0%}) achieve perfect Recall@10 "
                     f"(all cited cases in top 10), {partial} ({partial/n2:.0%}) achieve partial recall, "
                     f"and {zero} ({zero/n2:.0%}) achieve zero recall.")
        lines.append("")

        # Component method comparison
        lines.append("### Component Method Assessment")
        lines.append("")
        if exp1_agg['n'] > 0:
            c10_1 = exp1_agg.get('component_recall_10', 0)
            s10_1 = exp1_agg.get('section_recall_10', 0)
            diff = c10_1 - s10_1
            if abs(diff) < 0.02:
                lines.append("On the citation ground truth, the component method performs comparably "
                             "to the section method within the component-embedded pool. The structured "
                             "9-component decomposition does not yield a clear advantage for recovering "
                             "expert-cited precedents, though it may offer benefits for interpretability "
                             "and per-component analysis that are not captured by aggregate recall metrics.")
            elif diff > 0:
                lines.append(f"The component method shows a {diff:.3f} improvement in Recall@10 over "
                             f"the section method within the component pool. This suggests that the "
                             f"structured 9-component decomposition captures ethically relevant similarity "
                             f"dimensions that monolithic section embeddings miss.")
            else:
                lines.append(f"The section method outperforms the component method by {-diff:.3f} in "
                             f"Recall@10 within the component pool. The monolithic section embeddings "
                             f"capture citation-relevant similarity more effectively than the weighted "
                             f"component decomposition on this ground truth.")
        lines.append("")

        # Strong retrievals
        lines.append("### Strong Retrieval Examples (Experiment 2)")
        lines.append("")

        # Find cases with best recall (all citations found in top positions)
        scored = []
        for sid, ps in exp2_per.items():
            avg_rank = 0
            count = 0
            for row in data['exp2_rows']:
                if row['source_case_id'] == sid and row['section_rank'] is not None:
                    avg_rank += row['section_rank']
                    count += 1
            if count > 0:
                avg_rank /= count
                scored.append((sid, ps['section_recalls'][10], avg_rank, ps['resolvable']))

        # Sort: best recall first, then lowest avg rank
        scored.sort(key=lambda x: (-x[1], x[2]))

        # Top 5 strong
        strong = scored[:5]
        for sid, r10, avg_r, resolvable in strong:
            title = get_case_title(sid)[:60]
            n_cited = len(resolvable)
            ranks = []
            for row in data['exp2_rows']:
                if row['source_case_id'] == sid:
                    ranks.append(str(row['section_rank']) if row['section_rank'] else "---")
            ranks_str = ", ".join(ranks)
            lines.append(f"- **Case {sid}** ({title}): Recall@10={r10:.2f}, "
                         f"{n_cited} citation(s), ranks=[{ranks_str}]")
        lines.append("")

        # Weak retrievals: worst recall, highest avg rank
        scored.sort(key=lambda x: (x[1], -x[2]))
        weak = scored[:5]
        lines.append("### Weak Retrieval Examples (Experiment 2)")
        lines.append("")
        for sid, r10, avg_r, resolvable in weak:
            title = get_case_title(sid)[:60]
            n_cited = len(resolvable)
            ranks = []
            for row in data['exp2_rows']:
                if row['source_case_id'] == sid:
                    ranks.append(str(row['section_rank']) if row['section_rank'] else "---")
            ranks_str = ", ".join(ranks)
            lines.append(f"- **Case {sid}** ({title}): Recall@10={r10:.2f}, "
                         f"{n_cited} citation(s), ranks=[{ranks_str}]")
        lines.append("")

    # -------------------------------------------------------------------
    # Notes
    # -------------------------------------------------------------------
    lines.append("## 6. Notes")
    lines.append("")
    lines.append("1. **Citation as lower bound.** Board members cite the most salient precedents, "
                 "not all related cases. A similar but uncited case is not necessarily irrelevant. "
                 "These metrics underestimate true retrieval quality.")
    lines.append("")
    lines.append(f"2. **Component embedding coverage.** {len(data['component_pool'])} of "
                 f"{len(data['section_pool'])} cases have component embeddings (requires "
                 f"9-component entity extraction). Experiment 1 evaluates on a smaller pool; "
                 f"generating component embeddings for all cases would enable full-pool comparison.")
    lines.append("")
    lines.append("3. **Asymmetric citations.** If Case A cites Case B, Case B does not necessarily "
                 "cite Case A. The citation graph is directed.")
    lines.append("")
    lines.append("4. **Changes from v1.** All 25 Phase 1 citations fully resolved (Case 13: "
                 "05-04->05-4, Case 88: 07.6->07-6, Case 96-8 ingested). Component pool "
                 "remains the same 25 Phase 1 cases. Section pool increased from 117 to "
                 f"{len(data['section_pool'])} cases.")
    lines.append("")

    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"Markdown written: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Ground truth retrieval experiment v2')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--output-dir', default=None)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        service = PrecedentSimilarityService()

        print("Ground Truth Precedent Retrieval Experiment v2")
        print("=" * 70)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print()

        data = run_experiments(service, verbose=args.verbose)

        out_dir = args.output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'docs-internal', 'conferences_submissions', 'iccbr'
        )
        os.makedirs(out_dir, exist_ok=True)

        csv_path = os.path.join(out_dir, 'ground_truth_experiment_data_v2.csv')
        md_path = os.path.join(out_dir, 'ground_truth_experiment_results_v2.md')

        write_csv(data, csv_path)
        write_markdown(data, md_path)

        print("\nDone.")


if __name__ == '__main__':
    main()
