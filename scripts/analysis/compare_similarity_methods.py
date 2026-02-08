#!/usr/bin/env python3
"""
Compare section-based vs component-based similarity methods.

Generates analysis data for ICCBR paper comparing:
1. Section-based: facts + discussion embeddings (monolithic)
2. Component-based: 9-component weighted aggregation (structured)

Output includes:
- Ranking comparison (Spearman correlation, overlap metrics)
- Score distribution analysis
- Case-level similarity changes
- Component contribution breakdown

Usage:
    python scripts/analysis/compare_similarity_methods.py --case 7
    python scripts/analysis/compare_similarity_methods.py --all --output results.csv
    python scripts/analysis/compare_similarity_methods.py --case 7 --top 10 --verbose
"""

import argparse
import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, '/home/chris/onto')

from app import create_app
from app.models import Document, db
from app.services.precedent.similarity_service import PrecedentSimilarityService
from sqlalchemy import text


def get_cases_with_component_embeddings():
    """Get case IDs that have component-aggregated embeddings."""
    result = db.session.execute(text("""
        SELECT case_id FROM case_precedent_features
        WHERE combined_embedding IS NOT NULL
        AND extraction_method = 'component_aggregation'
        ORDER BY case_id
    """)).fetchall()
    return [r[0] for r in result]


def get_case_title(case_id: int) -> str:
    """Get title for a case."""
    doc = Document.query.get(case_id)
    return doc.title if doc else f"Case {case_id}"


def compare_rankings(section_results, component_results, top_k: int = 10):
    """
    Compare rankings between two methods.

    Returns dict with:
    - spearman_rho: Rank correlation coefficient
    - overlap_at_k: % of same cases in top K
    - rank_changes: List of (case_id, section_rank, component_rank, change)
    """
    # Build rank maps
    section_ranks = {r.target_case_id: i + 1 for i, r in enumerate(section_results)}
    component_ranks = {r.target_case_id: i + 1 for i, r in enumerate(component_results)}

    # Get all cases appearing in either list
    all_cases = set(section_ranks.keys()) | set(component_ranks.keys())

    # Spearman correlation (on overlapping cases)
    common_cases = set(section_ranks.keys()) & set(component_ranks.keys())
    if len(common_cases) > 1:
        n = len(common_cases)
        d_squared_sum = sum(
            (section_ranks[c] - component_ranks[c]) ** 2
            for c in common_cases
        )
        spearman_rho = 1 - (6 * d_squared_sum) / (n * (n**2 - 1))
    else:
        spearman_rho = 0.0

    # Overlap at K
    section_top_k = set(r.target_case_id for r in section_results[:top_k])
    component_top_k = set(r.target_case_id for r in component_results[:top_k])
    overlap_at_k = len(section_top_k & component_top_k) / top_k if top_k > 0 else 0.0

    # Rank changes for top K from each method
    rank_changes = []
    examined_cases = section_top_k | component_top_k
    for case_id in examined_cases:
        s_rank = section_ranks.get(case_id, len(section_results) + 1)
        c_rank = component_ranks.get(case_id, len(component_results) + 1)
        change = s_rank - c_rank  # Positive = moved up in component ranking
        rank_changes.append((case_id, s_rank, c_rank, change))

    rank_changes.sort(key=lambda x: abs(x[3]), reverse=True)

    return {
        'spearman_rho': spearman_rho,
        'overlap_at_k': overlap_at_k,
        'rank_changes': rank_changes
    }


def compare_case(case_id: int, service: PrecedentSimilarityService,
                 top_k: int = 10, verbose: bool = False) -> dict:
    """
    Compare similarity methods for a single case.

    Returns comparison metrics and details.
    """
    # Get results using both methods
    section_results = service.find_similar_cases(
        case_id, limit=top_k * 2, use_component_embedding=False
    )
    component_results = service.find_similar_cases(
        case_id, limit=top_k * 2, use_component_embedding=True
    )

    # Filter to cases with component embeddings for fair comparison
    valid_case_ids = set(get_cases_with_component_embeddings())
    section_results = [r for r in section_results if r.target_case_id in valid_case_ids]
    component_results = [r for r in component_results if r.target_case_id in valid_case_ids]

    # Compare rankings
    ranking_comparison = compare_rankings(section_results, component_results, top_k)

    # Score statistics
    section_scores = [r.overall_similarity for r in section_results[:top_k]]
    component_scores = [r.overall_similarity for r in component_results[:top_k]]

    result = {
        'case_id': case_id,
        'case_title': get_case_title(case_id),
        'spearman_rho': ranking_comparison['spearman_rho'],
        'overlap_at_k': ranking_comparison['overlap_at_k'],
        'section_mean_score': sum(section_scores) / len(section_scores) if section_scores else 0,
        'component_mean_score': sum(component_scores) / len(component_scores) if component_scores else 0,
        'rank_changes': ranking_comparison['rank_changes'][:5],  # Top 5 biggest changes
    }

    if verbose:
        result['section_top_k'] = [
            {
                'case_id': r.target_case_id,
                'title': get_case_title(r.target_case_id)[:40],
                'score': round(r.overall_similarity, 3),
                'components': {k: round(v, 3) for k, v in r.component_scores.items()}
            }
            for r in section_results[:top_k]
        ]
        result['component_top_k'] = [
            {
                'case_id': r.target_case_id,
                'title': get_case_title(r.target_case_id)[:40],
                'score': round(r.overall_similarity, 3),
                'components': {k: round(v, 3) for k, v in r.component_scores.items()}
            }
            for r in component_results[:top_k]
        ]

    return result


