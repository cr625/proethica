#!/usr/bin/env python3
"""
Standalone reproduction of ICCBR 2026 experiments.

Verifies all experiment results from pre-computed features without requiring
the ProEthica application stack, database, or LLM API keys.

Requirements: numpy, scipy (pip install numpy scipy)

Usage:
    python reproduce.py              # run all experiments
    python reproduce.py 1 3 6        # run specific experiments
    python reproduce.py --verify     # compare against committed CSV files
"""

import os
import sys
import csv
import pickle
import argparse
from collections import defaultdict

import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPONENT_ORDER = ['R', 'P', 'O', 'S', 'Rs', 'A', 'E', 'Ca', 'Cs']

COMPONENT_WEIGHTS = {
    'R': 0.12, 'S': 0.10, 'Rs': 0.10, 'P': 0.20, 'O': 0.15,
    'Cs': 0.08, 'Ca': 0.07, 'A': 0.10, 'E': 0.08,
}

COMPONENT_LABELS = {
    'R': 'Roles', 'P': 'Principles', 'O': 'Obligations',
    'S': 'States', 'Rs': 'Resources', 'A': 'Actions',
    'E': 'Events', 'Ca': 'Capabilities', 'Cs': 'Constraints',
}

# Paper weights: 0.40 embedding + 0.60 set-based
PAPER_W = {
    'embedding': 0.40,
    'provision_overlap': 0.25,
    'outcome_alignment': 0.15,
    'tag_overlap': 0.10,
    'principle_overlap': 0.10,
}

# Section embedding sub-weights normalized to 1.0
SECTION_W = {'facts': 0.15 / 0.40, 'discussion': 0.25 / 0.40}

# Set-feature sub-weights normalized to 1.0
SET_W = {
    'provision_overlap': 0.25 / 0.60,
    'outcome_alignment': 0.15 / 0.60,
    'tag_overlap': 0.10 / 0.60,
    'principle_overlap': 0.10 / 0.60,
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data():
    """Load pre-computed features from pickle."""
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    pkl_path = os.path.join(data_dir, 'features.pkl')

    if not os.path.exists(pkl_path):
        print(f"ERROR: {pkl_path} not found.")
        print("Run from the experiments/iccbr-2026/ directory or ensure data/features.pkl exists.")
        sys.exit(1)

    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)

    return data['features'], data['citation_graph'], data['titles']


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def cosine_sim(v1, v2):
    if v1 is None or v2 is None:
        return 0.0
    a = np.asarray(v1).flatten()
    b = np.asarray(v2).flatten()
    if len(a) != len(b):
        return 0.0
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def jaccard(sa, sb):
    if not sa and not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union > 0 else 0.0


def outcome_align(a, b):
    if a is None or b is None:
        return 0.5
    if a == b:
        return 1.0
    if {a, b} == {'ethical', 'unethical'}:
        return 0.0
    return 0.5


def principle_overlap(ta, tb):
    if not ta or not tb:
        return 0.0
    def ext(t):
        p = set()
        for x in t:
            if isinstance(x, dict):
                p.add(x.get('principle1', ''))
                p.add(x.get('principle2', ''))
        p.discard('')
        return p
    return jaccard(ext(ta), ext(tb))


