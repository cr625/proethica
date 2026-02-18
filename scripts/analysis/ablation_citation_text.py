#!/usr/bin/env python3
"""
Ablation Study: Citation Text Contamination in Discussion Embeddings

Measures how much retrieval performance is inflated by the board's descriptions
of cited precedent cases appearing in the Discussion section text.

Approach:
1. Load discussion text for all cases
2. Strip sentences containing "Case XX-Y" citation patterns
3. Re-embed the stripped text using the same model (all-MiniLM-L6-v2)
4. Re-run ground truth retrieval experiment using stripped embeddings
5. Compare Recall@K and MRR: original vs stripped

All computation is in-memory -- no database embeddings are modified.

Usage:
    python scripts/analysis/ablation_citation_text.py
    python scripts/analysis/ablation_citation_text.py --verbose
    python scripts/analysis/ablation_citation_text.py --output ablation_results.csv
"""

import argparse
import csv
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, '/home/chris/onto')

from app import create_app
from app.models import Document, db
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Citation stripping
# ---------------------------------------------------------------------------

# Matches sentences that reference BER case numbers like "Case 21-7", "BER Case 76-4"
CITATION_PATTERN = re.compile(
    r'[^.!?]*(?:BER\s+)?Case\s+\d{1,4}-\d+[^.!?]*[.!?]',
    re.IGNORECASE
)

# HTML tag removal
HTML_TAG_RE = re.compile(r'<[^>]+>')


def strip_html(text_content):
    """Remove HTML tags from text."""
    return HTML_TAG_RE.sub(' ', text_content)


def strip_citation_sentences(text_content):
    """
    Remove sentences containing BER case citation patterns.

    Returns (stripped_text, original_sentence_count, removed_sentence_count)
    """
    clean = strip_html(text_content)

    # Split into sentences (simple approach)
    sentences = re.split(r'(?<=[.!?])\s+', clean)
    original_count = len(sentences)

    kept = []
    removed_count = 0
    for sentence in sentences:
        if re.search(r'(?:BER\s+)?Case\s+\d{1,4}-\d+', sentence, re.IGNORECASE):
            removed_count += 1
        else:
            kept.append(sentence)

    stripped = ' '.join(kept)
    return stripped, original_count, removed_count


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

_model = None

