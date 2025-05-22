#!/usr/bin/env python3
"""
Test script for LLM-based section-triple association.

This script tests the LLM-based section-triple association by processing
a single section and displaying the results.
"""

import sys
import json
import logging
from pprint import pprint

from ttl_triple_association.ontology_triple_loader import OntologyTripleLoader
from ttl_triple_association.embedding_service import EmbeddingService
from ttl_triple_association.llm_section_triple_associator import LLMSectionTripleAssociator
from ttl_triple_association.section_triple_association_service import SectionTripleAssociationService

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_section_content(section_id):
    """Get section content from database for testing."""
    from sqlalchemy import create_engine, text
    import os

    # Get database URL from environment or use default
    db_url = os.environ.get(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm"
    )
    
    # Connect to database
    engine = create_engine(db_url)
    
    # Get section content
    with engine.connect() as conn:
        query = text("""
            SELECT content, section_type 
            FROM document_sections 
            WHERE id = :section_id
        """)
        result = conn.execute(query, {"section_id": section_id}).fetchone()
        
        if result:
            return {
                "content": result[0],
                "section_type": result[1],
                "section_id": section_id
            }
        else:
            return None

def test_with_section(section_id):
    """Test LLM-based associator with a specific section."""
    print(f"Testing LLM-based section-triple association with section {section_id}...")
    
    # Get section content
    section_data = get_section_content(section_id)
    if not section_data:
        print(f"Section {section_id} not found")
        return False
    
    print(f"Section type: {section_data['section_type']}")
    print(f"Content preview: {section_data['content'][:150]}...")
    
    try:
        # Initialize components
        ontology_loader = OntologyTripleLoader()
        embedding_service = EmbeddingService()
        
        # Create LLM associator
        llm_associator = LLMSectionTripleAssociator(
            ontology_loader=ontology_loader,
            embedding_service=embedding_service,
            max_matches=5
        )
        
        # Process section
        matches = llm_associator.associate_section(
            section_content=section_data["content"],
            section_metadata=section_data
        )
        
        # Display results
        print(f"\nFound {len(matches)} matches:")
        for i, match in enumerate(matches):
            print(f"\n--- Match {i+1} ---")
            print(f"Concept: {match['concept_label']}")
            print(f"URI: {match['concept_uri']}")
            print(f"Score: {match['combined_score']:.2f}")
            print(f"Match Type: {match['match_type']}")
            
            if 'metadata' in match and 'explanation' in match['metadata']:
                print(f"Explanation: {match['metadata']['explanation']}")
                
                if 'patterns' in match['metadata'] and match['metadata']['patterns']:
                    print("Patterns:")
                    for pattern in match['metadata']['patterns']:
                        print(f"  - {pattern}")
        
        return True
    
    except Exception as e:
        print(f"Error testing LLM associator: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_with_service(section_id):
    """Test LLM-based association using the service."""
    print(f"Testing SectionTripleAssociationService with LLM option for section {section_id}...")
    
    try:
        # Initialize service with LLM option
        service = SectionTripleAssociationService(
            similarity_threshold=0.5,
            max_matches=5,
            use_llm=True
        )
        
        # Process section
        result = service.associate_section_with_concepts(section_id, override_use_llm=True)
        
        # Display results
        if result.get('success'):
            matches = result.get('matches', [])
            print(f"\nFound {len(matches)} matches:")
            
            for i, match in enumerate(matches):
                print(f"\n--- Match {i+1} ---")
                print(f"Concept: {match['concept_label']}")
                print(f"URI: {match['concept_uri']}")
                print(f"Score: {match['match_score']:.2f}")
                print(f"Match Type: {match['match_type']}")
                
                if 'metadata' in match and 'explanation' in match['metadata']:
                    print(f"Explanation: {match['metadata']['explanation']}")
        else:
            print(f"Error: {result.get('error')}")
        
        return result.get('success', False)
    
    except Exception as e:
        print(f"Error testing service with LLM option: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_llm_section_triple_association.py SECTION_ID")
        sys.exit(1)
    
    section_id = int(sys.argv[1])
    
    # Test direct LLM associator
    print("\n=== Testing LLM Associator Directly ===\n")
    test_with_section(section_id)
    
    # Test service with LLM option
    print("\n\n=== Testing Service with LLM Option ===\n")
    test_with_service(section_id)
