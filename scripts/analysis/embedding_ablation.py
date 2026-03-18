#!/usr/bin/env python3
"""
Embedding-Only Ablation Experiment

Isolates the embedding contribution from set-based features by running
retrieval under four conditions plus a full-formula reference:

1. Embedding-only, section-based (facts + discussion cosines)
2. Embedding-only, combined D-tuple (single combined_embedding cosine)
3. Embedding-only, per-component D-tuple (9 component cosines, weighted)
4. Set-features only (provisions, outcome, tags, principles)
5. Full multi-factor (reference, loaded from existing results)

All features are loaded into memory upfront (119 queries) to avoid
the ~55K per-pair DB calls that the service API would require.

See EMBEDDING_ABLATION_SPEC.md for design rationale.

Output:
- embedding_ablation_results.md (aggregate metrics + analysis)
- embedding_ablation_per_edge.csv (228 rows x 7 rank columns)
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


# ---------------------------------------------------------------------------
# Weight constants (from paper formula, normalized per condition)
# ---------------------------------------------------------------------------

# Condition 1: section embedding sub-weights normalized to 1.0
EMB_SECTION_W = {
    'facts': 0.15 / 0.40,       # 0.375
    'discussion': 0.25 / 0.40,  # 0.625
}

# Condition 4: set-feature sub-weights normalized to 1.0
SET_ONLY_W = {
    'provision_overlap': 0.25 / 0.60,     # 5/12
    'outcome_alignment': 0.15 / 0.60,     # 3/12
    'tag_overlap': 0.10 / 0.60,           # 2/12
    'principle_overlap': 0.10 / 0.60,     # 2/12
}


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------

def load_all_features(service):
    """Load features for all cases with complete embeddings into memory.

    Returns dict mapping case_id -> feature dict (embeddings as numpy arrays,
    set features as lists/strings).
    """
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


def get_citation_graph():
    """Load citation edges from the database."""
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


def load_reference_results(results_dir):
    """Load full-formula aggregate metrics and per-edge ranks."""
    # Aggregate
    ref_agg = {}
    agg_path = os.path.join(results_dir, 'retrieval_aggregate.csv')
    with open(agg_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            metric = row['metric']
            ref_agg[metric] = {
                'section': float(row['section']),
                'combined': float(row['combined']),
                'component': float(row['component']),
                'random': float(row['random']),
            }

    # Per-edge ranks
    ref_edges = {}
    edge_path = os.path.join(results_dir, 'retrieval_per_edge.csv')
    with open(edge_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (int(row['source_case_id']), int(row['cited_case_id']))
            ref_edges[key] = {
                'full_section_rank': int(row['section_rank']),
                'full_combined_rank': int(row['combined_rank']),
                'full_component_rank': int(row['component_rank']),
            }

    return ref_agg, ref_edges


# ---------------------------------------------------------------------------
# Pairwise scoring (all in-memory)
# ---------------------------------------------------------------------------

def cosine_sim(vec1, vec2):
    """Cosine similarity, matching similarity_service._cosine_similarity."""
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
    """Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def outcome_alignment(a, b):
    """Outcome alignment score, matching similarity_service."""
    if a is None or b is None:
        return 0.5
    if a == b:
        return 1.0
    if {a, b} == {'ethical', 'unethical'}:
        return 0.0
    return 0.5


def principle_overlap(tensions_a, tensions_b):
    """Principle overlap from Step 4 tension data."""
    if not tensions_a or not tensions_b:
        return 0.0

    def extract(tensions):
        principles = set()
        for t in tensions:
            if isinstance(t, dict):
                principles.add(t.get('principle1', ''))
                principles.add(t.get('principle2', ''))
        principles.discard('')
        return principles

    return jaccard(extract(tensions_a), extract(tensions_b))


