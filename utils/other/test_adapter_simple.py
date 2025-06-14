#!/usr/bin/env python3
"""
Simple test script for the engineering ethics adapter.

This script tests just the adapter functionality without Flask dependencies.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.case_deconstruction.engineering_ethics_adapter import EngineeringEthicsAdapter
import json


def create_mock_nspe_case_content():
    """Create mock NSPE case content for testing."""
    return {
        'title': 'Test NSPE Case 85-5: Environmental Impact Assessment',
        'content': '''
        An engineering firm was hired to conduct an environmental impact assessment 
        for a proposed manufacturing facility. During the assessment, the engineers 
        discovered potential groundwater contamination issues that the client had 
        not disclosed. The client pressured the engineers to minimize these findings 
        in their report to avoid regulatory delays.
        ''',
        'case_number': '85-5',
        'sections': {
            'facts': '''
            Engineer A works for ABC Engineering, which was hired by XYZ Manufacturing 
            to conduct an environmental impact assessment for a new facility. During 
            soil testing, Engineer A discovered evidence of existing groundwater 
            contamination near the proposed site. When Engineer A informed the client 
            of these findings, the client revealed they were aware of potential 
            contamination but had hoped it wouldn't be detected. The client asked 
            Engineer A to either omit this information from the report or present 
            it in a way that wouldn't trigger additional regulatory review.
            ''',
            'question': '''
            What are Engineer A's ethical obligations regarding the environmental 
            findings? Should Engineer A modify the report as requested by the client?
            ''',
            'discussion': '''
            This case involves several key ethical principles from the NSPE Code of Ethics:

            1. Engineers must hold paramount the safety, health, and welfare of the public.
            2. Engineers must perform services only in areas of their competence.
            3. Engineers must act as faithful agents or trustees for their clients.
            4. Engineers must avoid conflicts of interest.

            The primary obligation is to public safety and environmental protection. 
            Groundwater contamination poses serious risks to public health and the 
            environment. Concealing or minimizing these findings would violate the 
            engineer's duty to protect public welfare.

            While engineers should act as faithful agents for their clients, this 
            obligation is subordinate to protecting public safety. The client's 
            request to minimize environmental findings creates a conflict between 
            client loyalty and public welfare.
            ''',
            'conclusion': '''
            Engineer A must include accurate and complete information about the 
            groundwater contamination in the environmental impact assessment. 
            The engineer should:

            1. Refuse the client's request to omit or minimize the findings
            2. Clearly document all environmental hazards discovered
            3. Recommend appropriate remediation measures
            4. If necessary, report the contamination to relevant regulatory authorities

            Professional integrity and public safety must take precedence over 
            client pressure in this situation.
            '''
        }
    }


def test_engineering_adapter():
    """Test the EngineeringEthicsAdapter."""
    print("=" * 60)
    print("TESTING ENGINEERING ETHICS ADAPTER")
    print("=" * 60)
    
    # Create adapter
    adapter = EngineeringEthicsAdapter()
    
    # Create mock case content
    case_content = create_mock_nspe_case_content()
    
    print(f"Testing case: {case_content['title']}")
    print(f"Case number: {case_content['case_number']}")
    print()
    
    try:
        # Test deconstruction
        print("Running case deconstruction...")
        deconstructed = adapter.deconstruct_case(case_content)
        
        print(f"✓ Deconstruction completed")
        print(f"  - Stakeholders: {len(deconstructed.analysis.stakeholders)}")
        print(f"  - Decision points: {len(deconstructed.analysis.decision_points)}")
        print(f"  - Reasoning chain steps: {len(deconstructed.analysis.reasoning_chain.reasoning_steps)}")
        print()
        
        # Display stakeholders
        print("STAKEHOLDERS:")
        for i, stakeholder in enumerate(deconstructed.analysis.stakeholders, 1):
            print(f"  {i}. {stakeholder.name} ({stakeholder.role.value})")
            print(f"     Interests: {', '.join(stakeholder.interests)}")
            print(f"     Power: {stakeholder.power_level}")
            print()
        
        # Display decision points
        print("DECISION POINTS:")
        for i, decision in enumerate(deconstructed.analysis.decision_points, 1):
            print(f"  {i}. {decision.title}")
            print(f"     Description: {decision.description[:100]}...")
            print(f"     Principles: {', '.join(decision.ethical_principles)}")
            print(f"     Options: {len(decision.primary_options)}")
            print()
        
        # Display reasoning chain
        print("REASONING CHAIN:")
        reasoning = deconstructed.analysis.reasoning_chain
        print(f"  Facts: {len(reasoning.case_facts)} items")
        print(f"  Principles: {len(reasoning.applicable_principles)} items")
        print(f"  Steps: {len(reasoning.reasoning_steps)} items")
        print(f"  Conclusion: {reasoning.predicted_outcome[:100]}...")
        print()
        
        # Display confidence scores
        print("CONFIDENCE SCORES:")
        print(f"  stakeholder_confidence: {deconstructed.analysis.stakeholder_confidence:.2f}")
        print(f"  decision_points_confidence: {deconstructed.analysis.decision_points_confidence:.2f}")
        print(f"  reasoning_confidence: {deconstructed.analysis.reasoning_confidence:.2f}")
        print()
        
        # Output detailed JSON for inspection
        print("=" * 60)
        print("DETAILED OUTPUT (JSON):")
        print("=" * 60)
        
        output = deconstructed.to_dict()
        
        print(json.dumps(output, indent=2))
        print()
        
        return deconstructed
        
    except Exception as e:
        print(f"✗ Error during deconstruction: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main test function."""
    print("ENGINEERING ETHICS ADAPTER TEST")
    print("=" * 60)
    print()
    
    # Test the adapter
    deconstructed = test_engineering_adapter()
    
    if deconstructed:
        print("=" * 60)
        print("✓ TEST PASSED!")
        print("✓ Engineering adapter successfully deconstructed the case")
        print("✓ Stakeholders, decision points, and reasoning chain extracted")
        print("✓ Confidence scores calculated")
        print("✓ System ready for scenario generation")
    else:
        print("✗ TEST FAILED!")
        print("✗ Engineering adapter encountered errors")
    
    print("=" * 60)


if __name__ == "__main__":
    main()