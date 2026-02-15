#!/usr/bin/env python3
"""
Compare extraction quality between Haiku and Opus models.

Phase 1 of pipeline harmonization: validate whether Haiku 4.5 produces
adequate D-tuple extraction quality compared to the Opus baseline already
stored in temporary_rdf_storage.

For each test case, runs the existing dual extractors with model_name
overridden to Haiku, then compares:
- Entity count per component
- Label overlap (Jaccard similarity)
- New vs existing class ratios

Usage:
    python scripts/analysis/compare_extraction_models.py
    python scripts/analysis/compare_extraction_models.py --cases 4,7,56
    python scripts/analysis/compare_extraction_models.py --concepts obligations,roles
    python scripts/analysis/compare_extraction_models.py --output results.csv
"""

import argparse
import csv
import sys
import os
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, '/home/chris/onto')

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# Map D-tuple component codes to extraction_type in temporary_rdf_storage
# and to the dual extractor class/method
CONCEPT_CONFIG = {
    'roles': {
        'code': 'R',
        'extraction_type': 'roles',
        'extractor_module': 'app.services.extraction.dual_role_extractor',
        'extractor_class': 'DualRoleExtractor',
        'extract_method': 'extract_dual_roles',
    },
    'states': {
        'code': 'S',
        'extraction_type': 'states',
        'extractor_module': 'app.services.extraction.dual_states_extractor',
        'extractor_class': 'DualStatesExtractor',
        'extract_method': 'extract_dual_states',
    },
    'resources': {
        'code': 'Rs',
        'extraction_type': 'resources',
        'extractor_module': 'app.services.extraction.dual_resources_extractor',
        'extractor_class': 'DualResourcesExtractor',
        'extract_method': 'extract_dual_resources',
    },
    'principles': {
        'code': 'P',
        'extraction_type': 'principles',
        'extractor_module': 'app.services.extraction.dual_principles_extractor',
        'extractor_class': 'DualPrinciplesExtractor',
        'extract_method': 'extract_dual_principles',
    },
    'obligations': {
        'code': 'O',
        'extraction_type': 'obligations',
        'extractor_module': 'app.services.extraction.dual_obligations_extractor',
        'extractor_class': 'DualObligationsExtractor',
        'extract_method': 'extract_dual_obligations',
    },
    'constraints': {
        'code': 'Cs',
        'extraction_type': 'constraints',
        'extractor_module': 'app.services.extraction.dual_constraints_extractor',
        'extractor_class': 'DualConstraintsExtractor',
        'extract_method': 'extract_dual_constraints',
    },
    'capabilities': {
        'code': 'Ca',
        'extraction_type': 'capabilities',
        'extractor_module': 'app.services.extraction.dual_capabilities_extractor',
        'extractor_class': 'DualCapabilitiesExtractor',
        'extract_method': 'extract_dual_capabilities',
    },
    'actions': {
        'code': 'A',
        'extraction_type': 'temporal_dynamics_enhanced',
        'entity_type_filter': 'actions',
        'extractor_module': 'app.services.extraction.dual_actions_extractor',
        'extractor_class': 'DualActionsExtractor',
        'extract_method': 'extract_dual_actions',
    },
    'events': {
        'code': 'E',
        'extraction_type': 'temporal_dynamics_enhanced',
        'entity_type_filter': 'events',
        'extractor_module': 'app.services.extraction.dual_events_extractor',
        'extractor_class': 'DualEventsExtractor',
        'extract_method': 'extract_dual_events',
    },
}

HAIKU_MODEL = 'claude-3-5-haiku-20241022'
SONNET_MODEL = 'claude-sonnet-4-5-20250929'


@dataclass
class ComparisonResult:
    case_id: int
    concept: str
    component_code: str
    baseline_count: int
    haiku_class_count: int
    haiku_individual_count: int
    haiku_total: int
    baseline_labels: List[str] = field(default_factory=list)
    haiku_labels: List[str] = field(default_factory=list)
    label_jaccard: float = 0.0
    duration_s: float = 0.0
    error: Optional[str] = None


