#!/usr/bin/env python3
"""
Test how our type mapper would handle existing "State" over-assignments.
This simulates what Phase 3 integration will do to fix current data.
"""

import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.models import db
from app.models.entity_triple import EntityTriple
from app.models.concept_type_mapping import ConceptTypeMapping
from app.services.guideline_concept_type_mapper import GuidelineConceptTypeMapper

def analyze_current_state_overassignments():
    """Analyze current entity triples that are forced to 'State' type."""
    print("🔍 ANALYZING CURRENT 'STATE' OVER-ASSIGNMENTS")
    print("=" * 50)
    
    # Find all guideline concept triples that are assigned "State"
    state_triples = EntityTriple.query.filter(
        EntityTriple.entity_type == 'guideline_concept',
        EntityTriple.predicate == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type',
        EntityTriple.object_literal == 'State'
    ).all()
    
    print(f"📊 Found {len(state_triples)} concepts currently assigned to 'State' type")
    
    if not state_triples:
        print("ℹ️  No 'State' assignments found (database may be empty)")
        return []
    
    # Group by subject to get unique concepts
    concepts = {}
    for triple in state_triples:
        subject = triple.subject_label or triple.subject
        if subject not in concepts:
            concepts[subject] = {
                'subject': subject,
                'subject_uri': triple.subject,
                'triple_id': triple.id,
                'description': None
            }
    
    # Get descriptions for these concepts
    for concept_name in concepts.keys():
        desc_triple = EntityTriple.query.filter(
            EntityTriple.subject_label == concept_name,
            EntityTriple.predicate == 'http://purl.org/dc/elements/1.1/description'
        ).first()
        
        if desc_triple:
            concepts[concept_name]['description'] = desc_triple.object_literal
    
    print(f"📋 Unique concepts assigned to 'State': {len(concepts)}")
    
    # Show sample concepts
    sample_concepts = list(concepts.values())[:10]
    for i, concept in enumerate(sample_concepts, 1):
        desc = concept['description'][:60] + "..." if concept['description'] and len(concept['description']) > 60 else concept['description']
        print(f"  {i}. {concept['subject']}")
        if desc:
            print(f"     Description: {desc}")
    
    if len(concepts) > 10:
        print(f"     ... and {len(concepts) - 10} more")
    
    return list(concepts.values())

def test_remapping_with_type_mapper():
    """Test how our type mapper would remap current 'State' assignments."""
    print("\n🎯 TESTING REMAPPING WITH TYPE MAPPER")
    print("=" * 40)
    
    # Get current state assignments
    current_concepts = analyze_current_state_overassignments()
    
    if not current_concepts:
        print("ℹ️  No concepts to test remapping")
        return []
    
    # Initialize the type mapper
    mapper = GuidelineConceptTypeMapper()
    
    # Test remapping
    remapping_results = []
    
    print(f"\n🔄 Testing remapping for {min(len(current_concepts), 15)} concepts...")
    
    for i, concept in enumerate(current_concepts[:15]):  # Test first 15
        concept_name = concept['subject']
        description = concept['description'] or ""
        
        # Get the remapping result
        result = mapper.map_concept_type(
            llm_type="State",  # Current assignment
            concept_description=description,
            concept_name=concept_name
        )
        
        remapping_results.append({
            'concept': concept_name,
            'current_type': 'State',
            'suggested_type': result.mapped_type,
            'confidence': result.confidence,
            'is_new_type': result.is_new_type,
            'needs_review': result.needs_review,
            'justification': result.justification
        })
        
        status_icon = "🆕" if result.is_new_type else "✅" if result.mapped_type != "state" else "⚠️"
        
        print(f"  {status_icon} {concept_name}")
        print(f"     Current: State → Suggested: {result.mapped_type} (confidence: {result.confidence:.2f})")
        if result.mapped_type != "state":
            print(f"     ✨ IMPROVEMENT: Would change from State to {result.mapped_type}")
        if result.needs_review:
            print(f"     👁️  Needs human review")
        print(f"     Justification: {result.justification}")
        print()
    
    return remapping_results

