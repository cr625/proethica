#!/usr/bin/env python
"""
Simple test script for Precedent Discovery Services
Uses direct database and service access without full Flask app.

Usage:
    cd /home/chris/onto/proethica
    source venv-proethica/bin/activate
    python experiments/test_precedent_simple.py
"""

import sys
import os

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import psycopg2
import numpy as np
from typing import Dict, List, Optional

# Database connection
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'ai_ethical_dm',
    'user': 'postgres',
    'password': 'PASS'
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def test_database_schema():
    """Verify the precedent tables exist."""
    print("\n" + "="*60)
    print("Testing Database Schema")
    print("="*60)

    conn = get_connection()
    cur = conn.cursor()

    tables = [
        'case_precedent_features',
        'precedent_similarity_cache',
        'precedent_discoveries'
    ]

    for table in tables:
        cur.execute(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = '{table}'
            )
        """)
        exists = cur.fetchone()[0]
        status = "EXISTS" if exists else "MISSING"
        print(f"  {table}: {status}")

    # Check functions
    cur.execute("""
        SELECT proname FROM pg_proc
        WHERE proname IN ('calculate_provision_overlap', 'calculate_outcome_alignment')
    """)
    functions = [row[0] for row in cur.fetchall()]
    print(f"\n  SQL functions: {functions}")

    conn.close()
    return True


def test_case_count():
    """Count available cases."""
    print("\n" + "="*60)
    print("Testing Case Count")
    print("="*60)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, source
        FROM documents
        WHERE document_type IN ('case', 'case_study')
        ORDER BY id
    """)
    cases = cur.fetchall()

    print(f"\nFound {len(cases)} cases:")
    for case_id, title, source in cases[:10]:
        print(f"  {case_id}: {title[:50]}")
    if len(cases) > 10:
        print(f"  ... and {len(cases) - 10} more")

    conn.close()
    return len(cases) >= 1


def test_section_embeddings():
    """Verify section embeddings exist."""
    print("\n" + "="*60)
    print("Testing Section Embeddings")
    print("="*60)

    conn = get_connection()
    cur = conn.cursor()

    # Check embedding counts
    cur.execute("""
        SELECT
            d.id,
            d.title,
            COUNT(ds.id) as section_count,
            SUM(CASE WHEN ds.embedding IS NOT NULL THEN 1 ELSE 0 END) as with_embedding
        FROM documents d
        LEFT JOIN document_sections ds ON d.id = ds.document_id
        WHERE d.document_type IN ('case', 'case_study')
        GROUP BY d.id, d.title
        ORDER BY d.id
        LIMIT 5
    """)
    results = cur.fetchall()

    print("\nSection embedding status:")
    for case_id, title, section_count, with_embedding in results:
        print(f"  Case {case_id}: {section_count} sections, {with_embedding} with embeddings")

    conn.close()
    return True


def test_outcome_extraction():
    """Test outcome extraction patterns."""
    print("\n" + "="*60)
    print("Testing Outcome Extraction")
    print("="*60)

    import re

    test_conclusions = [
        ("Engineer A was ethical in declining to work on the project.",
         "ethical"),
        ("The conduct of Engineer B was unethical because it violated Code Section II.1.a.",
         "unethical"),
        ("Engineer C's actions were not ethical under the circumstances.",
         "unethical"),
        ("It is the Board's opinion that Engineer A did not violate the Code.",
         "ethical"),
        ("The engineer's conduct violates Section III.2.a of the Code.",
         "unethical"),
        ("The action was in accordance with the Code of Ethics.",
         "ethical"),
    ]

    # Updated patterns matching case_feature_extractor.py
    def detect_outcome(text):
        text_lower = text.lower()
        ethical_indicators = []
        unethical_indicators = []

        # Check "not ethical" before "ethical"
        if re.search(r'\b(was|is|would be|were)\s+not\s+ethical\b', text_lower):
            unethical_indicators.append('was not ethical')
        elif re.search(r'\b(was|is|would be|were)\s+ethical\b', text_lower):
            ethical_indicators.append('ethical')

        # Explicit "unethical"
        if re.search(r'\bunethical\b', text_lower):
            unethical_indicators.append('unethical')

        # "did not violate" vs "violates"
        if re.search(r'\b(did|does|do)\s+not\s+violate\b', text_lower):
            ethical_indicators.append('did not violate')
        elif re.search(r'\bviolat(es?|ed|ing)\b', text_lower):
            unethical_indicators.append('violates')

        # "in accordance with"
        if re.search(r'\bin\s+(?:accordance|compliance)\s+with\b', text_lower):
            ethical_indicators.append('in accordance')

        if len(ethical_indicators) > 0 and len(unethical_indicators) == 0:
            return 'ethical'
        elif len(unethical_indicators) > 0 and len(ethical_indicators) == 0:
            return 'unethical'
        elif len(ethical_indicators) > 0 and len(unethical_indicators) > 0:
            return 'mixed'
        return None

    all_correct = True
    for conclusion, expected in test_conclusions:
        detected = detect_outcome(conclusion)

        status = "OK" if detected == expected else "FAIL"
        if detected != expected:
            all_correct = False
        print(f"  [{status}] Expected: {expected}, Got: {detected}")
        print(f"      Text: {conclusion[:60]}...")

    return all_correct