def get_baseline_entities(case_id: int, extraction_type: str,
                          entity_type_filter: str = None) -> List[dict]:
    """Get existing entities from temporary_rdf_storage for comparison."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    query = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type=extraction_type
    )
    if entity_type_filter:
        query = query.filter(
            TemporaryRDFStorage.entity_type.ilike(f'%{entity_type_filter}%')
        )

    entities = query.all()
    return [{'label': e.entity_label, 'definition': e.entity_definition,
             'type': e.entity_type} for e in entities if e.entity_label]


def get_case_text(case_id: int, section_type: str = 'discussion') -> str:
    """Get case text from document sections."""
    from app.models.document_section import DocumentSection

    section = DocumentSection.query.filter_by(
        document_id=case_id,
        section_type=section_type
    ).first()
    if section and section.content:
        return section.content

    # Fallback to facts if no discussion
    section = DocumentSection.query.filter_by(
        document_id=case_id,
        section_type='facts'
    ).first()
    return section.content if section else ''


def normalize_label(label: str) -> str:
    """Normalize label for comparison."""
    return label.lower().strip().replace('-', ' ').replace('_', ' ')


def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def run_extractor(concept: str, case_text: str, case_id: int,
                  section_type: str, model: str) -> Tuple[list, list]:
    """Run a dual extractor with specified model, return (classes, individuals)."""
    import importlib

    config = CONCEPT_CONFIG[concept]
    module = importlib.import_module(config['extractor_module'])
    extractor_cls = getattr(module, config['extractor_class'])

    extractor = extractor_cls()
    extractor.model_name = model

    extract_fn = getattr(extractor, config['extract_method'])
    classes, individuals = extract_fn(case_text, case_id, section_type)

    return classes, individuals


def compare_concept(case_id: int, concept: str, case_text: str,
                    model: str = HAIKU_MODEL) -> ComparisonResult:
    """Compare one concept extraction between Haiku and stored baseline."""
    config = CONCEPT_CONFIG[concept]

    # Get baseline
    baseline = get_baseline_entities(
        case_id, config['extraction_type'],
        config.get('entity_type_filter')
    )
    baseline_labels = {normalize_label(e['label']) for e in baseline}

    result = ComparisonResult(
        case_id=case_id,
        concept=concept,
        component_code=config['code'],
        baseline_count=len(baseline),
        haiku_class_count=0,
        haiku_individual_count=0,
        haiku_total=0,
        baseline_labels=sorted(baseline_labels),
    )

    # Run Haiku extraction
    start = time.time()
    try:
        classes, individuals = run_extractor(
            concept, case_text, case_id, 'discussion', model
        )
        result.duration_s = time.time() - start
        result.haiku_class_count = len(classes)
        result.haiku_individual_count = len(individuals)
        result.haiku_total = len(classes) + len(individuals)

        # Extract labels from Haiku results
        haiku_labels = set()
        for c in classes:
            if hasattr(c, 'label') and c.label:
                haiku_labels.add(normalize_label(c.label))
        for ind in individuals:
            # Individuals have different label fields per concept
            label = getattr(ind, 'identifier', None) or getattr(ind, 'name', None) or ''
            if label:
                haiku_labels.add(normalize_label(label))

        result.haiku_labels = sorted(haiku_labels)
        result.label_jaccard = jaccard_similarity(baseline_labels, haiku_labels)

    except Exception as e:
        result.duration_s = time.time() - start
        result.error = str(e)[:200]
        logger.error(f"Error extracting {concept} for case {case_id}: {e}")

    return result


def print_result(result: ComparisonResult):
    """Print one comparison result."""
    if result.error:
        print(f"  {result.concept:<14} ({result.component_code:>2}) "
              f"ERROR: {result.error[:60]}")
        return

    count_ratio = (result.haiku_total / result.baseline_count * 100
                   if result.baseline_count > 0 else 0)
    jaccard_pct = result.label_jaccard * 100

    # Color coding via text markers
    count_marker = 'OK' if 0.5 <= count_ratio / 100 <= 2.0 else 'WARN'
    jaccard_marker = 'OK' if jaccard_pct > 20 else 'LOW'

    print(f"  {result.concept:<14} ({result.component_code:>2})  "
          f"baseline={result.baseline_count:>3}  "
          f"haiku={result.haiku_total:>3} "
          f"(cls={result.haiku_class_count}, ind={result.haiku_individual_count})  "
          f"count_ratio={count_ratio:>5.0f}% [{count_marker}]  "
          f"jaccard={jaccard_pct:>5.1f}% [{jaccard_marker}]  "
          f"{result.duration_s:.1f}s")


def print_label_diff(result: ComparisonResult):
    """Print label-level diff for one result."""
    baseline_set = set(result.baseline_labels)
    haiku_set = set(result.haiku_labels)

    only_baseline = sorted(baseline_set - haiku_set)
    only_haiku = sorted(haiku_set - baseline_set)
    shared = sorted(baseline_set & haiku_set)

    if shared:
        print(f"    Shared ({len(shared)}): {', '.join(shared[:5])}"
              f"{'...' if len(shared) > 5 else ''}")
    if only_baseline:
        print(f"    Only baseline ({len(only_baseline)}): {', '.join(only_baseline[:5])}"
              f"{'...' if len(only_baseline) > 5 else ''}")
    if only_haiku:
        print(f"    Only Haiku ({len(only_haiku)}): {', '.join(only_haiku[:5])}"
              f"{'...' if len(only_haiku) > 5 else ''}")


def main():
    parser = argparse.ArgumentParser(
        description='Compare extraction quality: Haiku vs Opus baseline'
    )
    parser.add_argument('--cases', type=str, default='4,7,56',
                        help='Comma-separated case IDs (default: 4,7,56)')
    parser.add_argument('--concepts', type=str, default=None,
                        help='Comma-separated concepts (default: all 9)')
    parser.add_argument('--model', type=str, default=HAIKU_MODEL,
                        help=f'Model to test (default: {HAIKU_MODEL})')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show label-level diffs')
    parser.add_argument('--output', type=str,
                        help='Output CSV path')

    args = parser.parse_args()

    case_ids = [int(c.strip()) for c in args.cases.split(',')]
    concepts = ([c.strip() for c in args.concepts.split(',')]
                if args.concepts else list(CONCEPT_CONFIG.keys()))

    from app import create_app
    app = create_app()

    with app.app_context():
        print(f"\nExtraction Model Comparison")
        print(f"{'=' * 80}")
        print(f"Test model:  {args.model}")
        print(f"Baseline:    Opus (stored in temporary_rdf_storage)")
        print(f"Cases:       {case_ids}")
        print(f"Concepts:    {concepts}")
        print()

        all_results: List[ComparisonResult] = []

        for case_id in case_ids:
            from app.models import Document
            doc = Document.query.get(case_id)
            title = doc.title[:50] if doc else f'Case {case_id}'
            print(f"\nCase {case_id}: {title}")
            print(f"{'-' * 80}")

            case_text = get_case_text(case_id, 'discussion')
            if not case_text:
                print(f"  No discussion text found, skipping")
                continue
            print(f"  Discussion text: {len(case_text)} chars")

            for concept in concepts:
                result = compare_concept(case_id, concept, case_text, args.model)
                all_results.append(result)
                print_result(result)
                if args.verbose and not result.error:
                    print_label_diff(result)

        # Summary
        valid = [r for r in all_results if not r.error]
        if valid:
            print(f"\n{'=' * 80}")
            print("SUMMARY")
            print(f"{'=' * 80}")

            avg_jaccard = sum(r.label_jaccard for r in valid) / len(valid)
            avg_duration = sum(r.duration_s for r in valid) / len(valid)
            total_baseline = sum(r.baseline_count for r in valid)
            total_haiku = sum(r.haiku_total for r in valid)
            errors = [r for r in all_results if r.error]

            print(f"\n  Comparisons:     {len(valid)} successful, {len(errors)} errors")
            print(f"  Avg Jaccard:     {avg_jaccard:.1%}")
            print(f"  Avg duration:    {avg_duration:.1f}s per concept")
            print(f"  Total baseline:  {total_baseline} entities")
            print(f"  Total Haiku:     {total_haiku} entities "
                  f"({total_haiku / total_baseline * 100:.0f}% of baseline)"
                  if total_baseline else "")

            # Per-concept summary
            print(f"\n  Per-concept averages:")
            for concept in concepts:
                concept_results = [r for r in valid if r.concept == concept]
                if concept_results:
                    avg_j = sum(r.label_jaccard for r in concept_results) / len(concept_results)
                    avg_base = sum(r.baseline_count for r in concept_results) / len(concept_results)
                    avg_haiku = sum(r.haiku_total for r in concept_results) / len(concept_results)
                    code = CONCEPT_CONFIG[concept]['code']
                    print(f"    {concept:<14} ({code:>2}): "
                          f"jaccard={avg_j:.1%}  "
                          f"baseline_avg={avg_base:.0f}  "
                          f"haiku_avg={avg_haiku:.0f}")

        # CSV output
        if args.output and all_results:
            with open(args.output, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'case_id', 'concept', 'component_code',
                    'baseline_count', 'haiku_class_count',
                    'haiku_individual_count', 'haiku_total',
                    'label_jaccard', 'duration_s', 'error'
                ])
                writer.writeheader()
                for r in all_results:
                    writer.writerow({
                        'case_id': r.case_id,
                        'concept': r.concept,
                        'component_code': r.component_code,
                        'baseline_count': r.baseline_count,
                        'haiku_class_count': r.haiku_class_count,
                        'haiku_individual_count': r.haiku_individual_count,
                        'haiku_total': r.haiku_total,
                        'label_jaccard': round(r.label_jaccard, 4),
                        'duration_s': round(r.duration_s, 2),
                        'error': r.error or '',
                    })
            print(f"\nResults saved to: {args.output}")


if __name__ == '__main__':
    main()
