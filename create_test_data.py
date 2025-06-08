#!/usr/bin/env python3
"""
Create test data to simulate the 'State' over-assignment problem
so we can demonstrate how our type mapper fixes it.
"""

import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.models import db
from app.models.entity_triple import EntityTriple
from app.models.guideline import Guideline
from app.models.world import World

def create_test_concepts():
    """Create test concept triples that simulate the 'State' over-assignment problem."""
    print("🏗️ CREATING TEST DATA TO SIMULATE 'STATE' OVER-ASSIGNMENT")
    print("=" * 60)
    
    # Get or create test world and guideline
    world = World.query.first()
    if not world:
        world = World(name="Test Engineering World", description="Test world for demonstrating type mapping")
        db.session.add(world)
        db.session.commit()
    
    guideline = Guideline.query.first()
    if not guideline:
        guideline = Guideline(
            world_id=world.id,
            title="Test Ethics Guidelines",
            content="Test ethical guidelines for engineering practice",
            guideline_metadata={"test_data": True}
        )
        db.session.add(guideline)
        db.session.commit()
    
    print(f"✅ Using world: {world.name} (ID: {world.id})")
    print(f"✅ Using guideline: {guideline.title} (ID: {guideline.id})")
    
    # Create test concepts based on real examples from guideline 13
    # These represent what the LLM SHOULD have suggested vs what was forced to "State"
    test_concepts = [
        # (concept_name, original_llm_type, description, forced_to_state)
        ("Public Safety Paramount", "Fundamental Principle", "The overriding principle that engineers must prioritize the safety, health, and welfare of the public above all other considerations", True),
        ("Professional Competence", "Professional Standard", "The requirement that engineers only perform work within their areas of expertise and qualification", True),
        ("Honesty and Integrity", "Core Value", "The fundamental ethical requirement for truthfulness, transparency, and moral uprightness in all professional activities", True),
        ("Confidentiality", "Professional Duty", "The obligation to protect client and employer information from unauthorized disclosure", False),  # This one might be correct
        ("Conflict of Interest", "Ethical Risk", "Situations where personal, financial, or other interests may compromise professional judgment or loyalty", True),
        ("Professional Responsibility", "Professional Obligation", "The comprehensive duty to uphold professional standards and serve the broader interests of society", False),  # This one might be correct
        ("Truthful Communication", "Communication Standard", "The requirement to provide accurate, complete, and objective information in all professional communications", True),
        ("Faithful Agency", "Professional Relationship", "The duty to act loyally and in the best interests of employers and clients while maintaining professional independence", True),
        ("Deception Avoidance", "Ethical Prohibition", "The prohibition against misleading, fraudulent, or dishonest practices in professional activities", True),
        ("Public Interest Service", "Social Responsibility", "The commitment to serve broader societal needs and promote public understanding of engineering", True),
        ("Sustainability", "Environmental Responsibility", "The responsibility to consider long-term environmental and social impacts in engineering practice", True),
        ("Professional Development", "Professional Growth", "The ongoing obligation to maintain and improve professional knowledge and skills", True),
        ("Fair Treatment", "Social Justice", "The requirement to treat all individuals with fairness, respect, and without discrimination", True),
        ("Professional Recognition", "Professional Courtesy", "The duty to properly acknowledge the contributions and work of others in professional contexts", True),
        ("Legal Compliance", "Legal Obligation", "The obligation to follow applicable laws, regulations, and professional standards", False),  # This one might be correct
    ]
    
    print(f"\n📝 Creating {len(test_concepts)} test concept triples...")
    
    created_triples = []
    
    for i, (concept_name, original_llm_type, description, forced_to_state) in enumerate(test_concepts):
        # Create the concept URI
        concept_uri = f"http://proethica.org/test/concept/{concept_name.replace(' ', '')}"
        
        # Create type triple (this simulates the problem - everything forced to "State")
        type_triple = EntityTriple(
            subject=concept_uri,
            subject_label=concept_name,
            predicate="http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
            predicate_label="is a",
            object_literal="State" if forced_to_state else "Obligation",  # Simulate the forced assignment
            object_label="State" if forced_to_state else "Obligation",
            is_literal=True,
            entity_type="guideline_concept",
            entity_id=guideline.id,
            world_id=world.id,
            guideline_id=guideline.id,
            # Simulate that these were processed by old system (no type mapping metadata)
            original_llm_type=None,  # Old system didn't preserve this
            type_mapping_confidence=None,
            needs_type_review=None,
            mapping_justification=None
        )
        
        # Create label triple
        label_triple = EntityTriple(
            subject=concept_uri,
            subject_label=concept_name,
            predicate="http://www.w3.org/2000/01/rdf-schema#label",
            predicate_label="label",
            object_literal=concept_name,
            object_label=concept_name,
            is_literal=True,
            entity_type="guideline_concept",
            entity_id=guideline.id,
            world_id=world.id,
            guideline_id=guideline.id
        )
        
        # Create description triple
        desc_triple = EntityTriple(
            subject=concept_uri,
            subject_label=concept_name,
            predicate="http://purl.org/dc/elements/1.1/description",
            predicate_label="has description",
            object_literal=description,
            object_label=None,
            is_literal=True,
            entity_type="guideline_concept",
            entity_id=guideline.id,
            world_id=world.id,
            guideline_id=guideline.id
        )
        
        db.session.add(type_triple)
        db.session.add(label_triple)
        db.session.add(desc_triple)
        
        created_triples.extend([type_triple, label_triple, desc_triple])
        
        status = "🔴 FORCED TO STATE" if forced_to_state else "✅ Correctly typed"
        print(f"  {i+1:2d}. {concept_name} - {status}")
        print(f"      Original LLM suggestion: {original_llm_type}")
        print(f"      Forced to: {'State' if forced_to_state else 'Obligation'}")
    
    db.session.commit()
    
    forced_count = sum(1 for _, _, _, forced in test_concepts if forced)
    correct_count = len(test_concepts) - forced_count
    
    print(f"\n📊 Created {len(created_triples)} triples for {len(test_concepts)} concepts")
    print(f"🔴 Forced to 'State': {forced_count} concepts ({forced_count/len(test_concepts)*100:.1f}%)")
    print(f"✅ Correctly typed: {correct_count} concepts")
    
    return created_triples, test_concepts