def test_provision_extraction():
    """Test provision pattern matching."""
    print("\n" + "="*60)
    print("Testing Provision Extraction")
    print("="*60)

    import re

    # Provision pattern
    pattern = re.compile(
        r'\b(I{1,3}|IV)\s*\.\s*(\d+)\s*(?:\.\s*([a-z]))?\.?\b',
        re.IGNORECASE
    )

    test_texts = [
        "Section II.1.a requires engineers to...",
        "According to I.1 and III.2.b...",
        "The provisions II.4.a, II.4.b, and II.4.c apply here.",
        "Under Code Section IV.1...",
    ]

    for text in test_texts:
        matches = []
        for match in pattern.finditer(text):
            roman = match.group(1).upper()
            number = match.group(2)
            letter = match.group(3).lower() if match.group(3) else None
            if letter:
                provision = f"{roman}.{number}.{letter}"
            else:
                provision = f"{roman}.{number}"
            matches.append(provision)
        print(f"  Text: {text[:50]}...")
        print(f"  Found: {matches}")

    return True


def test_similarity_functions():
    """Test SQL similarity functions."""
    print("\n" + "="*60)
    print("Testing SQL Similarity Functions")
    print("="*60)

    conn = get_connection()
    cur = conn.cursor()

    # Test provision overlap
    cur.execute("""
        SELECT calculate_provision_overlap(
            ARRAY['I.1', 'II.1.a', 'III.2'],
            ARRAY['I.1', 'II.1.b', 'III.2']
        )
    """)
    overlap = cur.fetchone()[0]
    print(f"\n  Provision overlap (2/4 matching): {overlap:.4f}")
    assert abs(overlap - 0.5) < 0.01, f"Expected 0.5, got {overlap}"

    # Test outcome alignment
    cur.execute("SELECT calculate_outcome_alignment('ethical', 'ethical')")
    same = cur.fetchone()[0]
    print(f"  Outcome alignment (same): {same:.4f}")
    assert same == 1.0, f"Expected 1.0, got {same}"

    cur.execute("SELECT calculate_outcome_alignment('ethical', 'unethical')")
    opposite = cur.fetchone()[0]
    print(f"  Outcome alignment (opposite): {opposite:.4f}")
    assert opposite == 0.0, f"Expected 0.0, got {opposite}"

    cur.execute("SELECT calculate_outcome_alignment('ethical', 'mixed')")
    mixed = cur.fetchone()[0]
    print(f"  Outcome alignment (mixed): {mixed:.4f}")
    assert mixed == 0.5, f"Expected 0.5, got {mixed}"

    conn.close()
    print("\n  All SQL functions working correctly!")
    return True