def compute_raw_scores(src, tgt):
    """Compute all raw similarity scores for one case pair."""
    # Section embedding
    facts_sim = cosine_sim(src.get('facts_embedding'), tgt.get('facts_embedding'))
    disc_sim = cosine_sim(src.get('discussion_embedding'), tgt.get('discussion_embedding'))
    section_emb = SECTION_W['facts'] * facts_sim + SECTION_W['discussion'] * disc_sim

    # Combined D-tuple embedding
    combined_emb = cosine_sim(src.get('combined_embedding'), tgt.get('combined_embedding'))

    # Per-component D-tuple embedding
    weighted_sum = 0.0
    total_w = 0.0
    comp_sims = {}
    for code in COMPONENT_ORDER:
        se = src.get(f'embedding_{code}')
        te = tgt.get(f'embedding_{code}')
        if se is not None and te is not None:
            s = cosine_sim(se, te)
            w = COMPONENT_WEIGHTS.get(code, 0.0)
            weighted_sum += w * s
            total_w += w
            comp_sims[code] = s
    component_emb = weighted_sum / total_w if total_w > 0 else 0.0

    # Set-based features
    prov = jaccard(
        set(src.get('provisions_cited', [])),
        set(tgt.get('provisions_cited', []))
    )
    out = outcome_align(src.get('outcome_type'), tgt.get('outcome_type'))
    tags = jaccard(
        set(src.get('subject_tags', [])),
        set(tgt.get('subject_tags', []))
    )
    princ = principle_overlap(
        src.get('principle_tensions', []),
        tgt.get('principle_tensions', [])
    )
    set_score = (
        SET_W['provision_overlap'] * prov
        + SET_W['outcome_alignment'] * out
        + SET_W['tag_overlap'] * tags
        + SET_W['principle_overlap'] * princ
    )

    return {
        'section_emb': section_emb,
        'combined_emb': combined_emb,
        'component_emb': component_emb,
        'set_score': set_score,
        'comp_sims': comp_sims,
    }


EMB_KEYS = {
    'section': 'section_emb',
    'combined': 'combined_emb',
    'component': 'component_emb',
}
METHODS = ['section', 'combined', 'component']


def build_score_matrix(features):
    """Pre-compute all pairwise raw scores. Returns dict[(src,tgt)] -> scores."""
    case_ids = sorted(features.keys())
    matrix = {}
    n = len(case_ids)
    for i, src_id in enumerate(case_ids):
        for j, tgt_id in enumerate(case_ids):
            if src_id == tgt_id:
                continue
            matrix[(src_id, tgt_id)] = compute_raw_scores(
                features[src_id], features[tgt_id]
            )
    return matrix


def rank_cases(source_id, pool_ids, score_matrix, method, alpha=0.40):
    """Rank candidates for a source case by method at given alpha."""
    emb_key = EMB_KEYS[method]
    results = []
    for tgt_id in pool_ids:
        if tgt_id == source_id:
            continue
        scores = score_matrix[(source_id, tgt_id)]
        overall = alpha * scores[emb_key] + (1 - alpha) * scores['set_score']
        results.append((tgt_id, overall))
    results.sort(key=lambda x: -x[1])
    return results


def recall_at_k(ranking, cited_ids, k):
    if not cited_ids:
        return 0.0
    top_k = {cid for cid, _ in ranking[:k]}
    return len(set(cited_ids) & top_k) / len(cited_ids)


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
    return len(ranking) + 1


def random_baseline_recall(k, pool_size, num_cited):
    if pool_size <= 0 or num_cited <= 0:
        return 0.0
    return min(k * num_cited / pool_size, num_cited) / num_cited


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


def get_sources(features, citation_graph):
    """Filter to source cases with resolvable citations in the pool."""
    pool = set(features.keys())
    sources = {}
    for src_id in sorted(citation_graph.keys()):
        if src_id not in pool:
            continue
        resolvable = [c for c in citation_graph[src_id] if c in pool]
        if resolvable:
            sources[src_id] = resolvable
    return sources


# ---------------------------------------------------------------------------
# Experiment 1: Three-Way Retrieval Comparison
# ---------------------------------------------------------------------------

