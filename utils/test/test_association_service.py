#!/usr/bin/env python3
"""
Simple test for Enhanced Guideline Association Service
"""

import os
os.environ['DATABASE_URL'] = 'postgresql://ai_ethical_dm_user:password@localhost:5433/ai_ethical_dm'
os.environ['FLASK_ENV'] = 'development'

from app import create_app, db
from app.models.scenario import Scenario
from app.models.entity_triple import EntityTriple

def main():
    app = create_app()
    with app.app_context():
        print("Testing Enhanced Guideline Association Service")
        
        # Check available cases
        cases_with_metadata = Scenario.query.filter(Scenario.scenario_metadata.isnot(None)).limit(5).all()
        print(f"Found {len(cases_with_metadata)} cases with metadata:")
        
        test_case = None
        for case in cases_with_metadata:
            print(f"  Case {case.id}: {case.name}")
            
            if case.scenario_metadata:
                has_doc_structure = 'document_structure' in case.scenario_metadata
                has_sections = 'sections' in case.scenario_metadata
                print(f"    Has document_structure: {has_doc_structure}")
                print(f"    Has sections: {has_sections}")
                
                if has_doc_structure or has_sections:
                    test_case = case
                    break
        
        # Check guideline concepts
        guideline_concepts = EntityTriple.query.filter(
            EntityTriple.entity_type == 'guideline_concept',
            EntityTriple.predicate == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
        ).limit(10).all()
        
        print(f"\nFound {len(guideline_concepts)} guideline concepts:")
        for concept in guideline_concepts[:5]:
            print(f"  ID {concept.id}: {concept.subject}")
            if concept.object_literal:
                print(f"    Literal: {concept.object_literal[:100]}...")
        
        if test_case:
            print(f"\nTesting with case {test_case.id}: {test_case.name}")
            
            # Try to import and test the service
            try:
                from app.services.enhanced_guideline_association_service import EnhancedGuidelineAssociationService
                
                service = EnhancedGuidelineAssociationService()
                
                # Extract sections
                sections = service._extract_case_sections(test_case)
                print(f"Extracted {len(sections)} sections:")
                for section_type, content in sections.items():
                    print(f"  {section_type}: {len(content)} characters")
                
                if sections and guideline_concepts:
                    print("\nGenerating test associations...")
                    associations = service.generate_associations_for_case(test_case.id)
                    print(f"Generated {len(associations)} associations")
                    
                    if associations:
                        # Show top 3
                        for i, assoc in enumerate(associations[:3]):
                            print(f"  {i+1}. Section: {assoc.section_type}, Confidence: {assoc.score.overall_confidence:.3f}")
                            print(f"     Concept ID: {assoc.guideline_concept_id}")
                            print(f"     Reasoning: {assoc.score.reasoning[:80]}...")
                else:
                    print("Insufficient data for testing")
                    
            except Exception as e:
                print(f"Error testing service: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("No suitable test case found")

if __name__ == '__main__':
    main()