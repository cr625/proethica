#!/usr/bin/env python3
"""
Debug script for LLM-Enhanced Annotation System
"""

import sys
import os
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(Path(__file__).parent)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_ontology_loading():
    """Test that ontology concepts are being loaded properly."""
    print("\n" + "="*60)
    print("Testing Ontology Loading")
    print("="*60)
    
    from app.services.ontserve_annotation_service import OntServeAnnotationService
    
    service = OntServeAnnotationService()
    
    # Test world ontology mapping
    world_id = 1
    mapping = service.get_world_ontology_mapping(world_id)
    print(f"World {world_id} ontology mapping: {mapping}")
    
    # Test loading concepts
    target_ontologies = ['proethica-intermediate', 'engineering-ethics', 'proethica-core']
    print(f"\nTarget ontologies: {target_ontologies}")
    
    all_concepts = service.get_ontology_concepts(target_ontologies)
    
    for ontology_name, concepts in all_concepts.items():
        print(f"\n{ontology_name}: {len(concepts)} concepts")
        # Show first 3 concepts
        for i, concept in enumerate(concepts[:3]):
            print(f"  - {concept.get('label', 'No label')}: {concept.get('definition', 'No definition')[:50] if concept.get('definition') else 'No definition'}...")
    
    # Count concepts with definitions
    total_concepts = 0
    concepts_with_definitions = 0
    for ontology_name, concepts in all_concepts.items():
        for concept in concepts:
            total_concepts += 1
            if concept.get('definition', '').strip():
                concepts_with_definitions += 1
    
    print(f"\nTotal concepts: {total_concepts}")
    print(f"Concepts with definitions: {concepts_with_definitions}")
    print(f"Percentage with definitions: {concepts_with_definitions/total_concepts*100:.1f}%")
    
    return all_concepts

def test_llm_extraction():
    """Test LLM term extraction."""
    print("\n" + "="*60)
    print("Testing LLM Term Extraction")
    print("="*60)
    
    from app.services.llm_enhanced_annotation_service import LLMEnhancedAnnotationService
    
    service = LLMEnhancedAnnotationService()
    
    # Sample text
    text = """
    Engineers shall hold paramount the safety, health, and welfare of the public.
    Engineers shall perform services only in areas of their competence.
    Engineers shall issue public statements only in an objective and truthful manner.
    Engineers shall act for each employer or client as faithful agents or trustees.
    """
    
    print(f"Test text: {text[:200]}...")
    
    # Test extraction
    extracted_terms = service._extract_key_terms(text)
    
    print(f"\nExtracted {len(extracted_terms)} terms:")
    for term in extracted_terms[:5]:
        print(f"  - '{term.term}' (type: {term.term_type}, importance: {term.importance_score:.2f})")
    
    return extracted_terms

def test_semantic_matching(extracted_terms, concepts):
    """Test semantic matching between terms and concepts."""
    print("\n" + "="*60)
    print("Testing Semantic Matching")
    print("="*60)
    
    from app.services.llm_enhanced_annotation_service import LLMEnhancedAnnotationService
    
    service = LLMEnhancedAnnotationService()
    
    # Flatten concepts
    flattened_concepts = []
    for ontology_name, onto_concepts in concepts.items():
        for concept in onto_concepts:
            concept['source_ontology'] = ontology_name
            flattened_concepts.append(concept)
    
    print(f"Testing matching with {len(flattened_concepts)} total concepts")
    
    # Test matching for first few terms
    matches_found = 0
    for term in extracted_terms[:3]:
        print(f"\nTrying to match term: '{term.term}'")
        match = service._find_semantic_match(term, flattened_concepts)
        if match:
            matches_found += 1
            print(f"  ✅ MATCH FOUND: {match.concept_label} (score: {match.similarity_score:.2f})")
            print(f"     Reasoning: {match.reasoning}")
        else:
            print(f"  ❌ No match found")
    
    print(f"\nMatches found: {matches_found}/{min(3, len(extracted_terms))}")
    return matches_found

def test_full_annotation():
    """Test the full annotation pipeline."""
    print("\n" + "="*60)
    print("Testing Full Annotation Pipeline")
    print("="*60)
    
    from app.services.llm_enhanced_annotation_service import LLMEnhancedAnnotationService
    
    service = LLMEnhancedAnnotationService()
    
    # Sample text
    text = """
    Engineers shall hold paramount the safety, health, and welfare of the public.
    Engineers shall perform services only in areas of their competence.
    """
    
    print(f"Annotating text: {text[:100]}...")
    
    # Run full annotation
    result = service.annotate_text(text, world_id=1)
    
    print(f"\nResults:")
    print(f"  Terms extracted: {result.total_terms_extracted}")
    print(f"  Successful matches: {result.successful_matches}")
    print(f"  Failed matches: {result.failed_matches}")
    print(f"  Processing time: {result.processing_time_ms}ms")
    
    if result.matches:
        print(f"\nMatches found:")
        for match in result.matches[:3]:
            print(f"  - '{match.extracted_term.term}' → '{match.concept_label}'")
    
    if result.ontology_gaps:
        print(f"\nOntology gaps:")
        for gap in result.ontology_gaps[:5]:
            print(f"  - {gap}")
    
    if result.errors:
        print(f"\nErrors encountered:")
        for error in result.errors:
            print(f"  - {error}")

def check_api_keys():
    """Check if API keys are configured."""
    print("\n" + "="*60)
    print("Checking API Keys")
    print("="*60)
    
    import os
    
    keys = {
        'ANTHROPIC_API_KEY': os.environ.get('ANTHROPIC_API_KEY'),
        'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY'),
        'GEMINI_API_KEY': os.environ.get('GEMINI_API_KEY')
    }
    
    has_any_key = False
    for key_name, key_value in keys.items():
        if key_value:
            print(f"✅ {key_name}: Configured (length: {len(key_value)})")
            has_any_key = True
        else:
            print(f"❌ {key_name}: Not configured")
    
    if not has_any_key:
        print("\n⚠️  WARNING: No LLM API keys configured!")
        print("The LLM-enhanced annotation will fall back to regex patterns.")
        print("To enable LLM features, set one of the API keys:")
        print("  export ANTHROPIC_API_KEY='your-key'")
    
    return has_any_key

def main():
    """Run all debug tests."""
    print("\n" + "="*80)
    print("LLM-ENHANCED ANNOTATION DEBUG")
    print("="*80)
    
    # Check API keys first
    has_api_key = check_api_keys()
    
    # Test ontology loading
    all_concepts = test_ontology_loading()
    
    if not all_concepts:
        print("\n❌ CRITICAL: No ontology concepts loaded!")
        print("Check that OntServe is running on ports 5003 and 8082")
        return
    
    # Test term extraction
    extracted_terms = test_llm_extraction()
    
    if not extracted_terms:
        print("\n❌ CRITICAL: No terms extracted!")
        if not has_api_key:
            print("This is likely because no LLM API key is configured.")
        return
    
    # Test semantic matching
    if all_concepts and extracted_terms:
        matches = test_semantic_matching(extracted_terms, all_concepts)
        if matches == 0 and has_api_key:
            print("\n❌ PROBLEM: Terms extracted but no semantic matches found!")
            print("This could indicate an issue with the LLM semantic matching.")
    
    # Test full pipeline
    test_full_annotation()
    
    print("\n" + "="*80)
    print("DEBUG COMPLETE")
    print("="*80)

if __name__ == "__main__":
    main()