def experiment_1(features, citation_graph, titles, score_matrix):
    """Three-way embedding comparison at paper weights (alpha=0.40)."""
    print("=" * 60)
    print("Experiment 1: Three-Way Retrieval Comparison")
    print("=" * 60)

    pool_ids = sorted(features.keys())
    sources = get_sources(features, citation_graph)
    pool_size = len(pool_ids) - 1

    print(f"Cases: {len(pool_ids)}, Sources: {len(sources)}, "
          f"Edges: {sum(len(v) for v in sources.values())}")

    per_source = {}
    per_edge = []

    for src_id, resolvable in sorted(sources.items()):
        src_data = {}
        for method in METHODS:
            ranking = rank_cases(src_id, pool_ids, score_matrix, method, alpha=0.40)
            src_data[f'{method}_mrr'] = reciprocal_rank(ranking, resolvable)
            for k in [5, 10, 20]:
                src_data[f'{method}_r{k}'] = recall_at_k(ranking, resolvable, k)

            for cid in resolvable:
                if method == 'section':
                    per_edge_entry = next(
                        (e for e in per_edge
                         if e['source_case_id'] == src_id and e['cited_case_id'] == cid),
                        None
                    )
                    if per_edge_entry is None:
                        per_edge_entry = {
                            'source_case_id': src_id,
                            'cited_case_id': cid,
                        }
                        per_edge.append(per_edge_entry)
                    per_edge_entry['section_rank'] = find_rank(ranking, cid)
                    per_edge_entry['pool_size'] = pool_size
                else:
                    entry = next(
                        e for e in per_edge
                        if e['source_case_id'] == src_id and e['cited_case_id'] == cid
                    )
                    entry[f'{method}_rank'] = find_rank(ranking, cid)

        per_source[src_id] = src_data

    # Aggregate
    n = len(per_source)
    agg = {}
    for method in METHODS:
        for k in [5, 10, 20]:
            vals = [v[f'{method}_r{k}'] for v in per_source.values()]
            agg[f'{method}_r{k}'] = sum(vals) / n
        mrr_vals = [v[f'{method}_mrr'] for v in per_source.values()]
        agg[f'{method}_mrr'] = sum(mrr_vals) / n

    avg_cited = len(per_edge) / n
    for k in [5, 10, 20]:
        agg[f'random_r{k}'] = random_baseline_recall(k, pool_size, avg_cited)
    agg['random_mrr'] = random_baseline_mrr(pool_size, avg_cited)

    print(f"\n{'Metric':<12} {'Section':>8} {'Combined':>9} {'Per-comp':>9} {'Random':>8}")
    print(f"{'MRR':<12} {agg['section_mrr']:>8.3f} {agg['combined_mrr']:>9.3f} "
          f"{agg['component_mrr']:>9.3f} {agg['random_mrr']:>8.3f}")
    for k in [5, 10, 20]:
        print(f"{'Recall@' + str(k):<12} {agg[f'section_r{k}']:>8.3f} "
              f"{agg[f'combined_r{k}']:>9.3f} {agg[f'component_r{k}']:>9.3f} "
              f"{agg[f'random_r{k}']:>8.3f}")

    return agg


# ---------------------------------------------------------------------------
# Experiment 2: Citation Text Ablation (verify from CSV only)
# ---------------------------------------------------------------------------

def experiment_2():
    """Verify citation ablation results from committed CSV.

    This experiment requires the original case text and sentence-transformers
    to re-embed stripped discussions. The CSV contains the pre-computed results.
    """
    print("\n" + "=" * 60)
    print("Experiment 2: Citation Text Ablation (verify from CSV)")
    print("=" * 60)

    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'ablation_citation_text.csv')
    if not os.path.exists(csv_path):
        print("  SKIP: ablation_citation_text.csv not found")
        return None

    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    # Compute metrics per condition
    conditions = defaultdict(list)
    for row in rows:
        conditions[row['condition']].append(row)

    print(f"  Conditions: {sorted(conditions.keys())}")
    print(f"  Edges per condition: {len(rows) // len(conditions)}")

    for condition in ['original', 'stripped']:
        edges = conditions[condition]
        # Group by source case
        by_source = defaultdict(list)
        for e in edges:
            by_source[int(e['source_case_id'])].append(e)

        mrr_vals = []
        recall_vals = {5: [], 10: [], 20: []}
        for src_id, src_edges in by_source.items():
            cited_ids = [int(e['cited_case_id']) for e in src_edges]
            ranks = [int(e['rank']) for e in src_edges]
            pool = int(src_edges[0]['resolvable_count'])

            # MRR: best rank among cited
            best_rank = min(ranks)
            mrr_vals.append(1.0 / best_rank)

            # Recall@k
            for k in [5, 10, 20]:
                hits = sum(1 for r in ranks if r <= k)
                recall_vals[k].append(hits / len(cited_ids))

        n = len(by_source)
        print(f"\n  {condition}: MRR={np.mean(mrr_vals):.3f}, "
              f"R@5={np.mean(recall_vals[5]):.3f}, "
              f"R@10={np.mean(recall_vals[10]):.3f}, "
              f"R@20={np.mean(recall_vals[20]):.3f}")

    return True