def print_comparison(result: dict, verbose: bool = False):
    """Pretty print comparison results."""
    print(f"\n{'='*70}")
    print(f"Case {result['case_id']}: {result['case_title'][:50]}")
    print(f"{'='*70}")

    print(f"\nRanking Comparison:")
    print(f"  Spearman rho: {result['spearman_rho']:.3f}")
    print(f"  Overlap@K:    {result['overlap_at_k']:.1%}")

    print(f"\nScore Statistics:")
    print(f"  Section mean:   {result['section_mean_score']:.3f}")
    print(f"  Component mean: {result['component_mean_score']:.3f}")

    if result['rank_changes']:
        print(f"\nBiggest Rank Changes (positive = higher in component ranking):")
        for case_id, s_rank, c_rank, change in result['rank_changes']:
            title = get_case_title(case_id)[:30]
            direction = "UP" if change > 0 else "DOWN" if change < 0 else "SAME"
            print(f"  Case {case_id} ({title}): {s_rank} -> {c_rank} ({direction} {abs(change)})")

    if verbose and 'section_top_k' in result:
        print(f"\nSection-based Top Results:")
        for i, r in enumerate(result['section_top_k'], 1):
            print(f"  {i}. Case {r['case_id']} ({r['title']}) - {r['score']:.3f}")

        print(f"\nComponent-based Top Results:")
        for i, r in enumerate(result['component_top_k'], 1):
            print(f"  {i}. Case {r['case_id']} ({r['title']}) - {r['score']:.3f}")


def main():
    parser = argparse.ArgumentParser(
        description='Compare section-based vs component-based similarity'
    )
    parser.add_argument('--case', type=int, help='Compare for a single case')
    parser.add_argument('--cases', type=str, help='Comma-separated list of case IDs')
    parser.add_argument('--all', action='store_true', help='Compare all cases with embeddings')
    parser.add_argument('--top', type=int, default=10, help='Top K for overlap calculation')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed results')
    parser.add_argument('--output', type=str, help='Output CSV file path')

    args = parser.parse_args()

    if not args.case and not args.cases and not args.all:
        parser.print_help()
        print("\nError: Specify --case, --cases, or --all")
        sys.exit(1)

    # Create Flask app context
    app = create_app()
    with app.app_context():
        service = PrecedentSimilarityService()

        # Determine which cases to compare
        if args.case:
            case_ids = [args.case]
        elif args.cases:
            case_ids = [int(c.strip()) for c in args.cases.split(',')]
        else:
            case_ids = get_cases_with_component_embeddings()

        print(f"\nSimilarity Method Comparison")
        print(f"{'='*70}")
        print(f"Cases to compare: {len(case_ids)}")
        print(f"Top K: {args.top}")
        print(f"Verbose: {args.verbose}")

        results = []
        for case_id in case_ids:
            try:
                result = compare_case(case_id, service, args.top, args.verbose)
                results.append(result)
                print_comparison(result, args.verbose)
            except Exception as e:
                print(f"\nError comparing case {case_id}: {e}")

        # Summary statistics
        if len(results) > 1:
            print(f"\n{'='*70}")
            print("SUMMARY")
            print(f"{'='*70}")

            avg_rho = sum(r['spearman_rho'] for r in results) / len(results)
            avg_overlap = sum(r['overlap_at_k'] for r in results) / len(results)
            avg_section = sum(r['section_mean_score'] for r in results) / len(results)
            avg_component = sum(r['component_mean_score'] for r in results) / len(results)

            print(f"\nAcross {len(results)} cases:")
            print(f"  Average Spearman rho:      {avg_rho:.3f}")
            print(f"  Average Overlap@{args.top}:       {avg_overlap:.1%}")
            print(f"  Average Section Score:     {avg_section:.3f}")
            print(f"  Average Component Score:   {avg_component:.3f}")

            # Find cases with most different rankings
            by_rho = sorted(results, key=lambda r: r['spearman_rho'])
            print(f"\nCases with most different rankings (lowest rho):")
            for r in by_rho[:3]:
                print(f"  Case {r['case_id']}: rho={r['spearman_rho']:.3f}")

        # Output CSV if requested
        if args.output:
            import csv
            with open(args.output, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'case_id', 'case_title', 'spearman_rho', 'overlap_at_k',
                    'section_mean_score', 'component_mean_score'
                ])
                writer.writeheader()
                for r in results:
                    writer.writerow({
                        'case_id': r['case_id'],
                        'case_title': r['case_title'],
                        'spearman_rho': round(r['spearman_rho'], 4),
                        'overlap_at_k': round(r['overlap_at_k'], 4),
                        'section_mean_score': round(r['section_mean_score'], 4),
                        'component_mean_score': round(r['component_mean_score'], 4)
                    })
            print(f"\nResults saved to: {args.output}")


if __name__ == '__main__':
    main()