def main():
    """Create test data and show the problem we're solving."""
    print("🧪 CREATING TEST DATA FOR TYPE MAPPING VALIDATION")
    print("=" * 70)
    
    app = create_app('config')
    
    with app.app_context():
        print(f"📊 Database: {db.engine.url}")
        print()
        
        # Check if test data already exists
        existing_test_concepts = EntityTriple.query.filter(
            EntityTriple.entity_type == 'guideline_concept',
            EntityTriple.subject_label.like('%Test%')
        ).count()
        
        if existing_test_concepts > 0:
            print(f"ℹ️  Found {existing_test_concepts} existing test concepts - creating additional test data")
        
        try:
            created_triples, test_concepts = create_test_concepts()
            
            print("\n🎯 DEMONSTRATING THE PROBLEM")
            print("=" * 30)
            
            # Show current state of assignments
            state_count = EntityTriple.query.filter(
                EntityTriple.entity_type == 'guideline_concept',
                EntityTriple.predicate == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type',
                EntityTriple.object_literal == 'State'
            ).count()
            
            total_concepts = EntityTriple.query.filter(
                EntityTriple.entity_type == 'guideline_concept',
                EntityTriple.predicate == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
            ).count()
            
            if total_concepts > 0:
                state_percentage = state_count / total_concepts * 100
                print(f"📊 Current database state:")
                print(f"   Total concepts: {total_concepts}")
                print(f"   Assigned to 'State': {state_count} ({state_percentage:.1f}%)")
                print(f"   🔴 PROBLEM: {state_percentage:.1f}% over-assignment to 'State'!")
            
            print("\n✅ Test data created successfully!")
            print("Now you can run the migration test to see how our type mapper fixes this.")
            print("\nRun: python test_existing_data_migration.py")
            
            return True
            
        except Exception as e:
            print(f"\n❌ TEST DATA CREATION FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)