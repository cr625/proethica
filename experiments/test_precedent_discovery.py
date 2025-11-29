#!/usr/bin/env python
"""
Test script for Precedent Discovery Services

Tests:
1. CaseFeatureExtractor - extracts features from cases
2. PrecedentSimilarityService - calculates multi-factor similarity
3. PrecedentDiscoveryService - orchestrates precedent finding

Usage:
    cd /home/chris/onto/proethica
    source venv-proethica/bin/activate
    python experiments/test_precedent_discovery.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Document
from app.services.precedent import (
    CaseFeatureExtractor,
    PrecedentSimilarityService,
    PrecedentDiscoveryService
)


def test_feature_extraction(case_id: int = 7):
    """Test feature extraction for a single case."""
    print(f"\n{'='*60}")
    print(f"Testing CaseFeatureExtractor on case {case_id}")
    print('='*60)

    extractor = CaseFeatureExtractor()

    try:
        features = extractor.extract_precedent_features(case_id)

        print(f"\nExtracted features:")
        print(f"  Outcome: {features.outcome_type} (confidence: {features.outcome_confidence:.2f})")
        print(f"  Outcome reasoning: {features.outcome_reasoning[:100]}...")
        print(f"  Provisions cited: {features.provisions_cited}")
        print(f"  Subject tags: {features.subject_tags}")
        print(f"  Transformation type: {features.transformation_type}")
        print(f"  Principle tensions: {len(features.principle_tensions)} found")
        print(f"  Obligation conflicts: {len(features.obligation_conflicts)} found")
        print(f"  Facts embedding: {'Present' if features.facts_embedding else 'None'}")
        print(f"  Discussion embedding: {'Present' if features.discussion_embedding else 'None'}")
        print(f"  Combined embedding: {'Present' if features.combined_embedding else 'None'}")

        # Save features
        feature_id = extractor.save_features(features)
        print(f"\nSaved features with ID: {feature_id}")

        return True

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_extract_all_cases():
    """Test extracting features for all cases."""
    print(f"\n{'='*60}")
    print("Testing CaseFeatureExtractor.extract_and_save_all_cases()")
    print('='*60)

    extractor = CaseFeatureExtractor()

    try:
        results = extractor.extract_and_save_all_cases()

        print(f"\nResults:")
        for case_id, success in results.items():
            status = "OK" if success else "FAILED"
            print(f"  Case {case_id}: {status}")

        success_count = sum(1 for v in results.values() if v)
        print(f"\nTotal: {success_count}/{len(results)} successful")

        return success_count == len(results)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_similarity_calculation(source_id: int = 7, target_id: int = 8):
    """Test similarity calculation between two cases."""
    print(f"\n{'='*60}")
    print(f"Testing PrecedentSimilarityService between cases {source_id} and {target_id}")
    print('='*60)

    similarity_service = PrecedentSimilarityService()

    try:
        result = similarity_service.calculate_similarity(source_id, target_id)

        print(f"\nSimilarity result:")
        print(f"  Overall similarity: {result.overall_similarity:.4f}")
        print(f"  Component scores:")
        for component, score in result.component_scores.items():
            print(f"    {component}: {score:.4f}")
        print(f"  Matching provisions: {result.matching_provisions}")
        print(f"  Outcome match: {result.outcome_match}")

        return True

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_find_similar_cases(source_id: int = 7):
    """Test finding similar cases."""
    print(f"\n{'='*60}")
    print(f"Testing PrecedentSimilarityService.find_similar_cases() for case {source_id}")
    print('='*60)

    similarity_service = PrecedentSimilarityService()

    try:
        results = similarity_service.find_similar_cases(
            source_case_id=source_id,
            limit=5,
            min_score=0.0  # Show all for testing
        )

        print(f"\nFound {len(results)} similar cases:")
        for i, result in enumerate(results, 1):
            case = Document.query.get(result.target_case_id)
            title = case.title[:50] if case else f"Case {result.target_case_id}"
            print(f"\n  {i}. Case {result.target_case_id}: {title}")
            print(f"     Overall: {result.overall_similarity:.4f}")
            print(f"     Matching provisions: {result.matching_provisions[:3]}")

        return True

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_precedent_discovery(source_id: int = 7):
    """Test the full precedent discovery service."""
    print(f"\n{'='*60}")
    print(f"Testing PrecedentDiscoveryService.find_precedents() for case {source_id}")
    print('='*60)

    # Without LLM client for testing
    discovery_service = PrecedentDiscoveryService(llm_client=None)

    try:
        matches = discovery_service.find_precedents(
            source_case_id=source_id,
            limit=5,
            min_score=0.0,
            include_llm_analysis=False
        )

        print(f"\nFound {len(matches)} precedent matches:")
        for i, match in enumerate(matches, 1):
            print(f"\n  {i}. {match.target_case_title[:50]}")
            print(f"     Score: {match.overall_score:.4f}")
            print(f"     Outcome: {match.target_outcome} (match: {match.outcome_match})")
            print(f"     Matching provisions: {match.matching_provisions[:3]}")
            print(f"     Transformation: {match.target_transformation}")

        return True

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_discovery():
    """Test batch precedent discovery."""
    print(f"\n{'='*60}")
    print("Testing PrecedentDiscoveryService.batch_discover_all()")
    print('='*60)

    discovery_service = PrecedentDiscoveryService(llm_client=None)

    try:
        results = discovery_service.batch_discover_all(
            min_score=0.2,
            top_k=3,
            save_results=True
        )

        print(f"\nBatch discovery complete:")
        for case_id, matches in results.items():
            case = Document.query.get(case_id)
            title = case.title[:30] if case else f"Case {case_id}"
            print(f"  {title}: {len(matches)} precedents")

        # Verify saved to database
        from sqlalchemy import text
        count = db.session.execute(
            text("SELECT COUNT(*) FROM precedent_discoveries")
        ).scalar()
        print(f"\nTotal precedent discoveries in database: {count}")

        return True

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("Precedent Discovery Service Tests")
    print("="*60)

    # Create Flask app context
    app = create_app()

    with app.app_context():
        # Get available cases
        cases = Document.query.filter(
            Document.document_type.in_(['case', 'case_study'])
        ).all()
        print(f"\nAvailable cases: {len(cases)}")
        for case in cases[:5]:
            print(f"  {case.id}: {case.title[:50]}")
        if len(cases) > 5:
            print(f"  ... and {len(cases) - 5} more")

        # Run tests
        tests = [
            ("Feature Extraction", lambda: test_feature_extraction(cases[0].id if cases else 7)),
            ("Extract All Cases", test_extract_all_cases),
            ("Similarity Calculation", lambda: test_similarity_calculation(
                cases[0].id if cases else 7,
                cases[1].id if len(cases) > 1 else 8
            )),
            ("Find Similar Cases", lambda: test_find_similar_cases(cases[0].id if cases else 7)),
            ("Precedent Discovery", lambda: test_precedent_discovery(cases[0].id if cases else 7)),
            ("Batch Discovery", test_batch_discovery),
        ]

        results = []
        for name, test_func in tests:
            try:
                success = test_func()
                results.append((name, success))
            except Exception as e:
                print(f"\nTest '{name}' crashed: {e}")
                results.append((name, False))

        # Summary
        print(f"\n{'='*60}")
        print("Test Summary")
        print('='*60)
        for name, success in results:
            status = "PASS" if success else "FAIL"
            print(f"  {name}: {status}")

        passed = sum(1 for _, s in results if s)
        print(f"\nTotal: {passed}/{len(results)} tests passed")


if __name__ == '__main__':
    main()