def test_insert_sample_features():
    """Insert sample features for testing."""
    print("\n" + "="*60)
    print("Inserting Sample Features")
    print("="*60)

    conn = get_connection()
    cur = conn.cursor()

    # Get first few cases
    cur.execute("""
        SELECT id, title FROM documents
        WHERE document_type IN ('case', 'case_study')
        ORDER BY id LIMIT 3
    """)
    cases = cur.fetchall()

    if not cases:
        print("  No cases found!")
        conn.close()
        return False

    # Generate sample embeddings (random for testing)
    for case_id, title in cases:
        # Random 384-dim embedding for testing
        embedding = np.random.randn(384).tolist()

        # Sample data
        provisions = ['I.1', 'II.1.a']
        tags = ['competence', 'public safety']
        outcome = 'ethical' if case_id % 2 == 0 else 'unethical'

        cur.execute("""
            INSERT INTO case_precedent_features (
                case_id, outcome_type, outcome_confidence, outcome_reasoning,
                provisions_cited, provision_count, subject_tags,
                combined_embedding, extraction_method
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (case_id) DO UPDATE SET
                outcome_type = EXCLUDED.outcome_type,
                provisions_cited = EXCLUDED.provisions_cited,
                combined_embedding = EXCLUDED.combined_embedding,
                extracted_at = CURRENT_TIMESTAMP
        """, (
            case_id, outcome, 0.8, f'Test extraction for case {case_id}',
            provisions, len(provisions), tags,
            embedding, 'test'
        ))

        print(f"  Inserted features for case {case_id}: {title[:40]}...")

    conn.commit()
    conn.close()

    print("\n  Sample features inserted successfully!")
    return True


def test_similarity_query():
    """Test similarity query using embeddings."""
    print("\n" + "="*60)
    print("Testing Similarity Query")
    print("="*60)

    conn = get_connection()
    cur = conn.cursor()

    # Check if we have features
    cur.execute("SELECT COUNT(*) FROM case_precedent_features")
    count = cur.fetchone()[0]
    print(f"\n  Features in database: {count}")

    if count < 2:
        print("  Not enough features for similarity test")
        conn.close()
        return True

    # Get first case
    cur.execute("SELECT case_id FROM case_precedent_features LIMIT 1")
    source_id = cur.fetchone()[0]

    # Find similar cases using combined_embedding
    cur.execute("""
        SELECT
            cpf2.case_id,
            d.title,
            1 - (cpf1.combined_embedding <=> cpf2.combined_embedding) as cosine_sim,
            calculate_provision_overlap(cpf1.provisions_cited, cpf2.provisions_cited) as prov_overlap,
            calculate_outcome_alignment(cpf1.outcome_type, cpf2.outcome_type) as outcome_align
        FROM case_precedent_features cpf1
        CROSS JOIN case_precedent_features cpf2
        JOIN documents d ON cpf2.case_id = d.id
        WHERE cpf1.case_id = %s
        AND cpf2.case_id != %s
        AND cpf1.combined_embedding IS NOT NULL
        AND cpf2.combined_embedding IS NOT NULL
        ORDER BY cosine_sim DESC
        LIMIT 5
    """, (source_id, source_id))

    results = cur.fetchall()

    print(f"\n  Similar cases to case {source_id}:")
    for target_id, title, cosine_sim, prov_overlap, outcome_align in results:
        weighted = 0.5 * cosine_sim + 0.3 * prov_overlap + 0.2 * outcome_align
        print(f"    Case {target_id}: {title[:30]}...")
        print(f"      Cosine: {cosine_sim:.4f}, Provisions: {prov_overlap:.4f}, Outcome: {outcome_align:.4f}")
        print(f"      Weighted: {weighted:.4f}")

    conn.close()
    return True


def main():
    """Run all tests."""
    print("Precedent Discovery Simple Tests")
    print("="*60)

    tests = [
        ("Database Schema", test_database_schema),
        ("Case Count", test_case_count),
        ("Section Embeddings", test_section_embeddings),
        ("Outcome Extraction", test_outcome_extraction),
        ("Provision Extraction", test_provision_extraction),
        ("SQL Functions", test_similarity_functions),
        ("Insert Sample Features", test_insert_sample_features),
        ("Similarity Query", test_similarity_query),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n  ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    for name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"  {name}: {status}")

    passed = sum(1 for _, s in results if s)
    print(f"\nTotal: {passed}/{len(results)} tests passed")

    return passed == len(results)


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
