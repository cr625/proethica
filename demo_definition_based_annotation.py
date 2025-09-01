#!/usr/bin/env python3
"""
Demo script showing the definition-based annotation approach.

This demonstrates how the new approach:
1. Loads ontology definitions first
2. Asks LLM which definitions apply to text
3. Returns accurate, context-aware matches
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Sample NSPE Code text
SAMPLE_GUIDELINE = """
Professional engineers shall hold paramount the safety, health, and welfare of the public 
in the performance of their professional duties. Engineers shall perform services only 
in the areas of their competence and shall build their professional reputation on the 
merit of their services. Engineers shall continue their professional development throughout 
their careers and provide opportunities for the professional development of those engineers 
under their supervision.

Engineers shall act in professional matters for each employer or client as faithful agents 
or trustees, and shall avoid conflicts of interest. Engineers shall be guided in all their 
professional relations by the highest standards of integrity. Engineers shall issue public 
statements only in an objective and truthful manner.
"""


def main():
    print("=" * 70)
    print("DEFINITION-BASED ANNOTATION DEMO")
    print("=" * 70)
    print("\nThis demo shows the new, simpler approach where we:")
    print("1. Load ontology definitions first")
    print("2. Ask LLM which definitions apply to the text")
    print("3. Get accurate, context-aware matches\n")
    
    from app.services.definition_based_annotation_service import DefinitionBasedAnnotationService
    
    # Initialize service
    print("Initializing definition-based annotation service...")
    service = DefinitionBasedAnnotationService(batch_size=10)
    
    # Show sample text
    print("\nSample guideline text:")
    print("-" * 40)
    print(SAMPLE_GUIDELINE[:300] + "...")
    print("-" * 40)
    
    # Run annotation
    print("\n🔍 Running definition-based annotation...")
    print("(This loads ontology concepts and checks which apply to the text)\n")
    
    try:
        result = service.annotate_text(SAMPLE_GUIDELINE, world_id=1)
        
        # Display results
        print("\n✅ RESULTS:")
        print(f"- Concepts checked: {result.total_concepts_checked}")
        print(f"- Matches found: {len(result.matches)}")
        print(f"- Processing time: {result.processing_time_ms}ms")
        print(f"- Batch count: {result.batch_count}")
        
        if result.matches:
            print("\n📍 Sample Matches:")
            print("=" * 70)
            
            # Group by concept for display
            matches_by_concept = {}
            for match in result.matches:
                if match.concept_label not in matches_by_concept:
                    matches_by_concept[match.concept_label] = []
                matches_by_concept[match.concept_label].append(match)
            
            # Show first 3 concepts
            for i, (concept_label, concept_matches) in enumerate(list(matches_by_concept.items())[:3], 1):
                print(f"\n{i}. {concept_label}")
                print(f"   Ontology: {concept_matches[0].concept_ontology}")
                print(f"   Definition: {concept_matches[0].concept_definition[:100]}...")
                
                for match in concept_matches[:2]:  # Show up to 2 matches per concept
                    print(f"\n   Match:")
                    print(f"   • Text: \"{match.text_passage[:80]}...\"")
                    print(f"   • Reasoning: {match.reasoning}")
                    print(f"   • Confidence: {match.confidence:.2f}")
        
        if result.unmatched_concepts:
            print(f"\n📊 Unmatched concepts: {len(result.unmatched_concepts)}")
            print("   (These ontology concepts were checked but didn't match the text)")
        
        if result.errors:
            print(f"\n⚠️ Errors encountered:")
            for error in result.errors:
                print(f"   - {error}")
        
        # Show advantages
        print("\n" + "=" * 70)
        print("💡 ADVANTAGES OF THIS APPROACH:")
        print("- Knows what concepts exist in ontology from the start")
        print("- No guessing or extracting terms that don't exist")  
        print("- Provides clear reasoning for each match")
        print("- More accurate context-based matching")
        print("- Simpler implementation (no embeddings needed)")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("1. ANTHROPIC_API_KEY is set in environment")
        print("2. OntServe is running on port 5003")
        print("3. ProEthica database is accessible")
    
    print("\n" + "=" * 70)
    print("Demo complete!")


if __name__ == "__main__":
    main()