# ---------------------------------------------------------------------------
# Experiment 3: Embedding-Only Ablation
# ---------------------------------------------------------------------------

def experiment_3(features, citation_graph, titles, score_matrix):
    """Embedding-only and set-only ablation."""
    print("\n" + "=" * 60)
    print("Experiment 3: Embedding-Only Ablation")
    print("=" * 60)

    pool_ids = sorted(features.keys())
    sources = get_sources(features, citation_graph)
    pool_size = len(pool_ids) - 1

    # Four conditions: emb-section, emb-combined, emb-component, set-only
    # Each uses alpha=1.0 (emb-only) or alpha=0.0 (set-only)
    conditions = {
        'emb_section': ('section', 1.0),
        'emb_combined': ('combined', 1.0),
        'emb_component': ('component', 1.0),
        'set_only': ('section', 0.0),  # method irrelevant at alpha=0
    }

    agg = {}
    for cond_name, (method, alpha) in conditions.items():
        mrr_vals = []
        recall_vals = {5: [], 10: [], 20: []}

        for src_id, resolvable in sorted(sources.items()):
            ranking = rank_cases(src_id, pool_ids, score_matrix, method, alpha=alpha)
            mrr_vals.append(reciprocal_rank(ranking, resolvable))
            for k in [5, 10, 20]:
                recall_vals[k].append(recall_at_k(ranking, resolvable, k))

        n = len(sources)
        agg[f'{cond_name}_mrr'] = sum(mrr_vals) / n
        for k in [5, 10, 20]:
            agg[f'{cond_name}_r{k}'] = sum(recall_vals[k]) / n

    avg_cited = sum(len(v) for v in sources.values()) / len(sources)
    agg['random_mrr'] = random_baseline_mrr(pool_size, avg_cited)
    for k in [5, 10, 20]:
        agg[f'random_r{k}'] = random_baseline_recall(k, pool_size, avg_cited)

    print(f"\n{'Metric':<12} {'Emb-Sec':>8} {'Emb-Comb':>9} "
          f"{'Emb-Comp':>9} {'Set-Only':>9} {'Random':>8}")
    print(f"{'MRR':<12} {agg['emb_section_mrr']:>8.3f} "
          f"{agg['emb_combined_mrr']:>9.3f} {agg['emb_component_mrr']:>9.3f} "
          f"{agg['set_only_mrr']:>9.3f} {agg['random_mrr']:>8.3f}")
    for k in [5, 10, 20]:
        print(f"{'Recall@' + str(k):<12} {agg[f'emb_section_r{k}']:>8.3f} "
              f"{agg[f'emb_combined_r{k}']:>9.3f} "
              f"{agg[f'emb_component_r{k}']:>9.3f} "
              f"{agg[f'set_only_r{k}']:>9.3f} {agg[f'random_r{k}']:>8.3f}")

    return agg


# ---------------------------------------------------------------------------
# Experiment 4: Rank Correlation
# ---------------------------------------------------------------------------

