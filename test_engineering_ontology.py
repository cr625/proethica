#!/usr/bin/env python3
"""Test script for the Engineering Ontology integration."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables for testing
os.environ['BYPASS_AUTH'] = 'true'
os.environ['ENVIRONMENT'] = 'development'

from app import create_app
from app.models import db
from app.models.document import Document


def test_engineering_ontology():
    """Test the Engineering Ontology service integration."""
    print("=" * 60)
    print("Engineering Ontology Integration Test")
    print("=" * 60)
    
    # Create app context
    app = create_app('config')
    
    with app.app_context():
        print("\n1. Testing Engineering Ontology service import:")
        try:
            from app.services.engineering_ontology_service import engineering_ontology_service, EngineeringOntologyService
            print("   ✓ Successfully imported Engineering Ontology service")
            print(f"   ✓ Service type: {type(engineering_ontology_service)}")
            print(f"   ✓ Engineering roles defined: {len(engineering_ontology_service.engineering_roles)}")
            print(f"   ✓ Engineering artifacts defined: {len(engineering_ontology_service.engineering_artifacts)}")
            print(f"   ✓ Engineering standards defined: {len(engineering_ontology_service.engineering_standards)}")
        except Exception as e:
            print(f"   ✗ Error importing Engineering Ontology service: {e}")
            return
        
        print("\n2. Testing Engineering Role identification:")
        test_cases = [
            "A structural engineer was asked to review building plans",
            "The electrical engineer designed the power distribution system", 
            "A consulting engineer provided expert testimony",
            "The mechanical engineer designed the HVAC system",
            "A project engineer coordinated multiple disciplines"
        ]
        
        for i, test_case in enumerate(test_cases):
            print(f"   Test {i+1}: {test_case}")
            roles = engineering_ontology_service.identify_engineering_roles_in_case(test_case)
            if roles:
                for role in roles:
                    print(f"     ✓ Identified: {role.label}")
                    print(f"       Capabilities: {', '.join(role.capabilities)}")
            else:
                print(f"     ⚠ No roles identified")
        
        print("\n3. Testing Engineering Artifact identification:")
        test_artifacts = [
            "The engineering report contained structural analysis results",
            "Engineering drawings showed the foundation design",
            "The inspection report documented several deficiencies",
            "Engineering specifications outlined performance requirements",
            "As-built drawings reflected field changes"
        ]
        
        for i, test_case in enumerate(test_artifacts):
            print(f"   Test {i+1}: {test_case}")
            artifacts = engineering_ontology_service.identify_engineering_artifacts_in_case(test_case)
            if artifacts:
                for artifact in artifacts:
                    print(f"     ✓ Identified: {artifact.label}")
                    print(f"       Related roles: {', '.join(artifact.related_roles)}")
            else:
                print(f"     ⚠ No artifacts identified")
        
        print("\n4. Testing Engineering Standards identification:")
        test_standards = [
            "The design must comply with the local building code",
            "Engineers must follow the NSPE code of ethics",
            "The work violated building safety codes",
            "Professional ethics require honest communication"
        ]
        
        for i, test_case in enumerate(test_standards):
            print(f"   Test {i+1}: {test_case}")
            standards = engineering_ontology_service.identify_engineering_standards_in_case(test_case)
            if standards:
                for standard in standards:
                    print(f"     ✓ Identified: {standard.label}")
                    print(f"       Applicable domains: {', '.join(standard.applicable_domains)}")
            else:
                print(f"     ⚠ No standards identified")
        
        print("\n5. Testing Competence Boundary Analysis:")
        complex_case = """
        A structural engineer was asked to design both the building structure and the electrical systems.
        The project also required mechanical HVAC design and software control systems.
        The engineer had expertise in structural engineering but limited electrical knowledge.
        """
        
        print(f"   Test case: {complex_case.strip()}")
        
        # First identify roles
        roles = engineering_ontology_service.identify_engineering_roles_in_case(complex_case)
        print(f"   Identified roles: {[role.label for role in roles]}")
        
        # Then analyze competence boundaries
        competence_analysis = engineering_ontology_service.analyze_competence_boundaries(complex_case, roles)
        
        print(f"   Required domains: {competence_analysis['required_domains']}")
        print(f"   Available expertise: {competence_analysis['available_expertise']}")
        
        if competence_analysis['competence_gaps']:
            print(f"   ⚠ Competence gaps identified:")
            for gap in competence_analysis['competence_gaps']:
                print(f"     - {gap}")
        
        if competence_analysis['boundary_issues']:
            print(f"   ⚠ Boundary issues identified:")
            for issue in competence_analysis['boundary_issues']:
                print(f"     - {issue}")
        
        print("\n6. Testing FIRAC integration with Engineering Ontology:")
        try:
            from app.services.firac_analysis_service import firac_analysis_service
            
            # Find a case to test with
            cases = Document.query.filter(
                Document.doc_metadata.op('->>')('case_number').isnot(None)
            ).limit(1).all()
            
            if cases:
                test_case = cases[0]
                print(f"   Testing with case: {test_case.title}")
                
                # Run FIRAC analysis
                firac_analysis = firac_analysis_service.analyze_case(test_case.id)
                
                print(f"   ✓ FIRAC analysis completed")
                print(f"   - Facts stakeholders: {firac_analysis.facts.key_stakeholders}")
                print(f"   - Rules ethical principles: {len(firac_analysis.rules.ethical_principles)} principles")
                print(f"   - Rules professional standards: {len(firac_analysis.rules.professional_standards)} standards")
                print(f"   - Conclusion steps: {len(firac_analysis.conclusion.implementation_steps)} steps")
                
                # Check for engineering-specific content
                engineering_principles = [p for p in firac_analysis.rules.ethical_principles if 'engineering' in p.lower() or 'competence' in p.lower()]
                if engineering_principles:
                    print(f"   ✓ Engineering-specific principles identified:")
                    for principle in engineering_principles:
                        print(f"     - {principle}")
                
            else:
                print(f"   ⚠ No cases available for FIRAC testing")
                
        except Exception as e:
            print(f"   ✗ Error testing FIRAC integration: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n7. Testing Engineering Ethics Ontology concepts:")
        
        # Show available role definitions
        print(f"   Available Engineering Roles:")
        for role_key, role in engineering_ontology_service.engineering_roles.items():
            print(f"     - {role.label}: {role.description}")
        
        print(f"\n   Available Engineering Artifacts:")
        for artifact_key, artifact in engineering_ontology_service.engineering_artifacts.items():
            print(f"     - {artifact.label}: {artifact.description}")
        
        print(f"\n   Available Engineering Standards:")
        for standard_key, standard in engineering_ontology_service.engineering_standards.items():
            print(f"     - {standard.label}: {standard.description}")
    
    print("\n" + "=" * 60)
    print("Engineering Ontology Integration Test Complete")
    print("=" * 60)
    
    print("\n🎯 Key Benefits:")
    print("✓ Identifies specific engineering roles (Structural, Electrical, Mechanical, etc.)")
    print("✓ Recognizes engineering artifacts (Reports, Drawings, Specifications)")
    print("✓ Maps engineering standards (Building Codes, NSPE Ethics)")
    print("✓ Analyzes professional competence boundaries")
    print("✓ Enhances FIRAC analysis with engineering-specific insights")
    print("✓ Provides context-aware ethical guidance")


if __name__ == "__main__":
    test_engineering_ontology()