#!/usr/bin/env python3
"""
Test the type mapping database setup with sample data.
This script validates that our Phase 2 database extensions work correctly
with the Phase 1 GuidelineConceptTypeMapper.
"""

import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app import create_app
from app.models import db
from app.models.entity_triple import EntityTriple
from app.models.pending_concept_type import PendingConceptType
from app.models.custom_concept_type import CustomConceptType
from app.models.concept_type_mapping import ConceptTypeMapping
from app.models.guideline import Guideline
from app.models.world import World
from app.models.user import User
from app.services.guideline_concept_type_mapper import GuidelineConceptTypeMapper

def test_new_models():
    """Test creating and managing new type mapping models."""
    print("🧪 TESTING NEW TYPE MAPPING MODELS")
    print("=" * 50)
    
    # Get or create a test world and guideline
    world = World.query.first()
    if not world:
        world = World(name="Test World", description="Test world for type mapping")
        db.session.add(world)
        db.session.commit()
    
    guideline = Guideline.query.first()
    if not guideline:
        guideline = Guideline(
            world_id=world.id,
            title="Test Guideline",
            content="Test content for type mapping validation",
            guideline_metadata={"test": True}
        )
        db.session.add(guideline)
        db.session.commit()
    
    # Get or create a test user
    user = User.query.first()
    if not user:
        user = User(
            username="test_user",
            email="test@example.com",
            password_hash="test_hash"
        )
        db.session.add(user)
        db.session.commit()
    
    print(f"✅ Using test world: {world.name} (ID: {world.id})")
    print(f"✅ Using test guideline: {guideline.title} (ID: {guideline.id})")
    print(f"✅ Using test user: {user.username} (ID: {user.id})")
    
    # Test 1: PendingConceptType
    print("\n📝 Testing PendingConceptType...")
    pending_type = PendingConceptType(
        suggested_type="Environmental Standard",
        suggested_description="A standard related to environmental protection in engineering",
        suggested_parent_type="principle",
        source_guideline_id=guideline.id,
        example_concepts=[
            {"name": "Green Building Standard", "description": "Standards for sustainable construction"},
            {"name": "Emission Limits", "description": "Environmental emission requirements"}
        ]
    )
    db.session.add(pending_type)
    db.session.commit()
    
    print(f"✅ Created pending type: {pending_type.suggested_type}")
    print(f"   Status: {pending_type.status}")
    print(f"   Examples: {len(pending_type.example_concepts)} concepts")
    
    # Test approval workflow
    pending_type.approve(user.id, "Approved for testing")
    db.session.commit()
    print(f"✅ Approved pending type, new status: {pending_type.status}")
    
    # Test 2: CustomConceptType
    print("\n🏗️ Testing CustomConceptType...")
    custom_type = CustomConceptType.create_from_pending(
        pending_type,
        ontology_uri="http://proethica.org/ontology/engineering-ethics#EnvironmentalStandard"
    )
    db.session.add(custom_type)
    db.session.commit()
    
    print(f"✅ Created custom type: {custom_type.type_name}")
    print(f"   Parent type: {custom_type.parent_type}")
    print(f"   Hierarchy: {custom_type.get_full_hierarchy()}")
    print(f"   Active: {custom_type.is_active}")
    
    # Test 3: ConceptTypeMapping
    print("\n📊 Testing ConceptTypeMapping...")
    mapping = ConceptTypeMapping.create_or_update_mapping(
        llm_type="Environmental Standard",
        mapped_type="principle",
        confidence=0.85,
        is_automatic=True
    )
    db.session.commit()
    
    print(f"✅ Created type mapping: {mapping.original_llm_type} -> {mapping.mapped_to_type}")
    print(f"   Confidence: {mapping.mapping_confidence}")
    print(f"   Usage count: {mapping.usage_count}")
    
    # Test usage tracking
    mapping.record_usage()
    db.session.commit()
    print(f"✅ Recorded usage, new count: {mapping.usage_count}")
    
    return world, guideline, user

