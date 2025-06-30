#!/usr/bin/env python3
"""
Test concept remapping using concept names and descriptions,
simulating what Phase 3 integration will actually do.
"""

import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.models import db
from app.models.entity_triple import EntityTriple
from app.services.guideline_concept_type_mapper import GuidelineConceptTypeMapper

def test_concept_remapping():
    """Test remapping concepts using their names and descriptions."""
    print("🎯 TESTING CONCEPT REMAPPING USING NAMES AND DESCRIPTIONS")
    print("=" * 60)
    
    # Get concepts that are currently assigned to 'State'
    state_concepts = db.session.query(
        EntityTriple.subject_label,
        EntityTriple.subject
    ).filter(
        EntityTriple.entity_type == 'guideline_concept',
        EntityTriple.predicate == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type',
        EntityTriple.object_literal == 'State'
    ).distinct().all()
    
    if not state_concepts:
        print("ℹ️  No 'State' concepts found to test")
        return []
    
    print(f"📊 Found {len(state_concepts)} concepts currently assigned to 'State'")
    
    # Get descriptions for these concepts
    concept_data = []
    for subject_label, subject_uri in state_concepts:
        # Get description
        desc_triple = EntityTriple.query.filter(
            EntityTriple.subject == subject_uri,
            EntityTriple.predicate == 'http://purl.org/dc/elements/1.1/description'
        ).first()
        
        description = desc_triple.object_literal if desc_triple else ""
        
        concept_data.append({
            'name': subject_label,
            'uri': subject_uri,
            'description': description
        })
    
    # Initialize type mapper
    mapper = GuidelineConceptTypeMapper()
    
    print(f"\n🔄 Testing remapping based on concept names and descriptions...")
    
    remapping_results = []
    
    for concept in concept_data:
        # Test what the type mapper suggests based on concept name and description
        # This simulates what we'd do during Phase 3 integration
        result = mapper.map_concept_type(
            llm_type="unknown",  # We don't have the original LLM type
            concept_description=concept['description'],
            concept_name=concept['name']
        )
        
        remapping_results.append({
            'concept': concept['name'],
            'current_type': 'State',
            'suggested_type': result.mapped_type,
            'confidence': result.confidence,
            'is_new_type': result.is_new_type,
            'needs_review': result.needs_review,
            'justification': result.justification,
            'description': concept['description'][:100] + "..." if len(concept['description']) > 100 else concept['description']
        })
        
        status_icon = "🆕" if result.is_new_type else "✅" if result.mapped_type != "state" else "⚠️"
        
        print(f"  {status_icon} {concept['name']}")
        print(f"     Current: State → Suggested: {result.mapped_type} (confidence: {result.confidence:.2f})")
        if result.mapped_type != "state":
            print(f"     ✨ IMPROVEMENT: Would change from State to {result.mapped_type}")
        if result.needs_review:
            print(f"     👁️  Needs human review")
        print(f"     Justification: {result.justification}")
        if concept['description']:
            desc_short = concept['description'][:80] + "..." if len(concept['description']) > 80 else concept['description']
            print(f"     Description: {desc_short}")
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
    for result in high_confidence_improvements:
        print(f"  ✅ {result['concept']}: State → {result['suggested_type']} ({result['confidence']:.2f})")
    
    # Show concepts that would need review
    if needs_review:
        print(f"\n👁️  Concepts needing human review:")
        for result in needs_review[:5]:  # Show first 5
            print(f"  🔍 {result['concept']}: {result['justification']}")
    
    return {
        'total_concepts': total_concepts,
        'improved_concepts': len(improved_concepts),
        'improvement_rate': improvement_rate,
        'new_types_suggested': len(new_types_suggested),
        'needs_review': len(needs_review),
        'type_breakdown': type_breakdown,
        'high_confidence_improvements': len(high_confidence_improvements)
    }

def show_specific_examples():
    """Show specific examples of how concepts would be remapped."""
    print("\n🔍 DETAILED EXAMPLES OF REMAPPING")
    print("=" * 35)
    
    # Test specific examples we know should be improved
    mapper = GuidelineConceptTypeMapper()
    
    test_examples = [
        ("Public Safety Paramount", "The overriding principle that engineers must prioritize the safety, health, and welfare of the public above all other considerations"),
        ("Professional Competence", "The requirement that engineers only perform work within their areas of expertise and qualification"),
        ("Honesty and Integrity", "The fundamental ethical requirement for truthfulness, transparency, and moral uprightness in all professional activities"),
        ("Sustainability", "The responsibility to consider long-term environmental and social impacts in engineering practice"),
    ]
    
    for name, description in test_examples:
        result = mapper.map_concept_type("unknown", description, name)
        
        print(f"📝 {name}")
        print(f"   Description: {description}")
        print(f"   Current assignment: State")
        print(f"   Type mapper suggests: {result.mapped_type} (confidence: {result.confidence:.2f})")
        print(f"   Justification: {result.justification}")
        
        if result.mapped_type != "state":
            print(f"   ✨ IMPROVEMENT: State → {result.mapped_type}")
        else:
            print(f"   ⚠️  No improvement detected")
        print()

def main():
    """Run concept remapping tests."""
    print("🧪 TESTING CONCEPT REMAPPING WITH ACTUAL NAMES/DESCRIPTIONS")
    print("=" * 70)
    
    app = create_app('config')
    
    with app.app_context():
        print(f"📊 Database: {db.engine.url}")
        print()
        
        try:
            # Test remapping using concept names and descriptions
            remapping_results = test_concept_remapping()
            
            # Analyze improvement potential
            improvement_stats = analyze_improvement_potential(remapping_results)
            
            # Show detailed examples
            show_specific_examples()
            
            print("\n🎉 CONCEPT REMAPPING TEST SUMMARY")
            print("=" * 40)
            
            if improvement_stats:
                print(f"📈 Improvement potential: {improvement_stats['improvement_rate']:.1f}%")
                print(f"🎯 High-confidence fixes: {improvement_stats['high_confidence_improvements']}")
                print(f"🆕 New types to review: {improvement_stats['new_types_suggested']}")
                
                if improvement_stats['improvement_rate'] > 0:
                    print("\n✅ Type mapper successfully identifies improvements!")
                    print("Ready for Phase 3 integration to fix State over-assignments.")
                else:
                    print("\n⚠️  Type mapper needs tuning - not detecting expected improvements")
            
            return True
            
        except Exception as e:
            print(f"\n❌ CONCEPT REMAPPING TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)