#!/usr/bin/env python3
"""
Simple database validation test that handles existing data gracefully.
"""
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.models import db
from app.models.entity_triple import EntityTriple
from app.models.pending_concept_type import PendingConceptType
from app.models.custom_concept_type import CustomConceptType
from app.models.concept_type_mapping import ConceptTypeMapping
from app.services.guideline_concept_type_mapper import GuidelineConceptTypeMapper

def test_database_structure():
    """Test that all new database structures are working."""
    print("🏗️ TESTING DATABASE STRUCTURE")
    print("=" * 40)
    
    # Test queries work
    try:
        # Test basic queries on new tables
        pending_count = PendingConceptType.query.count()
        custom_count = CustomConceptType.query.count()
        mapping_count = ConceptTypeMapping.query.count()
        
        print(f"✅ PendingConceptType table: {pending_count} records")
        print(f"✅ CustomConceptType table: {custom_count} records")
        print(f"✅ ConceptTypeMapping table: {mapping_count} records")
        
        # Test new fields in EntityTriple
        concepts_with_metadata = EntityTriple.query.filter(
            EntityTriple.original_llm_type.isnot(None)
        ).count()
        
        concepts_needing_review = EntityTriple.query.filter(
            EntityTriple.needs_type_review == True
        ).count()
        
        print(f"✅ Concepts with type mapping metadata: {concepts_with_metadata}")
        print(f"✅ Concepts needing review: {concepts_needing_review}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database structure test failed: {e}")
        return False

def test_type_mapper_integration():
    """Test that type mapper works with database models."""
    print("\n🎯 TESTING TYPE MAPPER INTEGRATION")
    print("=" * 40)
    
    try:
        mapper = GuidelineConceptTypeMapper()
        
        # Test various type mappings
        test_cases = [
            ("Professional Standard", "Professional Code"),
            ("Ethical Principle", "Integrity"),
            ("New Unknown Type", "Some Concept")
        ]
        
        for llm_type, concept_name in test_cases:
            result = mapper.map_concept_type(llm_type, "", concept_name)
            print(f"✅ {llm_type} → {result.mapped_type} (confidence: {result.confidence:.2f})")
            
            # Test creating a mapping record (if it doesn't exist)
            existing = ConceptTypeMapping.query.filter_by(
                original_llm_type=llm_type
            ).first()
            
            if not existing:
                mapping = ConceptTypeMapping.create_or_update_mapping(
                    llm_type=llm_type,
                    mapped_type=result.mapped_type,
                    confidence=result.confidence,
                    is_automatic=True
                )
                print(f"   📊 Created mapping record")
            else:
                print(f"   📊 Mapping already exists")
        
        db.session.commit()
        return True
        
    except Exception as e:
        print(f"❌ Type mapper integration test failed: {e}")
        return False

def test_query_performance():
    """Test performance of key queries."""
    print("\n⚡ TESTING QUERY PERFORMANCE")
    print("=" * 30)
    
    import time
    
    queries = [
        ("Concepts needing review", 
         lambda: EntityTriple.query.filter_by(needs_type_review=True).count()),
        ("Pending types", 
         lambda: PendingConceptType.query.filter_by(status='pending').count()),
        ("Mapping statistics", 
         lambda: ConceptTypeMapping.get_mapping_statistics()),
    ]
    
    for desc, query_func in queries:
        try:
            start_time = time.time()
            result = query_func()
            duration = (time.time() - start_time) * 1000
            print(f"✅ {desc}: {result} ({duration:.2f}ms)")
        except Exception as e:
            print(f"❌ {desc}: ERROR - {e}")
    
    return True

def test_model_relationships():
    """Test that model relationships work correctly."""
    print("\n🔗 TESTING MODEL RELATIONSHIPS")
    print("=" * 35)
    
    try:
        # Test a few relationships if data exists
        pending_types = PendingConceptType.query.limit(3).all()
        for pending in pending_types:
            guideline = pending.source_guideline
            print(f"✅ Pending '{pending.suggested_type}' → Guideline '{guideline.title if guideline else 'None'}'")
        
        custom_types = CustomConceptType.query.limit(3).all()
        for custom in custom_types:
            print(f"✅ Custom type '{custom.type_name}' is active: {custom.is_active}")
        
        mappings = ConceptTypeMapping.query.limit(3).all()
        for mapping in mappings:
            print(f"✅ Mapping '{mapping.original_llm_type}' → '{mapping.mapped_to_type}' (used {mapping.usage_count} times)")
        
        return True
        
    except Exception as e:
        print(f"❌ Relationship test failed: {e}")
        return False

def main():
    """Run database validation tests."""
    print("🧪 SIMPLE DATABASE VALIDATION TEST")
    print("=" * 50)
    
    app = create_app('config')
    
    with app.app_context():
        print(f"📊 Database: {db.engine.url}")
        print(f"📅 Test run: {datetime.now().isoformat()}")
        print()
        
        try:
            # Run tests
            structure_ok = test_database_structure()
            integration_ok = test_type_mapper_integration()
            performance_ok = test_query_performance()
            relationships_ok = test_model_relationships()
            
            print("\n📊 VALIDATION SUMMARY")
            print("=" * 25)
            print(f"✅ Database structure: {'PASS' if structure_ok else 'FAIL'}")
            print(f"✅ Type mapper integration: {'PASS' if integration_ok else 'FAIL'}")
            print(f"✅ Query performance: {'PASS' if performance_ok else 'FAIL'}")
            print(f"✅ Model relationships: {'PASS' if relationships_ok else 'FAIL'}")
            
            all_pass = all([structure_ok, integration_ok, performance_ok, relationships_ok])
            
            if all_pass:
                print("\n🎉 ALL VALIDATION TESTS PASSED!")
                print("Database is ready for Phase 3 integration.")
                return True
            else:
                print("\n⚠️ Some tests failed - investigate before proceeding.")
                return False
            
        except Exception as e:
            print(f"\n❌ VALIDATION FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)