def compute_pair_scores(src, tgt):
    """Compute all raw scores for a (source, target) pair.

    Returns dict with keys for each individual score component.
    """
    return {
        'facts_sim': cosine_sim(
            src.get('facts_embedding'), tgt.get('facts_embedding')
        ),
        'discussion_sim': cosine_sim(
            src.get('discussion_embedding'), tgt.get('discussion_embedding')
        ),
        'combined_sim': cosine_sim(
            src.get('combined_embedding'), tgt.get('combined_embedding')
        ),
        'component_sim': _weighted_component_sim(src, tgt),
        'provision_overlap': jaccard(
            set(src.get('provisions_cited', [])),
            set(tgt.get('provisions_cited', []))
        ),
        'outcome_alignment': outcome_alignment(
            src.get('outcome_type'), tgt.get('outcome_type')
        ),
        'tag_overlap': jaccard(
            set(src.get('subject_tags', [])),
            set(tgt.get('subject_tags', []))
        ),
        'principle_overlap': principle_overlap(
            src.get('principle_tensions', []),
            tgt.get('principle_tensions', [])
        ),
    }


def _weighted_component_sim(src, tgt):
    """Weighted average of 9 component cosines using COMPONENT_WEIGHTS.

    Matches similarity_service.calculate_similarity(use_component_embedding=True)
    logic at lines 142-161.
    """
    weighted_sum = 0.0
    total_weight = 0.0
    for code in ['R', 'P', 'O', 'S', 'Rs', 'A', 'E', 'Ca', 'Cs']:
        src_emb = src.get(f'embedding_{code}')
        tgt_emb = tgt.get(f'embedding_{code}')
        if src_emb is not None and tgt_emb is not None:
            sim = cosine_sim(src_emb, tgt_emb)
            w = COMPONENT_WEIGHTS.get(code, 0.0)
            weighted_sum += w * sim
            total_weight += w
    return weighted_sum / total_weight if total_weight > 0 else 0.0


def condition_scores(raw):
    """Apply 4 condition weight formulas to raw pair scores."""
    return {
        'emb_section': (
            EMB_SECTION_W['facts'] * raw['facts_sim'] +
            EMB_SECTION_W['discussion'] * raw['discussion_sim']
        ),
        'emb_combined': raw['combined_sim'],
        'emb_component': raw['component_sim'],
        'set_only': (
            SET_ONLY_W['provision_overlap'] * raw['provision_overlap'] +
            SET_ONLY_W['outcome_alignment'] * raw['outcome_alignment'] +
            SET_ONLY_W['tag_overlap'] * raw['tag_overlap'] +
            SET_ONLY_W['principle_overlap'] * raw['principle_overlap']
        ),
    }


# ---------------------------------------------------------------------------
# Ranking + metrics
# ---------------------------------------------------------------------------

CONDITIONS = ['emb_section', 'emb_combined', 'emb_component', 'set_only']


def rank_all_conditions(features, source_id, pool_ids):
    """Rank all candidates under all 4 conditions for one source case."""
    src = features[source_id]
    rankings = {c: [] for c in CONDITIONS}

    for target_id in pool_ids:
        if target_id == source_id:
            continue
        raw = compute_pair_scores(src, features[target_id])
        scores = condition_scores(raw)
        for cond, score in scores.items():
            rankings[cond].append((target_id, score))

    for cond in rankings:
        rankings[cond].sort(key=lambda x: -x[1])

    return rankings


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
    return None


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
        p_hit = prob_no_hit * c / (n - r + 1)
        total_mrr += (1.0 / r) * p_hit
        denom = n - (r - 1)
        numer = n - c - (r - 1)
        prob_no_hit *= numer / denom if denom > 0 and numer >= 0 else 0
    return total_mrr


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------