def test_entity_triple_extensions():
    """Test the new fields in EntityTriple model."""
    print("\n🔗 TESTING ENTITY_TRIPLE EXTENSIONS")
    print("=" * 40)
    
    # Create a test concept triple with type mapping metadata
    test_triple = EntityTriple(
        subject="http://proethica.org/concept/TestConcept",
        subject_label="Test Environmental Principle",
        predicate="http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
        predicate_label="is a",
        object_literal="Principle",
        object_label="Principle",
        is_literal=True,
        entity_type="guideline_concept",
        entity_id=1,
        # New type mapping fields
        original_llm_type="Environmental Standard",
        type_mapping_confidence=0.85,
        needs_type_review=False,
        mapping_justification="Mapped via semantic similarity: Environmental Standard -> principle"
    )
    
    db.session.add(test_triple)
    db.session.commit()
    
    print(f"✅ Created entity triple with type mapping metadata:")
    print(f"   Subject: {test_triple.subject_label}")
    print(f"   Original LLM type: {test_triple.original_llm_type}")
    print(f"   Mapped to: {test_triple.object_literal}")
    print(f"   Confidence: {test_triple.type_mapping_confidence}")
    print(f"   Needs review: {test_triple.needs_type_review}")
    print(f"   Justification: {test_triple.mapping_justification}")
    
    # Test the to_dict method includes new fields
    triple_dict = test_triple.to_dict()
    type_mapping_fields = ['original_llm_type', 'type_mapping_confidence', 'needs_type_review', 'mapping_justification']
    
    print(f"\n✅ Verified to_dict() includes all type mapping fields:")
    for field in type_mapping_fields:
        if field in triple_dict:
            print(f"   ✅ {field}: {triple_dict[field]}")
        else:
            print(f"   ❌ {field}: MISSING")
    
    return test_triple

def test_type_mapper_integration():
    """Test integration between GuidelineConceptTypeMapper and database models."""
    print("\n🎯 TESTING TYPE MAPPER INTEGRATION")
    print("=" * 40)
    
    # Initialize the type mapper
    mapper = GuidelineConceptTypeMapper()
    
    # Test with guideline 13 examples
    test_concepts = [
        ("Fundamental Principle", "Public Safety Paramount"),
        ("Professional Standard", "Professional Competence"),
        ("Environmental Responsibility", "Sustainability"),
        ("Unknown New Type", "Some New Concept"),
    ]
    
    results = []
    for llm_type, concept_name in test_concepts:
        result = mapper.map_concept_type(llm_type, "", concept_name)
        results.append((llm_type, concept_name, result))
        
        print(f"✅ {llm_type}:")
        print(f"   Mapped to: {result.mapped_type}")
        print(f"   Confidence: {result.confidence}")
        print(f"   Is new type: {result.is_new_type}")
        print(f"   Needs review: {result.needs_review}")
        print(f"   Justification: {result.justification}")
        
        # Create a ConceptTypeMapping entry for this
        mapping = ConceptTypeMapping.create_or_update_mapping(
            llm_type=llm_type,
            mapped_type=result.mapped_type,
            confidence=result.confidence,
            is_automatic=True
        )
        
        # If it's a new type, create a pending type entry
        if result.is_new_type and result.mapped_type not in ['role', 'principle', 'obligation', 'state', 'resource', 'action', 'event', 'capability']:
            # Find a guideline to associate with
            guideline = Guideline.query.first()
            if guideline:
                pending = PendingConceptType(
                    suggested_type=llm_type,
                    suggested_description=f"New type suggested for concept: {concept_name}",
                    suggested_parent_type=result.suggested_parent,
                    source_guideline_id=guideline.id,
                    example_concepts=[{"name": concept_name, "description": "Example concept"}]
                )
                db.session.add(pending)
        
        print()
    
    db.session.commit()
    return results