def experiment_4(features, titles, score_matrix):
    """Pairwise rank correlation across all cases."""
    print("\n" + "=" * 60)
    print("Experiment 4: Rank Correlation")
    print("=" * 60)

    pool_ids = sorted(features.keys())
    per_case = []

    for case_id in pool_ids:
        rankings = {}
        for method in METHODS:
            ranking = rank_cases(case_id, pool_ids, score_matrix, method, alpha=0.40)
            rankings[method] = ranking

        # Spearman rho between rank vectors
        # Build rank vectors (same ordering of targets)
        targets = [cid for cid, _ in rankings['section']]
        rank_vecs = {}
        for method in METHODS:
            rank_map = {cid: r for r, (cid, _) in enumerate(rankings[method], 1)}
            rank_vecs[method] = [rank_map.get(t, len(targets)) for t in targets]

        rho_sc = stats.spearmanr(rank_vecs['section'], rank_vecs['combined']).statistic
        rho_sp = stats.spearmanr(rank_vecs['section'], rank_vecs['component']).statistic
        rho_cp = stats.spearmanr(rank_vecs['combined'], rank_vecs['component']).statistic

        # Overlap@10
        top10 = {}
        for method in METHODS:
            top10[method] = {cid for cid, _ in rankings[method][:10]}

        ol_sc = len(top10['section'] & top10['combined']) / 10
        ol_sp = len(top10['section'] & top10['component']) / 10
        ol_cp = len(top10['combined'] & top10['component']) / 10

        per_case.append({
            'case_id': case_id,
            'rho_sec_comb': rho_sc, 'rho_sec_comp': rho_sp, 'rho_comb_comp': rho_cp,
            'ol_sec_comb': ol_sc, 'ol_sec_comp': ol_sp, 'ol_comb_comp': ol_cp,
        })

    n = len(per_case)
    mean_rho_sc = sum(c['rho_sec_comb'] for c in per_case) / n
    mean_rho_sp = sum(c['rho_sec_comp'] for c in per_case) / n
    mean_rho_cp = sum(c['rho_comb_comp'] for c in per_case) / n
    mean_ol_sc = sum(c['ol_sec_comb'] for c in per_case) / n
    mean_ol_sp = sum(c['ol_sec_comp'] for c in per_case) / n
    mean_ol_cp = sum(c['ol_comb_comp'] for c in per_case) / n

    print(f"\n{'Metric':<20} {'Sec vs Comb':>12} {'Sec vs Comp':>12} {'Comb vs Comp':>13}")
    print(f"{'Mean Spearman rho':<20} {mean_rho_sc:>12.3f} {mean_rho_sp:>12.3f} {mean_rho_cp:>13.3f}")
    print(f"{'Mean Overlap@10':<20} {mean_ol_sc:>12.3f} {mean_ol_sp:>12.3f} {mean_ol_cp:>13.3f}")

    # Most divergent (section vs per-component)
    by_rho = sorted(per_case, key=lambda c: c['rho_sec_comp'])
    print("\nMost divergent cases (section vs per-component):")
    for c in by_rho[:5]:
        print(f"  Case {c['case_id']} (rho={c['rho_sec_comp']:.3f}): "
              f"{titles.get(c['case_id'], '')[:60]}")

    return {
        'mean_rho_sc': mean_rho_sc, 'mean_rho_sp': mean_rho_sp, 'mean_rho_cp': mean_rho_cp,
        'mean_ol_sc': mean_ol_sc, 'mean_ol_sp': mean_ol_sp, 'mean_ol_cp': mean_ol_cp,
    }


# ---------------------------------------------------------------------------
# Experiment 5: Divergent Component Analysis
# ---------------------------------------------------------------------------