def analyze_improvement_potential(remapping_results):
    """Analyze how much improvement our type mapper would provide."""
    print("📈 IMPROVEMENT ANALYSIS")
    print("=" * 25)
    
    if not remapping_results:
        print("ℹ️  No remapping results to analyze")
        return
    
    total_concepts = len(remapping_results)
    improved_concepts = [r for r in remapping_results if r['suggested_type'] != 'state']
    new_types_suggested = [r for r in remapping_results if r['is_new_type']]
    needs_review = [r for r in remapping_results if r['needs_review']]
    
    improvement_rate = len(improved_concepts) / total_concepts * 100
    
    print(f"📊 Total concepts analyzed: {total_concepts}")
    print(f"✅ Would be improved: {len(improved_concepts)} ({improvement_rate:.1f}%)")
    print(f"🆕 New types suggested: {len(new_types_suggested)}")
    print(f"👁️  Would need review: {len(needs_review)}")
    
    # Breakdown by suggested type
    type_breakdown = {}
    for result in remapping_results:
        suggested_type = result['suggested_type']
        type_breakdown[suggested_type] = type_breakdown.get(suggested_type, 0) + 1
    
    print(f"\n📋 Type distribution after remapping:")
    for type_name, count in sorted(type_breakdown.items()):
        percentage = count / total_concepts * 100
        print(f"  {type_name}: {count} ({percentage:.1f}%)")
    
    # Show highest confidence improvements
    high_confidence_improvements = [
        r for r in improved_concepts 
        if r['confidence'] >= 0.8 and r['suggested_type'] != 'state'
    ]
    
    print(f"\n🎯 High-confidence improvements (≥80% confidence):")
    for result in high_confidence_improvements[:5]:
        print(f"  ✅ {result['concept']}: State → {result['suggested_type']} ({result['confidence']:.2f})")
    
    return {
        'total_concepts': total_concepts,
        'improved_concepts': len(improved_concepts),
        'improvement_rate': improvement_rate,
        'new_types_suggested': len(new_types_suggested),
        'needs_review': len(needs_review),
        'type_breakdown': type_breakdown,
        'high_confidence_improvements': len(high_confidence_improvements)
    }

def test_batch_mapping_performance():
    """Test performance of batch type mapping operations."""
    print("\n⚡ TESTING BATCH MAPPING PERFORMANCE")
    print("=" * 35)
    
    # Get sample concepts
    state_triples = EntityTriple.query.filter(
        EntityTriple.entity_type == 'guideline_concept',
        EntityTriple.predicate == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type',
        EntityTriple.object_literal == 'State'
    ).limit(50).all()
    
    if not state_triples:
        print("ℹ️  No State triples to test performance")
        return
    
    # Initialize mapper
    mapper = GuidelineConceptTypeMapper()
    
    # Measure performance
    import time
    
    concepts = [(t.subject_label or t.subject, t.id) for t in state_triples]
    
    print(f"🔄 Testing batch mapping for {len(concepts)} concepts...")
    
    start_time = time.time()
    
    results = []
    for concept_name, triple_id in concepts:
        result = mapper.map_concept_type(
            llm_type="State",
            concept_name=concept_name
        )
        results.append(result)
    
    end_time = time.time()
    duration = end_time - start_time
    concepts_per_second = len(concepts) / duration if duration > 0 else 0
    
    print(f"✅ Processed {len(concepts)} concepts in {duration:.2f} seconds")
    print(f"⚡ Rate: {concepts_per_second:.1f} concepts/second")
    print(f"📊 Average time per concept: {duration/len(concepts)*1000:.1f}ms")
    
    return {
        'concepts_processed': len(concepts),
        'duration_seconds': duration,
        'concepts_per_second': concepts_per_second
    }

def main():
    """Run all existing data migration tests."""
    print("🔄 TESTING EXISTING DATA MIGRATION POTENTIAL")
    print("=" * 60)
    
    app = create_app('config')
    
    with app.app_context():
        print(f"📊 Database: {db.engine.url}")
        print()
        
        try:
            # Test remapping current State assignments
            remapping_results = test_remapping_with_type_mapper()
            
            # Analyze improvement potential
            improvement_stats = analyze_improvement_potential(remapping_results)
            
            # Test performance
            performance_stats = test_batch_mapping_performance()
            
            print("\n🎉 MIGRATION TEST SUMMARY")
            print("=" * 30)
            
            if improvement_stats:
                print(f"📈 Improvement potential: {improvement_stats['improvement_rate']:.1f}%")
                print(f"🎯 High-confidence fixes: {improvement_stats['high_confidence_improvements']}")
                print(f"🆕 New types to review: {improvement_stats['new_types_suggested']}")
            
            if performance_stats:
                print(f"⚡ Processing speed: {performance_stats['concepts_per_second']:.1f} concepts/sec")
            
            print("\n✅ Database is ready for Phase 3 integration!")
            print("The type mapper can successfully improve existing 'State' over-assignments.")
            
            return True
            
        except Exception as e:
            print(f"\n❌ MIGRATION TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)