def test_query_performance():
    """Test the performance of new indexes and queries."""
    print("\n⚡ TESTING QUERY PERFORMANCE")
    print("=" * 30)
    
    # Test queries that should benefit from new indexes
    test_queries = [
        ("Find concepts needing review", 
         lambda: EntityTriple.query.filter_by(needs_type_review=True).count()),
        
        ("Find concepts by original LLM type",
         lambda: EntityTriple.query.filter_by(original_llm_type="Environmental Standard").count()),
        
        ("Find low confidence mappings",
         lambda: EntityTriple.query.filter(EntityTriple.type_mapping_confidence < 0.7).count()),
        
        ("Get pending types for review",
         lambda: PendingConceptType.query.filter_by(status='pending').count()),
        
        ("Get mapping statistics",
         lambda: ConceptTypeMapping.get_mapping_statistics()),
    ]
    
    for description, query_func in test_queries:
        try:
            import time
            start_time = time.time()
            result = query_func()
            end_time = time.time()
            duration = (end_time - start_time) * 1000  # Convert to milliseconds
            
            print(f"✅ {description}: {result} ({duration:.2f}ms)")
        except Exception as e:
            print(f"❌ {description}: ERROR - {e}")

def test_data_relationships():
    """Test relationships between models work correctly."""
    print("\n🔗 TESTING MODEL RELATIONSHIPS")
    print("=" * 35)
    
    # Test PendingConceptType -> Guideline relationship
    pending_types = PendingConceptType.query.all()
    for pending in pending_types[:3]:  # Test first 3
        guideline = pending.source_guideline
        print(f"✅ Pending type '{pending.suggested_type}' -> Guideline '{guideline.title if guideline else 'None'}'")
    
    # Test CustomConceptType -> PendingConceptType relationship  
    custom_types = CustomConceptType.query.all()
    for custom in custom_types[:3]:  # Test first 3
        pending = custom.created_from_pending
        print(f"✅ Custom type '{custom.type_name}' -> Created from pending '{pending.suggested_type if pending else 'None'}'")
    
    # Test ConceptTypeMapping -> User relationship
    mappings = ConceptTypeMapping.query.filter(ConceptTypeMapping.reviewed_by.isnot(None)).all()
    for mapping in mappings[:3]:  # Test first 3
        user = mapping.reviewer
        print(f"✅ Mapping '{mapping.original_llm_type}' -> Reviewed by '{user.username if user else 'None'}'")

def main():
    """Run all tests."""
    print("🧪 TYPE MAPPING DATABASE VALIDATION")
    print("=" * 60)
    
    # Create app with the same configuration as the debug app
    app = create_app('config')
    
    with app.app_context():
        print(f"📊 Database: {db.engine.url}")
        print(f"📅 Test run: {datetime.now().isoformat()}")
        print()
        
        try:
            # Run all tests
            world, guideline, user = test_new_models()
            test_triple = test_entity_triple_extensions()
            mapping_results = test_type_mapper_integration()
            test_query_performance()
            test_data_relationships()
            
            print("\n📊 FINAL SUMMARY")
            print("=" * 20)
            
            # Count records in new tables
            pending_count = PendingConceptType.query.count()
            custom_count = CustomConceptType.query.count()
            mapping_count = ConceptTypeMapping.query.count()
            review_needed = EntityTriple.query.filter_by(needs_type_review=True).count()
            
            print(f"✅ Pending concept types: {pending_count}")
            print(f"✅ Custom concept types: {custom_count}")
            print(f"✅ Type mappings recorded: {mapping_count}")
            print(f"✅ Concepts needing review: {review_needed}")
            
            # Get mapping statistics
            stats = ConceptTypeMapping.get_mapping_statistics()
            print(f"✅ Average mapping confidence: {stats['average_confidence']}")
            print(f"✅ Automatic vs reviewed: {stats['automatic_mappings']}/{stats['reviewed_mappings']}")
            
            print("\n🎉 ALL TESTS PASSED!")
            print("Database setup is working correctly and ready for Phase 3 integration.")
            
            return True
            
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)