def experiment_5(features, titles, score_matrix):
    """Per-component similarity for the three most divergent cases."""
    print("\n" + "=" * 60)
    print("Experiment 5: Divergent Component Analysis")
    print("=" * 60)

    pool_ids = sorted(features.keys())
    divergent_cases = [19, 105, 141]

    all_rows = []
    for case_id in divergent_cases:
        # Rank by per-component method at paper weights
        ranking = rank_cases(case_id, pool_ids, score_matrix, 'component', alpha=0.40)
        top10 = ranking[:10]

        print(f"\nCase {case_id}: {titles.get(case_id, '')}")
        for rank, (tgt_id, overall) in enumerate(top10, 1):
            scores = score_matrix[(case_id, tgt_id)]
            row = {
                'source_id': case_id,
                'source_title': titles.get(case_id, ''),
                'target_id': tgt_id,
                'target_title': titles.get(tgt_id, ''),
                'rank': rank,
                'weighted_similarity': round(scores['component_emb'], 4),
            }
            for code in COMPONENT_ORDER:
                row[f'sim_{code}'] = round(scores['comp_sims'].get(code, 0), 4)
            all_rows.append(row)

        # Component stats
        print(f"  {'Component':<15} {'StdDev':>7}")
        for code in COMPONENT_ORDER:
            vals = [score_matrix[(case_id, tgt_id)]['comp_sims'].get(code, 0)
                    for tgt_id, _ in top10]
            print(f"  {COMPONENT_LABELS[code]:<15} {np.std(vals):.4f}")

    return all_rows


# ---------------------------------------------------------------------------
# Experiment 6: Weight Sweep
# ---------------------------------------------------------------------------

def experiment_6(features, citation_graph, titles, score_matrix):
    """Recall@10 as a function of embedding weight alpha."""
    print("\n" + "=" * 60)
    print("Experiment 6: Weight Sweep")
    print("=" * 60)

    pool_ids = sorted(features.keys())
    sources = get_sources(features, citation_graph)
    alphas = [round(a * 0.05, 2) for a in range(21)]

    print(f"\n{'Alpha':>6} {'Section':>9} {'Combined':>9} {'Per-comp':>9}")
    results = []

    for alpha in alphas:
        row = {'alpha': alpha}
        for method in METHODS:
            mrr_vals = []
            recall_vals = {5: [], 10: [], 20: []}
            for src_id, resolvable in sources.items():
                ranking = rank_cases(src_id, pool_ids, score_matrix, method, alpha=alpha)
                mrr_vals.append(reciprocal_rank(ranking, resolvable))
                for k in [5, 10, 20]:
                    recall_vals[k].append(recall_at_k(ranking, resolvable, k))
            n = len(sources)
            row[f'{method}_mrr'] = sum(mrr_vals) / n
            for k in [5, 10, 20]:
                row[f'{method}_r{k}'] = sum(recall_vals[k]) / n
        results.append(row)

        marker = " <-- paper" if alpha == 0.40 else ""
        print(f"  {alpha:.2f} {row['section_r10']:>9.3f} {row['combined_r10']:>9.3f} "
              f"{row['component_r10']:>9.3f}{marker}")

    # Optimal alpha per method
    print(f"\n{'Method':<12} {'Opt Alpha':>10} {'R@10 Opt':>9} {'R@10 0.40':>10}")
    for method in METHODS:
        best = max(results, key=lambda r: r[f'{method}_r10'])
        at_40 = next(r for r in results if r['alpha'] == 0.40)
        print(f"  {method:<10} {best['alpha']:>10.2f} {best[f'{method}_r10']:>9.3f} "
              f"{at_40[f'{method}_r10']:>10.3f}")

    return results


# ---------------------------------------------------------------------------
# Verification against committed CSV files
# ---------------------------------------------------------------------------

