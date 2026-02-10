#!/usr/bin/env python3
"""
Per-component similarity analysis for ICCBR paper Section 5.5.

For each target case (default: divergent cases 14, 18, 58), generates
individual embeddings for each of the 9 D-tuple components, then computes
pairwise cosine similarity against all other cases at the component level.

Output:
- Per-component similarity matrix (9 separate scores per case pair)
- Identification of which components drive ranking disagreements
- CSV and console output for paper drafting

Usage:
    python scripts/analysis/per_component_similarity.py
    python scripts/analysis/per_component_similarity.py --cases 14,18,58
    python scripts/analysis/per_component_similarity.py --all --output results.csv
"""

import argparse
import csv
import sys
import os
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, '/home/chris/onto')

from app import create_app
from app.models import Document, db
from app.services.precedent.case_feature_extractor import (
    EXTRACTION_TYPE_TO_COMPONENT,
    ENTITY_TYPE_TO_COMPONENT,
    COMPONENT_WEIGHTS,
)
from sqlalchemy import text

# Component display order matching D-tuple: D=(R,P,O,S,Rs,A,E,Ca,Cs)
COMPONENT_ORDER = ['R', 'P', 'O', 'S', 'Rs', 'A', 'E', 'Ca', 'Cs']

COMPONENT_LABELS = {
    'R': 'Roles', 'P': 'Principles', 'O': 'Obligations',
    'S': 'States', 'Rs': 'Resources', 'A': 'Actions',
    'E': 'Events', 'Ca': 'Capabilities', 'Cs': 'Constraints',
}


def get_cases_with_component_embeddings() -> List[int]:
    """Get case IDs that have component-aggregated embeddings."""
    result = db.session.execute(text("""
        SELECT case_id FROM case_precedent_features
        WHERE combined_embedding IS NOT NULL
        AND extraction_method = 'component_aggregation'
        ORDER BY case_id
    """)).fetchall()
    return [r[0] for r in result]


def get_case_number(case_id: int) -> str:
    """Get the NSPE case number from the document title."""
    doc = Document.query.get(case_id)
    if doc and doc.title:
        return doc.title
    return f"Case {case_id}"


def get_local_model():
    """Get the SentenceTransformer model instance."""
    from app.services.embedding_service import EmbeddingService
    svc = EmbeddingService()
    if 'local' not in svc.providers or not svc.providers['local'].get('available'):
        raise RuntimeError("Local embedding provider not available")
    return svc.providers['local']['model']


