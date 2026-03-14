#!/usr/bin/env python3
"""
Weight Sweep: Retrieval as a function of embedding/set-feature ratio.

For each method (section, combined, per-component), varies alpha from
0.0 to 1.0 and computes:
    score = alpha * embedding_score + (1 - alpha) * set_score

All per-pair raw scores are computed once from in-memory features.
The sweep is pure arithmetic over cached scores.

See WEIGHT_SWEEP_SPEC.md for design rationale.
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


# Normalized set-feature sub-weights (paper proportions, sum to 1.0)
SET_W = {
    'provision_overlap': 0.25 / 0.60,
    'outcome_alignment': 0.15 / 0.60,
    'tag_overlap': 0.10 / 0.60,
    'principle_overlap': 0.10 / 0.60,
}

# Section embedding sub-weights (paper proportions, sum to 1.0)
SECTION_W = {
    'facts': 0.15 / 0.40,
    'discussion': 0.25 / 0.40,
}


def load_all_features(service):
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
    rows = db.session.execute(text("""
        SELECT case_id, cited_case_ids
        FROM case_precedent_features
        WHERE cited_case_ids IS NOT NULL
          AND array_length(cited_case_ids, 1) > 0
    """)).fetchall()
    return {r[0]: list(r[1]) for r in rows}


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


def outcome_alignment(a, b):
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
    """Compute all raw scores for one pair. Returns dict with 5 scores."""
    # Three embedding scores
    facts_sim = cosine_sim(
        src.get('facts_embedding'), tgt.get('facts_embedding')
    )
    disc_sim = cosine_sim(
        src.get('discussion_embedding'), tgt.get('discussion_embedding')
    )
    section_emb = SECTION_W['facts'] * facts_sim + SECTION_W['discussion'] * disc_sim

    combined_emb = cosine_sim(
        src.get('combined_embedding'), tgt.get('combined_embedding')
    )

    weighted_sum = 0.0
    total_w = 0.0
    for code in ['R', 'P', 'O', 'S', 'Rs', 'A', 'E', 'Ca', 'Cs']:
        se = src.get(f'embedding_{code}')
        te = tgt.get(f'embedding_{code}')
        if se is not None and te is not None:
            s = cosine_sim(se, te)
            w = COMPONENT_WEIGHTS.get(code, 0.0)
            weighted_sum += w * s
            total_w += w
    component_emb = weighted_sum / total_w if total_w > 0 else 0.0

    # Set-feature score (shared across methods)
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
    set_score = (
        SET_W['provision_overlap'] * prov +
        SET_W['outcome_alignment'] * out +
        SET_W['tag_overlap'] * tags +
        SET_W['principle_overlap'] * princ
    )

    return {
        'section_emb': section_emb,
        'combined_emb': combined_emb,
        'component_emb': component_emb,
        'set_score': set_score,
    }


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


METHODS = ['section', 'combined', 'component']
EMB_KEYS = {
    'section': 'section_emb',
    'combined': 'combined_emb',
    'component': 'component_emb',
}


def run_sweep(features, alphas, verbose=False):
    """Run the weight sweep across all alpha values."""
    citation_graph = get_citation_graph()
    pool_ids = sorted(features.keys())

    # Filter to sources with resolvable citations
    sources = {}
    for sid in sorted(citation_graph.keys()):
        if sid not in features:
            continue
        resolvable = [c for c in citation_graph[sid] if c in features]
        if resolvable:
            sources[sid] = resolvable

    n_sources = len(sources)
    print(f"Cases: {len(pool_ids)}, Sources: {n_sources}, "
          f"Edges: {sum(len(v) for v in sources.values())}")

    # Precompute all pairwise raw scores for source cases
    print("Precomputing pairwise scores...")
    pair_scores = {}
    for i, (sid, _) in enumerate(sorted(sources.items()), 1):
        if verbose or i % 20 == 0 or i == 1:
            print(f"  [{i}/{n_sources}] Case {sid}...")
        src = features[sid]
        for tid in pool_ids:
            if tid == sid:
                continue
            pair_scores[(sid, tid)] = compute_raw_scores(src, features[tid])

    print(f"Precomputed {len(pair_scores)} pair scores")
    print(f"Sweeping {len(alphas)} alpha values...")

    # Sweep
    results = []
    for alpha in alphas:
        for method in METHODS:
            emb_key = EMB_KEYS[method]
            per_source_metrics = {}

            for sid, resolvable in sources.items():
                # Build ranking for this source at this alpha
                ranking = []
                for tid in pool_ids:
                    if tid == sid:
                        continue
                    ps = pair_scores[(sid, tid)]
                    score = alpha * ps[emb_key] + (1 - alpha) * ps['set_score']
                    ranking.append((tid, score))
                ranking.sort(key=lambda x: -x[1])

                per_source_metrics[sid] = {
                    'mrr': reciprocal_rank(ranking, resolvable),
                    'r5': recall_at_k(ranking, resolvable, 5),
                    'r10': recall_at_k(ranking, resolvable, 10),
                    'r20': recall_at_k(ranking, resolvable, 20),
                }

            # Aggregate
            n = len(per_source_metrics)
            agg = {
                'alpha': alpha,
                'method': method,
                'mrr': sum(v['mrr'] for v in per_source_metrics.values()) / n,
                'r5': sum(v['r5'] for v in per_source_metrics.values()) / n,
                'r10': sum(v['r10'] for v in per_source_metrics.values()) / n,
                'r20': sum(v['r20'] for v in per_source_metrics.values()) / n,
            }
            results.append(agg)

        if verbose:
            r10s = {r['method']: r['r10'] for r in results[-3:]}
            print(f"  alpha={alpha:.2f}: "
                  f"S={r10s['section']:.3f} "
                  f"C={r10s['combined']:.3f} "
                  f"P={r10s['component']:.3f}")

    return results


def write_csv(results, output_dir):
    path = os.path.join(output_dir, 'weight_sweep_data.csv')
    fields = ['alpha', 'method', 'MRR', 'Recall@5', 'Recall@10', 'Recall@20']
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            writer.writerow({
                'alpha': f"{r['alpha']:.2f}",
                'method': r['method'],
                'MRR': f"{r['mrr']:.3f}",
                'Recall@5': f"{r['r5']:.3f}",
                'Recall@10': f"{r['r10']:.3f}",
                'Recall@20': f"{r['r20']:.3f}",
            })
    print(f"CSV: {path} ({len(results)} rows)")


def write_markdown(results, output_dir):
    path = os.path.join(output_dir, 'weight_sweep_results.md')
    lines = []

    lines.append("# Weight Sweep Results")
    lines.append("")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Script:** `scripts/analysis/weight_sweep.py`")
    lines.append("")
    lines.append(
        "Retrieval metrics as a function of embedding weight (alpha). "
        "At each alpha: score = alpha * embedding + (1 - alpha) * set_features."
    )
    lines.append("")

    # Build lookup
    by_alpha_method = {}
    for r in results:
        by_alpha_method[(r['alpha'], r['method'])] = r

    alphas = sorted(set(r['alpha'] for r in results))

    # R@10 table
    lines.append("## Recall@10 by Alpha")
    lines.append("")
    lines.append("| Alpha | Section | Combined | Per-comp |")
    lines.append("|------:|:-------:|:--------:|:--------:|")
    for alpha in alphas:
        s = by_alpha_method.get((alpha, 'section'), {})
        c = by_alpha_method.get((alpha, 'combined'), {})
        p = by_alpha_method.get((alpha, 'component'), {})
        lines.append(
            f"| {alpha:.2f} "
            f"| {s.get('r10', 0):.3f} "
            f"| {c.get('r10', 0):.3f} "
            f"| {p.get('r10', 0):.3f} |"
        )
    lines.append("")

    # Find optima
    lines.append("## Optimal Alpha per Method (Recall@10)")
    lines.append("")
    lines.append("| Method | Optimal Alpha | R@10 at Optimum | R@10 at 0.40 |")
    lines.append("|--------|:------------:|:---------------:|:------------:|")

    for method in METHODS:
        method_results = [r for r in results if r['method'] == method]
        best = max(method_results, key=lambda r: r['r10'])
        at_040 = next(
            (r for r in method_results if abs(r['alpha'] - 0.40) < 0.001),
            None
        )
        r10_040 = at_040['r10'] if at_040 else 0.0
        label = {'section': 'Section', 'combined': 'Combined',
                 'component': 'Per-comp'}[method]
        lines.append(
            f"| {label} | {best['alpha']:.2f} "
            f"| {best['r10']:.3f} | {r10_040:.3f} |"
        )
    lines.append("")

    # Crossover analysis
    lines.append("## Crossover Analysis")
    lines.append("")

    # Find alpha where per-component overtakes combined
    crossover = None
    for alpha in alphas:
        c = by_alpha_method.get((alpha, 'combined'), {}).get('r10', 0)
        p = by_alpha_method.get((alpha, 'component'), {}).get('r10', 0)
        if p > c:
            crossover = alpha
            break

    if crossover is not None:
        c_val = by_alpha_method[(crossover, 'combined')]['r10']
        p_val = by_alpha_method[(crossover, 'component')]['r10']
        lines.append(
            f"Per-component overtakes Combined at alpha = {crossover:.2f} "
            f"(Per-comp {p_val:.3f} vs Combined {c_val:.3f})."
        )
    else:
        lines.append(
            "Combined leads Per-component at all alpha values."
        )
    lines.append("")

    # Set-feature interaction
    lines.append("## Set-Feature Interaction")
    lines.append("")
    lines.append("| Method | Emb-only R@10 | R@10 at alpha=0.40 | Delta |")
    lines.append("|--------|:------------:|:------------------:|:-----:|")
    for method in METHODS:
        emb_only = by_alpha_method.get((1.0, method), {}).get('r10', 0)
        at_040 = by_alpha_method.get((0.40, method), {}).get('r10', 0)
        delta = at_040 - emb_only
        label = {'section': 'Section', 'combined': 'Combined',
                 'component': 'Per-comp'}[method]
        lines.append(
            f"| {label} | {emb_only:.3f} | {at_040:.3f} "
            f"| {delta:+.3f} |"
        )
    lines.append("")

    # Validation
    lines.append("## Validation")
    lines.append("")
    set_only = by_alpha_method.get((0.0, 'section'), {}).get('r10', 0)
    set_c = by_alpha_method.get((0.0, 'combined'), {}).get('r10', 0)
    set_p = by_alpha_method.get((0.0, 'component'), {}).get('r10', 0)
    lines.append(
        f"At alpha=0.00 (set-only), all methods should be identical: "
        f"Section={set_only:.3f}, Combined={set_c:.3f}, "
        f"Per-comp={set_p:.3f}."
    )

    s_040 = by_alpha_method.get((0.40, 'section'), {}).get('r10', 0)
    c_040 = by_alpha_method.get((0.40, 'combined'), {}).get('r10', 0)
    p_040 = by_alpha_method.get((0.40, 'component'), {}).get('r10', 0)
    lines.append(
        f"At alpha=0.40 (paper config), Table 3 check: "
        f"Section={s_040:.3f} (expect 0.420), "
        f"Combined={c_040:.3f} (expect 0.463), "
        f"Per-comp={p_040:.3f} (expect 0.442)."
    )

    s_100 = by_alpha_method.get((1.0, 'section'), {}).get('r10', 0)
    c_100 = by_alpha_method.get((1.0, 'combined'), {}).get('r10', 0)
    p_100 = by_alpha_method.get((1.0, 'component'), {}).get('r10', 0)
    lines.append(
        f"At alpha=1.00 (emb-only), ablation check: "
        f"Section={s_100:.3f} (expect 0.387), "
        f"Combined={c_100:.3f} (expect 0.523), "
        f"Per-comp={p_100:.3f} (expect 0.568)."
    )
    lines.append("")

    with open(path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"Markdown: {path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Weight sweep experiment')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--output-dir', default=None)
    parser.add_argument(
        '--step', type=float, default=0.05,
        help='Alpha step size (default: 0.05, gives 21 points)'
    )
    args = parser.parse_args()

    alphas = [round(x * args.step, 4)
              for x in range(int(1.0 / args.step) + 1)]

    app = create_app()
    with app.app_context():
        service = PrecedentSimilarityService()

        print("Weight Sweep Experiment")
        print("=" * 60)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"Alpha range: {alphas[0]:.2f} to {alphas[-1]:.2f} "
              f"(step {args.step}, {len(alphas)} points)")
        print()

        print("Loading case features...")
        features = load_all_features(service)
        print(f"Loaded {len(features)} cases")
        print()

        results = run_sweep(features, alphas, verbose=args.verbose)

        base_dir = os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        )
        out_dir = args.output_dir or os.path.join(
            base_dir, 'docs-internal', 'iccbr-experiments'
        )

        write_csv(results, out_dir)
        write_markdown(results, out_dir)

        # Print summary
        print()
        print("=" * 60)
        by_am = {(r['alpha'], r['method']): r for r in results}
        print(f"{'Alpha':>6}  {'Section':>8}  {'Combined':>9}  {'Per-comp':>9}")
        for alpha in alphas:
            s = by_am.get((alpha, 'section'), {}).get('r10', 0)
            c = by_am.get((alpha, 'combined'), {}).get('r10', 0)
            p = by_am.get((alpha, 'component'), {}).get('r10', 0)
            marker = " <-- paper" if abs(alpha - 0.40) < 0.001 else ""
            print(f"  {alpha:.2f}  {s:>8.3f}  {c:>9.3f}  {p:>9.3f}{marker}")

        print("\nDone.")


if __name__ == '__main__':
    main()