def run_ablation(features, verbose=False):
    """Run the 4-condition ablation experiment."""
    citation_graph = get_citation_graph()
    pool_ids = sorted(features.keys())
    pool_size = len(pool_ids) - 1

    print(f"Cases with all embeddings: {len(pool_ids)}")
    print(f"Candidates per query: {pool_size}")

    # Filter to source cases with resolvable citations
    sources = {}
    for source_id in sorted(citation_graph.keys()):
        if source_id not in features:
            continue
        resolvable = [c for c in citation_graph[source_id] if c in features]
        if resolvable:
            sources[source_id] = resolvable

    n_sources = len(sources)
    total_edges = sum(len(v) for v in sources.values())
    print(f"Source cases with resolvable citations: {n_sources}")
    print(f"Resolvable citation edges: {total_edges}")

    per_edge = []
    per_source = {}

    for i, (source_id, resolvable) in enumerate(sorted(sources.items()), 1):
        if verbose or i % 10 == 0 or i == 1:
            print(f"  [{i}/{n_sources}] Case {source_id}...")

        rankings = rank_all_conditions(features, source_id, pool_ids)

        src_data = {'resolvable': resolvable}
        for cond in CONDITIONS:
            src_data[f'{cond}_mrr'] = reciprocal_rank(rankings[cond], resolvable)
            for k in [5, 10, 20]:
                src_data[f'{cond}_r{k}'] = recall_at_k(rankings[cond], resolvable, k)
        per_source[source_id] = src_data

        title = get_case_title(source_id)
        for cid in resolvable:
            edge = {
                'source_case_id': source_id,
                'source_title': title,
                'cited_case_id': cid,
                'cited_title': get_case_title(cid),
                'pool_size': pool_size,
            }
            for cond in CONDITIONS:
                edge[f'{cond}_rank'] = find_rank(rankings[cond], cid)
            per_edge.append(edge)

    # Aggregate
    agg = {
        'n_sources': n_sources,
        'pool_size': len(pool_ids),
        'n_edges': len(per_edge),
    }
    for cond in CONDITIONS:
        for k in [5, 10, 20]:
            vals = [v[f'{cond}_r{k}'] for v in per_source.values()]
            agg[f'{cond}_r{k}'] = sum(vals) / n_sources
        mrr_vals = [v[f'{cond}_mrr'] for v in per_source.values()]
        agg[f'{cond}_mrr'] = sum(mrr_vals) / n_sources

    # Random baselines
    avg_cited = len(per_edge) / n_sources
    for k in [5, 10, 20]:
        agg[f'random_r{k}'] = random_baseline_recall(k, pool_size, avg_cited)
    agg['random_mrr'] = random_baseline_mrr(pool_size, avg_cited)

    return agg, per_source, per_edge


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_per_edge_csv(per_edge, ref_edges, output_dir):
    """Write per-edge ranks: 4 ablation conditions + 3 full-formula reference."""
    path = os.path.join(output_dir, 'embedding_ablation_per_edge.csv')
    fields = [
        'source_case_id', 'source_title', 'cited_case_id', 'cited_title',
        'emb_section_rank', 'emb_combined_rank', 'emb_component_rank',
        'set_only_rank',
        'full_section_rank', 'full_combined_rank', 'full_component_rank',
        'pool_size',
    ]

    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for edge in per_edge:
            key = (edge['source_case_id'], edge['cited_case_id'])
            ref = ref_edges.get(key, {})
            row = {
                'source_case_id': edge['source_case_id'],
                'source_title': edge['source_title'],
                'cited_case_id': edge['cited_case_id'],
                'cited_title': edge['cited_title'],
                'emb_section_rank': edge['emb_section_rank'],
                'emb_combined_rank': edge['emb_combined_rank'],
                'emb_component_rank': edge['emb_component_rank'],
                'set_only_rank': edge['set_only_rank'],
                'full_section_rank': ref.get('full_section_rank', ''),
                'full_combined_rank': ref.get('full_combined_rank', ''),
                'full_component_rank': ref.get('full_component_rank', ''),
                'pool_size': edge['pool_size'],
            }
            writer.writerow(row)

    print(f"Per-edge CSV: {path} ({len(per_edge)} rows)")


