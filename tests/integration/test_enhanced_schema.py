#!/usr/bin/env python3
"""
Test Enhanced Guideline Association Schema

Simple test script that validates the database schema and demonstrates
the enhanced association capabilities.

Usage: python test_enhanced_schema.py
"""

import psycopg2
import json
import os
from datetime import datetime
from urllib.parse import urlparse

def connect_to_database():
    """Connect to the database using environment variables or defaults"""
    db_url = os.getenv('DATABASE_URL', 'postgresql://ai_ethical_dm_user:password@localhost:5433/ai_ethical_dm')
    
    try:
        parsed = urlparse(db_url)
        conn_params = {
            'host': parsed.hostname,
            'port': parsed.port,
            'user': parsed.username,
            'password': parsed.password,
            'database': parsed.path[1:]
        }
        
        return psycopg2.connect(**conn_params)
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("Make sure PostgreSQL is running and DATABASE_URL is correct")
        return None

def test_schema_structure(cursor):
    """Test that all tables and columns exist"""
    print("🔍 Testing Schema Structure...")
    
    required_tables = {
        'case_guideline_associations': 15,
        'outcome_patterns': 14, 
        'case_prediction_results': 16
    }
    
    for table_name, expected_columns in required_tables.items():
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = %s
        """, (table_name,))
        
        actual_columns = cursor.fetchone()[0]
        
        if actual_columns == expected_columns:
            print(f"  ✅ {table_name}: {actual_columns} columns")
        else:
            print(f"  ❌ {table_name}: expected {expected_columns}, got {actual_columns}")
            return False
    
    return True

def test_outcome_patterns(cursor):
    """Test outcome patterns data"""
    print("\n📊 Testing Outcome Patterns...")
    
    cursor.execute("SELECT COUNT(*) FROM outcome_patterns WHERE is_active = true")
    pattern_count = cursor.fetchone()[0]
    
    if pattern_count >= 8:
        print(f"  ✅ Found {pattern_count} active patterns")
    else:
        print(f"  ❌ Expected at least 8 patterns, found {pattern_count}")
        return False
    
    # Test specific patterns
    test_patterns = [
        ('public_safety_prioritized', 0.9, 0.1),
        ('safety_risk_ignored', 0.1, 0.9)
    ]
    
    for pattern_name, min_ethical, max_ethical in test_patterns:
        cursor.execute("""
            SELECT ethical_correlation, unethical_correlation 
            FROM outcome_patterns 
            WHERE pattern_name = %s
        """, (pattern_name,))
        
        result = cursor.fetchone()
        if result:
            ethical, unethical = result
            if ethical >= min_ethical and ethical <= max_ethical:
                print(f"  ✅ {pattern_name}: ethical={ethical:.3f}, unethical={unethical:.3f}")
            else:
                print(f"  ❌ {pattern_name}: unexpected correlation values")
                return False
        else:
            print(f"  ❌ Pattern '{pattern_name}' not found")
            return False
    
    return True

def test_association_insertion(cursor):
    """Test inserting a sample association"""
    print("\n💾 Testing Association Insertion...")
    
    # Check if we have any scenarios to work with
    cursor.execute("SELECT id FROM scenarios LIMIT 1")
    scenario_result = cursor.fetchone()
    
    if not scenario_result:
        print("  ⚠️  No scenarios found - skipping insertion test")
        return True
    
    scenario_id = scenario_result[0]
    
    # Check if we have any guideline concepts
    cursor.execute("""
        SELECT id FROM entity_triples 
        WHERE entity_type = 'guideline_concept' 
        LIMIT 1
    """)
    concept_result = cursor.fetchone()
    
    if not concept_result:
        print("  ⚠️  No guideline concepts found - skipping insertion test")
        return True
    
    concept_id = concept_result[0]
    
    # Insert test association
    test_association = {
        'case_id': scenario_id,
        'guideline_concept_id': concept_id,
        'section_type': 'test_section',
        'semantic_similarity': 0.75,
        'keyword_overlap': 0.60,
        'contextual_relevance': 0.80,
        'overall_confidence': 0.72,
        'pattern_indicators': json.dumps({
            'test_mode': True,
            'safety_mentioned': True,
            'confidence_level': 0.72
        }),
        'association_reasoning': 'Test association for schema validation',
        'association_method': 'test'
    }
    
    try:
        cursor.execute("""
            INSERT INTO case_guideline_associations 
            (case_id, guideline_concept_id, section_type, semantic_similarity,
             keyword_overlap, contextual_relevance, overall_confidence,
             pattern_indicators, association_reasoning, association_method)
            VALUES (%(case_id)s, %(guideline_concept_id)s, %(section_type)s,
                   %(semantic_similarity)s, %(keyword_overlap)s, %(contextual_relevance)s,
                   %(overall_confidence)s, %(pattern_indicators)s, %(association_reasoning)s,
                   %(association_method)s)
            RETURNING id
        """, test_association)
        
        association_id = cursor.fetchone()[0]
        print(f"  ✅ Test association created with ID: {association_id}")
        
        # Verify the data
        cursor.execute("""
            SELECT overall_confidence, pattern_indicators 
            FROM case_guideline_associations 
            WHERE id = %s
        """, (association_id,))
        
        confidence, indicators = cursor.fetchone()
        indicators_data = json.loads(indicators) if indicators else {}
        
        print(f"  ✅ Confidence: {confidence}, Indicators: {len(indicators_data)} keys")
        
        # Clean up test data
        cursor.execute("DELETE FROM case_guideline_associations WHERE id = %s", (association_id,))
        print("  ✅ Test data cleaned up")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Association insertion failed: {e}")
        return False

def test_prediction_functions(cursor):
    """Test the prediction analysis functions"""
    print("\n🧮 Testing Prediction Functions...")
    
    try:
        # Test accuracy calculation function
        cursor.execute("SELECT * FROM calculate_prediction_accuracy() LIMIT 1")
        print("  ✅ calculate_prediction_accuracy() function works")
        
        # Test summary function  
        cursor.execute("SELECT * FROM get_prediction_summary_by_outcome() LIMIT 1")
        print("  ✅ get_prediction_summary_by_outcome() function works")
        
        # Test view
        cursor.execute("SELECT * FROM prediction_accuracy_summary LIMIT 1")
        print("  ✅ prediction_accuracy_summary view works")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Function test failed: {e}")
        return False

def test_jsonb_operations(cursor):
    """Test JSONB operations and indexes"""
    print("\n🔗 Testing JSONB Operations...")
    
    try:
        # Test pattern criteria query
        cursor.execute("""
            SELECT pattern_name 
            FROM outcome_patterns 
            WHERE pattern_criteria @> '{"public_safety_association": ">0.8"}'
        """)
        
        results = cursor.fetchall()
        if results:
            print(f"  ✅ JSONB containment query found {len(results)} patterns")
        else:
            print("  ⚠️  No patterns found with safety criteria (may be normal)")
        
        # Test array operations
        cursor.execute("""
            SELECT pattern_name 
            FROM outcome_patterns 
            WHERE 'discussion' = ANY(section_types)
        """)
        
        results = cursor.fetchall()
        print(f"  ✅ Array query found {len(results)} patterns for discussion sections")
        
        return True
        
    except Exception as e:
        print(f"  ❌ JSONB operations failed: {e}")
        return False

def display_schema_summary(cursor):
    """Display a summary of the schema capabilities"""
    print("\n📋 Schema Summary:")
    
    # Count data in each table
    tables = ['case_guideline_associations', 'outcome_patterns', 'case_prediction_results']
    
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  📊 {table}: {count} records")
    
    # Show pattern types
    cursor.execute("SELECT DISTINCT pattern_type FROM outcome_patterns")
    pattern_types = [row[0] for row in cursor.fetchall()]
    print(f"  🎯 Pattern types: {', '.join(pattern_types)}")
    
    # Show confidence range in patterns
    cursor.execute("""
        SELECT MIN(confidence_level), MAX(confidence_level), AVG(confidence_level)
        FROM outcome_patterns 
        WHERE confidence_level IS NOT NULL
    """)
    
    result = cursor.fetchone()
    if result and result[0] is not None:
        min_conf, max_conf, avg_conf = result
        print(f"  📈 Pattern confidence range: {min_conf:.3f} - {max_conf:.3f} (avg: {avg_conf:.3f})")

def main():
    """Main test function"""
    print("🧪 Enhanced Guideline Association Schema Test")
    print("=" * 50)
    
    # Connect to database
    conn = connect_to_database()
    if not conn:
        return 1
    
    cursor = conn.cursor()
    
    try:
        # Run all tests
        tests = [
            test_schema_structure,
            test_outcome_patterns,
            test_association_insertion,
            test_prediction_functions,
            test_jsonb_operations
        ]
        
        passed = 0
        total = len(tests)
        
        for test_func in tests:
            if test_func(cursor):
                passed += 1
            conn.commit()  # Commit after each test
        
        # Display summary
        display_schema_summary(cursor)
        
        print(f"\n🎯 Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("✅ All tests passed! Enhanced schema is working correctly.")
            return 0
        else:
            print("❌ Some tests failed. Check the output above.")
            return 1
            
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        return 1
        
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    exit(main())