def get_embedding_model():
    """Load SentenceTransformer model (cached)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def embed_text(text_content):
    """Generate 384-dim embedding for text."""
    model = get_embedding_model()
    if not text_content or not text_content.strip():
        return None
    embedding = model.encode(text_content, normalize_embeddings=True)
    return embedding


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_discussion_texts():
    """Load discussion section text for all cases. Returns {case_id: text}."""
    rows = db.session.execute(text("""
        SELECT ds.document_id, ds.content
        FROM document_sections ds
        WHERE ds.section_type = 'discussion'
        ORDER BY ds.document_id
    """)).fetchall()
    return {r[0]: r[1] for r in rows}


def load_facts_embeddings():
    """Load facts embeddings from DB. Returns {case_id: np.array}."""
    rows = db.session.execute(text("""
        SELECT case_id, facts_embedding::text
        FROM case_precedent_features
        WHERE facts_embedding IS NOT NULL
    """)).fetchall()

    result = {}
    for case_id, emb_text in rows:
        # Parse PostgreSQL vector format: [0.1,0.2,...]
        values = emb_text.strip('[]').split(',')
        result[case_id] = np.array([float(v) for v in values], dtype=np.float32)
    return result


def load_original_discussion_embeddings():
    """Load original discussion embeddings from DB. Returns {case_id: np.array}."""
    rows = db.session.execute(text("""
        SELECT case_id, discussion_embedding::text
        FROM case_precedent_features
        WHERE discussion_embedding IS NOT NULL
    """)).fetchall()

    result = {}
    for case_id, emb_text in rows:
        values = emb_text.strip('[]').split(',')
        result[case_id] = np.array([float(v) for v in values], dtype=np.float32)
    return result


def get_citation_graph():
    """Return {source_case_id: [cited_case_id, ...]}."""
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
# Similarity (in-memory, replicating similarity_service weights)
# ---------------------------------------------------------------------------

# Section-based weights from PrecedentSimilarityService.DEFAULT_WEIGHTS
# Only using embedding components for this ablation; non-embedding factors
# (provisions, outcome, tags, principles) are identical between conditions,
# so we isolate the embedding contribution.
EMBEDDING_ONLY_WEIGHTS = {
    'facts_similarity': 0.15,
    'discussion_similarity': 0.25,
}

FULL_WEIGHTS = {
    'facts_similarity': 0.15,
    'discussion_similarity': 0.25,
    'provision_overlap': 0.25,
    'outcome_alignment': 0.15,
    'tag_overlap': 0.10,
    'principle_overlap': 0.10,
}


def cosine_similarity(a, b):
    """Cosine similarity between two vectors."""
    if a is None or b is None:
        return 0.0
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def compute_ranking(source_id, facts_embeddings, discussion_embeddings,
                    candidate_pool):
    """
    Compute ranking of candidates by facts+discussion similarity.
    Uses the same weight ratio as the full service (0.15:0.25 = 37.5%:62.5%).

    Returns: [(case_id, score), ...] sorted by score descending.
    """
    src_facts = facts_embeddings.get(source_id)
    src_disc = discussion_embeddings.get(source_id)

    scores = []
    for cid in candidate_pool:
        if cid == source_id:
            continue
        tgt_facts = facts_embeddings.get(cid)
        tgt_disc = discussion_embeddings.get(cid)

        facts_sim = cosine_similarity(src_facts, tgt_facts)
        disc_sim = cosine_similarity(src_disc, tgt_disc)

        # Weight ratio: facts 0.15, discussion 0.25 (total 0.40)
        # Normalize to sum to 1.0 for the embedding-only comparison
        score = (0.375 * facts_sim) + (0.625 * disc_sim)
        scores.append((cid, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


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


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------

def run_ablation(verbose=False, output_csv=None):
    # Load data
    print("Loading data...")
    discussion_texts = load_discussion_texts()
    facts_embeddings = load_facts_embeddings()
    original_disc_embeddings = load_original_discussion_embeddings()
    citation_graph = get_citation_graph()

    # Determine candidate pool: cases with both facts and discussion embeddings
    pool = set(facts_embeddings.keys()) & set(original_disc_embeddings.keys())
    print(f"Cases with section embeddings: {len(pool)}")
    print(f"Cases with citations: {len(citation_graph)}")
    print(f"Cases with discussion text: {len(discussion_texts)}")

    # Strip citation text and re-embed
    print("\nStripping citation sentences and re-embedding...")
    stripped_disc_embeddings = {}
    strip_stats = []

    for case_id in sorted(pool):
        disc_text = discussion_texts.get(case_id, '')
        if not disc_text:
            # No discussion text available; use original embedding
            stripped_disc_embeddings[case_id] = original_disc_embeddings.get(case_id)
            strip_stats.append((case_id, 0, 0, 0))
            continue

        stripped, orig_count, removed_count = strip_citation_sentences(disc_text)
        stripped_disc_embeddings[case_id] = embed_text(stripped)
        strip_stats.append((case_id, orig_count, removed_count,
                           removed_count / orig_count if orig_count > 0 else 0))

    # Summary of stripping
    total_removed = sum(s[2] for s in strip_stats)
    total_sentences = sum(s[1] for s in strip_stats)
    cases_affected = sum(1 for s in strip_stats if s[2] > 0)
    print(f"  Total sentences: {total_sentences}")
    print(f"  Sentences removed: {total_removed} ({total_removed/total_sentences*100:.1f}%)")
    print(f"  Cases affected: {cases_affected} / {len(pool)}")

    if verbose:
        # Show top-10 most affected cases
        by_removed = sorted(strip_stats, key=lambda s: s[2], reverse=True)[:10]
        print(f"\n  Most affected cases:")
        for case_id, orig, removed, pct in by_removed:
            if removed > 0:
                title = get_case_title(case_id)[:40]
                print(f"    Case {case_id} ({title}): {removed}/{orig} sentences removed ({pct:.0%})")

    # Run evaluation for both conditions
    print("\n" + "=" * 70)
    print("GROUND TRUTH RETRIEVAL: Original vs Stripped Discussion Embeddings")
    print("=" * 70)

    conditions = {
        'original': original_disc_embeddings,
        'stripped': stripped_disc_embeddings,
    }

    results = {}
    csv_rows = []

    for condition_name, disc_embeddings in conditions.items():
        print(f"\n--- Condition: {condition_name} ---")

        recalls = {5: [], 10: [], 20: []}
        mrr_list = []
        per_case = []

        for source_id in sorted(citation_graph.keys()):
            if source_id not in pool:
                continue
            cited_ids = citation_graph[source_id]
            resolvable = [c for c in cited_ids if c in pool]
            if not resolvable:
                continue

            ranking = compute_ranking(source_id, facts_embeddings,
                                      disc_embeddings, pool)

            for k in [5, 10, 20]:
                recalls[k].append(recall_at_k(ranking, resolvable, k))
            mrr_list.append(reciprocal_rank(ranking, resolvable))

            # Track per-case for CSV
            for cid in resolvable:
                rank_map = {rid: i+1 for i, (rid, _) in enumerate(ranking)}
                csv_rows.append({
                    'condition': condition_name,
                    'source_case_id': source_id,
                    'source_title': get_case_title(source_id),
                    'cited_case_id': cid,
                    'cited_title': get_case_title(cid),
                    'rank': rank_map.get(cid),
                    'resolvable_count': len(resolvable),
                })

            per_case.append({
                'source_id': source_id,
                'resolvable': len(resolvable),
                'recall_5': recalls[5][-1],
                'recall_10': recalls[10][-1],
                'mrr': mrr_list[-1],
            })

        n = len(mrr_list)
        r = {k: sum(v)/n for k, v in recalls.items()}
        mrr = sum(mrr_list) / n

        print(f"  Source cases evaluated: {n}")
        for k in [5, 10, 20]:
            print(f"  Recall@{k:2d}: {r[k]:.3f}")
        print(f"  MRR:       {mrr:.3f}")

        results[condition_name] = {
            'n': n,
            'recalls': r,
            'mrr': mrr,
            'per_case': per_case,
        }

    # Comparison
    print("\n" + "=" * 70)
    print("COMPARISON: Impact of Citation Text Removal")
    print("=" * 70)

    orig = results['original']
    stripped = results['stripped']

    print(f"\n{'Metric':<15} {'Original':>10} {'Stripped':>10} {'Delta':>10} {'% Change':>10}")
    print("-" * 55)
    for k in [5, 10, 20]:
        o = orig['recalls'][k]
        s = stripped['recalls'][k]
        delta = s - o
        pct = (delta / o * 100) if o != 0 else 0
        print(f"Recall@{k:<8d} {o:>10.3f} {s:>10.3f} {delta:>+10.3f} {pct:>+9.1f}%")

    o_mrr = orig['mrr']
    s_mrr = stripped['mrr']
    delta_mrr = s_mrr - o_mrr
    pct_mrr = (delta_mrr / o_mrr * 100) if o_mrr != 0 else 0
    print(f"{'MRR':<15} {o_mrr:>10.3f} {s_mrr:>10.3f} {delta_mrr:>+10.3f} {pct_mrr:>+9.1f}%")

    # Per-case changes for verbose
    if verbose:
        print("\nPer-case Recall@10 changes (largest drops):")
        paired = []
        for o_case in orig['per_case']:
            s_case = next((s for s in stripped['per_case']
                          if s['source_id'] == o_case['source_id']), None)
            if s_case:
                drop = s_case['recall_10'] - o_case['recall_10']
                paired.append((o_case['source_id'], o_case['recall_10'],
                              s_case['recall_10'], drop))
        paired.sort(key=lambda x: x[3])
        for case_id, o_r, s_r, drop in paired[:10]:
            title = get_case_title(case_id)[:35]
            print(f"  Case {case_id:3d} ({title}): {o_r:.2f} -> {s_r:.2f} ({drop:+.2f})")

    # Output CSV
    if output_csv:
        with open(output_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'condition', 'source_case_id', 'source_title',
                'cited_case_id', 'cited_title', 'rank', 'resolvable_count'
            ])
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"\nCSV saved to: {output_csv}")

    return results, strip_stats


def main():
    parser = argparse.ArgumentParser(
        description='Ablation: citation text contamination in discussion embeddings'
    )
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--output', type=str, help='Output CSV path')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        run_ablation(verbose=args.verbose, output_csv=args.output)


if __name__ == '__main__':
    main()