def generate_component_embeddings(case_id: int, model) -> Dict[str, np.ndarray]:
    """
    Generate individual L2-normalized embeddings for each component of a case.

    Returns dict mapping component code -> 384-dim normalized embedding.
    Components with no entities are omitted.
    """
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    entities = TemporaryRDFStorage.query.filter_by(case_id=case_id).all()
    if not entities:
        return {}

    # Group entity texts by component
    components_by_type: Dict[str, List[str]] = defaultdict(list)
    for entity in entities:
        comp_code = None
        if entity.extraction_type in EXTRACTION_TYPE_TO_COMPONENT:
            comp_code = EXTRACTION_TYPE_TO_COMPONENT[entity.extraction_type]
        elif entity.extraction_type == 'temporal_dynamics_enhanced':
            if entity.entity_type:
                comp_code = ENTITY_TYPE_TO_COMPONENT.get(entity.entity_type.lower())
        if comp_code:
            text_val = entity.entity_label or ''
            if entity.entity_definition:
                text_val = f"{text_val}: {entity.entity_definition}"
            if text_val.strip():
                components_by_type[comp_code].append(text_val)

    # Generate per-component embeddings
    component_embeddings: Dict[str, np.ndarray] = {}
    for comp_code, texts in components_by_type.items():
        combined = ' '.join(texts)[:2000]
        emb = model.encode(combined)
        if not isinstance(emb, np.ndarray):
            emb = np.array(emb)
        # L2 normalize
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        component_embeddings[comp_code] = emb

    return component_embeddings


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two L2-normalized vectors."""
    return float(np.dot(a, b))


def compute_per_component_similarity(
    source_embs: Dict[str, np.ndarray],
    target_embs: Dict[str, np.ndarray],
) -> Dict[str, Optional[float]]:
    """
    Compute per-component cosine similarity between two cases.

    Returns dict mapping component code -> similarity score (or None if
    either case is missing that component).
    """
    result = {}
    for comp in COMPONENT_ORDER:
        if comp in source_embs and comp in target_embs:
            result[comp] = cosine_similarity(source_embs[comp], target_embs[comp])
        else:
            result[comp] = None
    return result


def compute_weighted_similarity(
    per_comp: Dict[str, Optional[float]],
    weights: Dict[str, float] = COMPONENT_WEIGHTS,
) -> float:
    """Compute weighted aggregate similarity from per-component scores."""
    total = 0.0
    total_weight = 0.0
    for comp, score in per_comp.items():
        if score is not None:
            w = weights.get(comp, 0.0)
            total += w * score
            total_weight += w
    return total / total_weight if total_weight > 0 else 0.0


def analyze_divergent_case(
    source_id: int,
    all_embeddings: Dict[int, Dict[str, np.ndarray]],
    section_rankings: Optional[Dict[int, List[int]]] = None,
    top_k: int = 10,
) -> dict:
    """
    Full per-component analysis for one source case.

    Returns structured data including:
    - Per-component similarity to every other case
    - Component-weighted ranking
    - Component-level breakdown for top neighbors
    """
    source_embs = all_embeddings[source_id]
    similarities = []

    for target_id, target_embs in all_embeddings.items():
        if target_id == source_id:
            continue
        per_comp = compute_per_component_similarity(source_embs, target_embs)
        weighted = compute_weighted_similarity(per_comp)
        similarities.append({
            'target_id': target_id,
            'target_title': get_case_number(target_id),
            'per_component': per_comp,
            'weighted_similarity': weighted,
        })

    # Sort by weighted similarity descending
    similarities.sort(key=lambda x: x['weighted_similarity'], reverse=True)

    # Entity counts per component for the source case
    entity_counts = {comp: 0 for comp in COMPONENT_ORDER}
    from app.models.temporary_rdf_storage import TemporaryRDFStorage
    entities = TemporaryRDFStorage.query.filter_by(case_id=source_id).all()
    for entity in entities:
        comp_code = None
        if entity.extraction_type in EXTRACTION_TYPE_TO_COMPONENT:
            comp_code = EXTRACTION_TYPE_TO_COMPONENT[entity.extraction_type]
        elif entity.extraction_type == 'temporal_dynamics_enhanced':
            if entity.entity_type:
                comp_code = ENTITY_TYPE_TO_COMPONENT.get(entity.entity_type.lower())
        if comp_code:
            entity_counts[comp_code] += 1

    return {
        'source_id': source_id,
        'source_title': get_case_number(source_id),
        'components_present': [c for c in COMPONENT_ORDER if c in source_embs],
        'entity_counts': entity_counts,
        'similarities': similarities,
    }


def print_case_analysis(analysis: dict, top_k: int = 10):
    """Console output for one case's per-component analysis."""
    print(f"\n{'='*90}")
    print(f"Case {analysis['source_id']}: {analysis['source_title']}")
    print(f"{'='*90}")

    # Component presence and entity counts
    print(f"\nComponents present: {len(analysis['components_present'])}/9")
    print(f"  {'Component':<14} {'Entities':>8}  {'Weight':>6}")
    print(f"  {'-'*30}")
    for comp in COMPONENT_ORDER:
        count = analysis['entity_counts'].get(comp, 0)
        weight = COMPONENT_WEIGHTS.get(comp, 0)
        present = comp in analysis['components_present']
        marker = '' if present else ' (missing)'
        print(f"  {COMPONENT_LABELS[comp]:<14} {count:>8}  {weight:>6.2f}{marker}")

    # Top neighbors with per-component breakdown
    print(f"\nTop {top_k} neighbors (component-weighted):")
    header = f"  {'Rank':<5} {'Case':<6} {'Weighted':>8}"
    for comp in COMPONENT_ORDER:
        header += f" {comp:>5}"
    print(header)
    print(f"  {'-'*len(header)}")

    for i, sim in enumerate(analysis['similarities'][:top_k], 1):
        line = f"  {i:<5} {sim['target_id']:<6} {sim['weighted_similarity']:>8.3f}"
        for comp in COMPONENT_ORDER:
            val = sim['per_component'].get(comp)
            if val is not None:
                line += f" {val:>5.3f}"
            else:
                line += f" {'--':>5}"
        print(line)

    # Component variance analysis: which components have highest variance
    # across top neighbors (indicating discriminative power)
    print(f"\nComponent discriminative power (std dev across top {top_k} neighbors):")
    comp_values = {comp: [] for comp in COMPONENT_ORDER}
    for sim in analysis['similarities'][:top_k]:
        for comp in COMPONENT_ORDER:
            val = sim['per_component'].get(comp)
            if val is not None:
                comp_values[comp].append(val)

    comp_stats = []
    for comp in COMPONENT_ORDER:
        vals = comp_values[comp]
        if len(vals) >= 2:
            comp_stats.append((
                comp,
                np.mean(vals),
                np.std(vals),
                np.min(vals),
                np.max(vals),
            ))

    comp_stats.sort(key=lambda x: x[2], reverse=True)
    print(f"  {'Component':<14} {'Mean':>6} {'StdDev':>7} {'Min':>6} {'Max':>6}  {'Weight':>6}")
    for comp, mean, std, mn, mx in comp_stats:
        print(f"  {COMPONENT_LABELS[comp]:<14} {mean:>6.3f} {std:>7.3f} {mn:>6.3f} {mx:>6.3f}  {COMPONENT_WEIGHTS[comp]:>6.2f}")