def verify_against_csv(agg_exp1, agg_exp3, sweep_results):
    """Compare computed results against committed CSV files."""
    print("\n" + "=" * 60)
    print("VERIFICATION: Comparing against committed CSV files")
    print("=" * 60)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    all_pass = True

    # Check Experiment 1 against retrieval_aggregate.csv
    agg_path = os.path.join(base_dir, 'retrieval_aggregate.csv')
    if os.path.exists(agg_path) and agg_exp1:
        with open(agg_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                metric = row['metric']
                for method in ['section', 'combined', 'component', 'random']:
                    csv_val = float(row[method])
                    key = f'{method}_mrr' if metric == 'MRR' else f'{method}_r{metric.split("@")[1]}'
                    computed = agg_exp1.get(key, 0)
                    if abs(csv_val - computed) > 0.001:
                        print(f"  MISMATCH Exp1 {metric}/{method}: CSV={csv_val:.3f} computed={computed:.3f}")
                        all_pass = False
        if all_pass:
            print("  Experiment 1: PASS (matches retrieval_aggregate.csv)")

    # Check Experiment 6 against weight_sweep_data.csv
    sweep_path = os.path.join(base_dir, 'weight_sweep_data.csv')
    if os.path.exists(sweep_path) and sweep_results:
        sweep_pass = True
        with open(sweep_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                alpha = float(row['alpha'])
                method = row['method']
                csv_r10 = float(row['Recall@10'])
                computed_row = next((r for r in sweep_results if abs(r['alpha'] - alpha) < 0.001), None)
                if computed_row:
                    computed_r10 = computed_row[f'{method}_r10']
                    if abs(csv_r10 - computed_r10) > 0.001:
                        print(f"  MISMATCH Exp6 alpha={alpha}/{method}: "
                              f"CSV={csv_r10:.3f} computed={computed_r10:.3f}")
                        sweep_pass = False
                        all_pass = False
        if sweep_pass:
            print("  Experiment 6: PASS (matches weight_sweep_data.csv)")

    # Cross-validate: sweep at alpha=1.0 should match Exp 3 embedding-only
    if sweep_results and agg_exp3:
        xval_pass = True
        at_100 = next((r for r in sweep_results if r['alpha'] == 1.0), None)
        if at_100:
            checks = [
                ('section', 'emb_section'), ('combined', 'emb_combined'),
                ('component', 'emb_component'),
            ]
            for sweep_method, abl_key in checks:
                sv = at_100[f'{sweep_method}_r10']
                av = agg_exp3[f'{abl_key}_r10']
                if abs(sv - av) > 0.001:
                    print(f"  MISMATCH cross-val alpha=1.0 {sweep_method}: "
                          f"sweep={sv:.3f} ablation={av:.3f}")
                    xval_pass = False
                    all_pass = False
            if xval_pass:
                print("  Cross-validation (sweep alpha=1.0 vs ablation): PASS")

    if all_pass:
        print("\n  All verifications passed.")
    return all_pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Reproduce ICCBR 2026 experiments from pre-computed features'
    )
    parser.add_argument(
        'experiments', nargs='*', type=int, default=[],
        help='Experiment numbers to run (default: all)'
    )
    parser.add_argument(
        '--verify', action='store_true',
        help='Verify results against committed CSV files'
    )
    args = parser.parse_args()

    run_all = not args.experiments
    to_run = set(args.experiments) if args.experiments else {1, 2, 3, 4, 5, 6}

    print("ICCBR 2026 Experiment Reproduction")
    print("=" * 60)

    # Load data
    features, citation_graph, titles = load_data()
    print(f"Loaded {len(features)} cases, {len(citation_graph)} source cases, "
          f"{sum(len(v) for v in citation_graph.values())} citation edges")

    # Pre-compute pairwise scores (shared across experiments)
    if to_run & {1, 3, 4, 5, 6}:
        print("Pre-computing pairwise scores...")
        score_matrix = build_score_matrix(features)
        print(f"  {len(score_matrix)} pairs computed")
    else:
        score_matrix = None

    # Run experiments
    agg_exp1 = agg_exp3 = sweep_results = None

    if 1 in to_run:
        agg_exp1 = experiment_1(features, citation_graph, titles, score_matrix)
    if 2 in to_run:
        experiment_2()
    if 3 in to_run:
        agg_exp3 = experiment_3(features, citation_graph, titles, score_matrix)
    if 4 in to_run:
        experiment_4(features, titles, score_matrix)
    if 5 in to_run:
        experiment_5(features, titles, score_matrix)
    if 6 in to_run:
        sweep_results = experiment_6(features, citation_graph, titles, score_matrix)

    # Verify
    if args.verify or run_all:
        verify_against_csv(agg_exp1, agg_exp3, sweep_results)

    print("\nDone.")


if __name__ == '__main__':
    main()