def write_markdown(agg, ref_agg, per_edge, output_dir):
    """Write results markdown with required analysis sections."""
    path = os.path.join(output_dir, 'embedding_ablation_results.md')
    lines = []

    lines.append("# Embedding-Only Ablation Results")
    lines.append("")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Script:** `scripts/analysis/embedding_ablation.py`")
    lines.append(f"**Spec:** `EMBEDDING_ABLATION_SPEC.md`")
    lines.append("")

    lines.append("## Design")
    lines.append("")
    lines.append(
        "Four conditions isolating embedding and set-feature contributions, "
        "plus the full multi-factor reference from Table 3. All conditions "
        f"use the same {agg['n_sources']} source cases, {agg['n_edges']} "
        f"citation edges, {agg['pool_size'] - 1} candidates per query."
    )
    lines.append("")
    lines.append("| Condition | Formula |")
    lines.append("|-----------|---------|")
    lines.append("| Emb-Section | 0.375 x facts_cosine + 0.625 x discussion_cosine |")
    lines.append("| Emb-Combined | cosine(combined_embedding_i, combined_embedding_j) |")
    lines.append("| Emb-PerComp | weighted avg of 9 component cosines (Table 2 weights, renormalized to 1.0) |")
    lines.append("| Set-Only | 0.417 x provisions + 0.250 x outcome + 0.167 x tags + 0.167 x principles |")
    lines.append("| Full (ref) | 0.40 x embedding + 0.60 x set-based (from Table 3) |")
    lines.append("")

    # --- Results table ---
    lines.append("## Results")
    lines.append("")
    lines.append(
        "| Metric | Emb-Section | Emb-Combined | Emb-PerComp | Set-Only "
        "| Full (S/C/P) | Random |"
    )
    lines.append(
        "|--------|:-----------:|:------------:|:-----------:|:--------:"
        "|:------------:|:------:|"
    )

    for label, key in [('MRR', 'mrr'), ('Recall@5', 'r5'),
                        ('Recall@10', 'r10'), ('Recall@20', 'r20')]:
        ref = ref_agg.get(label, {})
        ref_str = (
            f"{ref.get('section', 0):.3f}/"
            f"{ref.get('combined', 0):.3f}/"
            f"{ref.get('component', 0):.3f}"
        )
        lines.append(
            f"| {label} "
            f"| {agg[f'emb_section_{key}']:.3f} "
            f"| {agg[f'emb_combined_{key}']:.3f} "
            f"| {agg[f'emb_component_{key}']:.3f} "
            f"| {agg[f'set_only_{key}']:.3f} "
            f"| {ref_str} "
            f"| {agg[f'random_{key}']:.3f} |"
        )

    lines.append("")

    # --- Analysis ---
    lines.append("## Analysis")
    lines.append("")

    # Shorthand for frequently used values
    es_mrr = agg['emb_section_mrr']
    ec_mrr = agg['emb_combined_mrr']
    ep_mrr = agg['emb_component_mrr']
    so_mrr = agg['set_only_mrr']

    es_r10 = agg['emb_section_r10']
    ec_r10 = agg['emb_combined_r10']
    ep_r10 = agg['emb_component_r10']
    so_r10 = agg['set_only_r10']

    ref_s_r10 = ref_agg.get('Recall@10', {}).get('section', 0)
    ref_c_r10 = ref_agg.get('Recall@10', {}).get('combined', 0)
    ref_p_r10 = ref_agg.get('Recall@10', {}).get('component', 0)
    full_best_r10 = max(ref_s_r10, ref_c_r10, ref_p_r10)

    # 1. Embedding isolation
    lines.append("### 1. Embedding Isolation")
    lines.append("")
    lines.append(
        "D-tuple advantage with embeddings only (no set-feature floor):"
    )
    lines.append("")
    lines.append("| Comparison | Delta MRR | Delta Recall@10 |")
    lines.append("|------------|:---------:|:---------------:|")
    lines.append(
        f"| Combined vs Section | {ec_mrr - es_mrr:+.3f} "
        f"| {ec_r10 - es_r10:+.3f} |"
    )
    lines.append(
        f"| Per-comp vs Section | {ep_mrr - es_mrr:+.3f} "
        f"| {ep_r10 - es_r10:+.3f} |"
    )
    lines.append("")

    full_delta_r10 = ref_c_r10 - ref_s_r10
    emb_delta_r10 = ec_r10 - es_r10

    lines.append(
        f"Full-formula Combined-vs-Section Recall@10 delta: "
        f"{full_delta_r10:+.3f}"
    )
    lines.append(
        f"Embedding-only Combined-vs-Section Recall@10 delta: "
        f"{emb_delta_r10:+.3f}"
    )
    lines.append("")

    if abs(full_delta_r10) > 0 and abs(emb_delta_r10) > abs(full_delta_r10):
        lines.append(
            "The D-tuple advantage is **larger** in isolation than in the "
            "full formula, confirming that the 60% shared set-feature floor "
            "compresses the observable effect."
        )
    elif abs(full_delta_r10) > 0 and abs(emb_delta_r10) < abs(full_delta_r10) * 0.5:
        lines.append(
            "The D-tuple advantage is **smaller** in isolation, suggesting "
            "that D-tuple embeddings interact positively with the set features."
        )
    else:
        lines.append(
            "The D-tuple advantage is **comparable** in isolation to the "
            "full formula."
        )
    lines.append("")

    # 2. Set-feature contribution
    lines.append("### 2. Set-Feature Contribution")
    lines.append("")

    emb_best_r10 = max(es_r10, ec_r10, ep_r10)
    emb_best_label = (
        'Emb-PerComp' if ep_r10 >= ec_r10 and ep_r10 >= es_r10
        else 'Emb-Combined' if ec_r10 >= es_r10
        else 'Emb-Section'
    )

    lines.append(f"| Signal | Recall@10 |")
    lines.append(f"|--------|:---------:|")
    lines.append(f"| Set-Only | {so_r10:.3f} |")
    lines.append(f"| {emb_best_label} (best embedding-only) | {emb_best_r10:.3f} |")
    lines.append(f"| Full-formula best | {full_best_r10:.3f} |")
    lines.append("")

    if emb_best_r10 > full_best_r10:
        lines.append(
            f"Embedding-only ({emb_best_r10:.3f}) **exceeds** the full "
            f"formula ({full_best_r10:.3f}). The 0.60 set-feature weight "
            f"does not improve retrieval over D-tuple embeddings alone. "
            f"Set-Only ({so_r10:.3f}) is the weakest signal."
        )
    elif full_best_r10 > 0:
        pct_set = so_r10 / full_best_r10 * 100
        pct_emb = emb_best_r10 / full_best_r10 * 100
        lines.append(
            f"Set-Only achieves {pct_set:.0f}% of the full-formula best; "
            f"{emb_best_label} achieves {pct_emb:.0f}%. "
        )
        if pct_set > pct_emb:
            lines.append("Set features are the stronger standalone signal.")
        else:
            lines.append("Embeddings are the stronger standalone signal.")
    lines.append("")

    # 3. Complementarity
    lines.append("### 3. Complementarity")
    lines.append("")

    marginal_emb = full_best_r10 - so_r10
    marginal_set = full_best_r10 - emb_best_r10

    lines.append(
        f"Marginal embedding contribution (Full best - Set-Only): "
        f"{marginal_emb:+.3f} Recall@10"
    )
    lines.append(
        f"Marginal set-feature contribution (Full best - Emb-best): "
        f"{marginal_set:+.3f} Recall@10"
    )
    lines.append("")

    if marginal_set < 0:
        lines.append(
            f"Set features have **negative** marginal contribution: "
            f"adding set features to the best embedding reduces Recall@10 "
            f"by {abs(marginal_set):.3f}. The current 0.40/0.60 weighting "
            f"dilutes the embedding signal. The D-tuple extraction framework "
            f"produces embeddings strong enough to outperform the combined "
            f"formula."
        )
    elif marginal_set > marginal_emb:
        lines.append(
            f"Set features contribute more marginally "
            f"({marginal_set:.3f}) than embeddings ({marginal_emb:.3f})."
        )
    else:
        lines.append(
            f"Embeddings contribute more marginally "
            f"({marginal_emb:.3f}) than set features ({marginal_set:.3f})."
        )
    lines.append("")

    # 4. Per-edge wins/losses
    lines.append("### 4. Per-Edge Comparison (Embedding-Only)")
    lines.append("")

    comparisons = [
        ('emb_combined', 'emb_section', 'Emb-Combined vs Emb-Section'),
        ('emb_component', 'emb_section', 'Emb-PerComp vs Emb-Section'),
        ('emb_combined', 'emb_component', 'Emb-Combined vs Emb-PerComp'),
    ]
    for m1, m2, label in comparisons:
        m1_wins = sum(
            1 for e in per_edge
            if e[f'{m1}_rank'] and e[f'{m2}_rank']
            and e[f'{m1}_rank'] < e[f'{m2}_rank']
        )
        m2_wins = sum(
            1 for e in per_edge
            if e[f'{m1}_rank'] and e[f'{m2}_rank']
            and e[f'{m2}_rank'] < e[f'{m1}_rank']
        )
        ties = sum(
            1 for e in per_edge
            if e[f'{m1}_rank'] and e[f'{m2}_rank']
            and e[f'{m1}_rank'] == e[f'{m2}_rank']
        )
        lines.append(
            f"**{label}:** "
            f"{m1.split('_', 1)[1].title()} wins {m1_wins}, "
            f"{m2.split('_', 1)[1].title()} wins {m2_wins}, "
            f"tied {ties}"
        )
        lines.append("")

    with open(path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"Markdown: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Embedding-only ablation experiment'
    )
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--output-dir', default=None)
    parser.add_argument(
        '--reference-dir', default=None,
        help='Directory with existing full-formula results '
             '(default: experiments/iccbr-2026)'
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        service = PrecedentSimilarityService()

        print("Embedding-Only Ablation Experiment")
        print("=" * 60)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print()

        # Load all features into memory (119 queries, not ~55K)
        print("Loading case features...")
        features = load_all_features(service)
        print(f"Loaded {len(features)} cases")
        print()

        # Run 4-condition experiment
        agg, per_source, per_edge = run_ablation(
            features, verbose=args.verbose
        )

        # Load reference results
        base_dir = os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        )
        ref_dir = args.reference_dir or os.path.join(
            base_dir, 'experiments', 'iccbr-2026'
        )
        print(f"\nLoading reference results from {ref_dir}")
        ref_agg, ref_edges = load_reference_results(ref_dir)

        # Print summary
        print()
        print("=" * 60)
        print("RESULTS")
        print("=" * 60)
        header = (
            f"{'Metric':<12} {'Emb-Sec':>8} {'Emb-Comb':>9} "
            f"{'Emb-Comp':>9} {'Set-Only':>9} {'Random':>8}"
        )
        print(header)
        print(
            f"{'MRR':<12} {agg['emb_section_mrr']:>8.3f} "
            f"{agg['emb_combined_mrr']:>9.3f} "
            f"{agg['emb_component_mrr']:>9.3f} "
            f"{agg['set_only_mrr']:>9.3f} "
            f"{agg['random_mrr']:>8.3f}"
        )
        for k in [5, 10, 20]:
            print(
                f"{'Recall@' + str(k):<12} "
                f"{agg[f'emb_section_r{k}']:>8.3f} "
                f"{agg[f'emb_combined_r{k}']:>9.3f} "
                f"{agg[f'emb_component_r{k}']:>9.3f} "
                f"{agg[f'set_only_r{k}']:>9.3f} "
                f"{agg[f'random_r{k}']:>8.3f}"
            )

        # Write output
        out_dir = args.output_dir or os.path.join(base_dir, 'experiments', 'iccbr-2026')
        write_per_edge_csv(per_edge, ref_edges, out_dir)
        write_markdown(agg, ref_agg, per_edge, out_dir)

        print("\nDone.")


if __name__ == '__main__':
    main()