def write_csv(all_analyses: List[dict], output_path: str, top_k: int = 10):
    """Write per-component similarity data to CSV."""
    with open(output_path, 'w', newline='') as f:
        fieldnames = [
            'source_id', 'source_title', 'target_id', 'target_title',
            'rank', 'weighted_similarity',
        ] + [f'sim_{comp}' for comp in COMPONENT_ORDER]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for analysis in all_analyses:
            for rank, sim in enumerate(analysis['similarities'][:top_k], 1):
                row = {
                    'source_id': analysis['source_id'],
                    'source_title': analysis['source_title'],
                    'target_id': sim['target_id'],
                    'target_title': sim['target_title'],
                    'rank': rank,
                    'weighted_similarity': round(sim['weighted_similarity'], 4),
                }
                for comp in COMPONENT_ORDER:
                    val = sim['per_component'].get(comp)
                    row[f'sim_{comp}'] = round(val, 4) if val is not None else ''
                writer.writerow(row)

    print(f"\nCSV written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Per-component similarity analysis for ICCBR Section 5.5'
    )
    parser.add_argument(
        '--cases', type=str, default='14,18,58',
        help='Comma-separated source case IDs (default: 14,18,58 divergent cases)'
    )
    parser.add_argument('--all', action='store_true', help='Analyze all cases')
    parser.add_argument('--top', type=int, default=10, help='Top K neighbors to show')
    parser.add_argument('--output', type=str, help='Output CSV path')

    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        # Get all case IDs with component embeddings
        valid_ids = get_cases_with_component_embeddings()
        print(f"Cases with component embeddings: {len(valid_ids)}")
        print(f"Case IDs: {valid_ids}")

        # Load the embedding model once
        print("Loading embedding model...")
        model = get_local_model()

        # Generate per-component embeddings for ALL cases (needed for pairwise comparison)
        print("Generating per-component embeddings for all cases...")
        all_embeddings: Dict[int, Dict[str, np.ndarray]] = {}
        for case_id in valid_ids:
            embs = generate_component_embeddings(case_id, model)
            if embs:
                all_embeddings[case_id] = embs
                print(f"  Case {case_id}: {len(embs)} components "
                      f"({', '.join(sorted(embs.keys()))})")

        print(f"\nGenerated embeddings for {len(all_embeddings)} cases")

        # Determine which cases to analyze in detail
        if args.all:
            source_ids = list(all_embeddings.keys())
        else:
            source_ids = [int(c.strip()) for c in args.cases.split(',')]
            # Validate
            for sid in source_ids:
                if sid not in all_embeddings:
                    print(f"WARNING: Case {sid} not in embedding set, skipping")
            source_ids = [sid for sid in source_ids if sid in all_embeddings]

        # Run analysis
        all_analyses = []
        for source_id in source_ids:
            analysis = analyze_divergent_case(
                source_id, all_embeddings, top_k=args.top
            )
            all_analyses.append(analysis)
            print_case_analysis(analysis, args.top)

        # Write CSV
        if args.output:
            write_csv(all_analyses, args.output, args.top)
        else:
            # Default output location
            default_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'docs-internal', 'conferences_submissions', 'iccbr',
                'per_component_similarity.csv'
            )
            write_csv(all_analyses, default_path, args.top)


if __name__ == '__main__':
    main()
