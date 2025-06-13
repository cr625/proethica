#!/usr/bin/env python3
"""
Test script for scenario generation system.

This script tests the case deconstruction and scenario generation
without requiring a full Flask application context.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.case_deconstruction.engineering_ethics_adapter import EngineeringEthicsAdapter
from app.services.scenario_generation_service import ScenarioGenerationService
import json


def create_mock_nspe_case():
    """Create a mock NSPE case for testing."""
    case_data = {
        'title': 'Test NSPE Case 85-5: Environmental Impact Assessment',
        'content': '''
        An engineering firm was hired to conduct an environmental impact assessment 
        for a proposed manufacturing facility. During the assessment, the engineers 
        discovered potential groundwater contamination issues that the client had 
        not disclosed. The client pressured the engineers to minimize these findings 
        in their report to avoid regulatory delays.
        ''',
        'doc_metadata': {
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
    }
    
    # Create a mock Document object
    doc = type('Document', (), case_data)()
    doc.id = 1
    doc.world = type('World', (), {'name': 'Engineering Ethics'})()
    
    return doc


def test_engineering_adapter():
    """Test the EngineeringEthicsAdapter."""
    print("=" * 60)
    print("TESTING ENGINEERING ETHICS ADAPTER")
    print("=" * 60)
    
    # Create adapter
    adapter = EngineeringEthicsAdapter()
    
    # Create mock case
    case = create_mock_nspe_case()
    
    print(f"Testing case: {case.title}")
    print(f"Case number: {case.doc_metadata['case_number']}")
    print()
    
    try:
        # Test deconstruction
        print("Running case deconstruction...")
        deconstructed = adapter.deconstruct_case(case)
        
        print(f"✓ Deconstruction completed")
        print(f"  - Stakeholders: {len(deconstructed.stakeholders)}")
        print(f"  - Decision points: {len(deconstructed.decision_points)}")
        print(f"  - Reasoning chain steps: {len(deconstructed.reasoning_chain.get('steps', []))}")
        print()
        
        # Display stakeholders
        print("STAKEHOLDERS:")
        for i, stakeholder in enumerate(deconstructed.stakeholders, 1):
            print(f"  {i}. {stakeholder['name']} ({stakeholder['role']})")
            print(f"     Interests: {', '.join(stakeholder.get('interests', []))}")
            print(f"     Power: {stakeholder.get('power_level', 'unknown')}")
            print()
        
        # Display decision points
        print("DECISION POINTS:")
        for i, decision in enumerate(deconstructed.decision_points, 1):
            print(f"  {i}. {decision['title']}")
            print(f"     Description: {decision['description'][:100]}...")
            print(f"     Principles: {', '.join(decision.get('ethical_principles', []))}")
            print(f"     Options: {len(decision.get('options', []))}")
            print()
        
        # Display reasoning chain
        print("REASONING CHAIN:")
        reasoning = deconstructed.reasoning_chain
        print(f"  Facts: {len(reasoning.get('facts', []))} items")
        print(f"  Principles: {len(reasoning.get('principles', []))} items")
        print(f"  Steps: {len(reasoning.get('steps', []))} items")
        print(f"  Conclusion: {reasoning.get('conclusion', 'N/A')[:100]}...")
        print()
        
        # Display confidence scores
        print("CONFIDENCE SCORES:")
        for component, score in deconstructed.confidence_scores.items():
            print(f"  {component}: {score:.2f}")
        print()
        
        return deconstructed
        
    except Exception as e:
        print(f"✗ Error during deconstruction: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_scenario_generation(deconstructed_case):
    """Test scenario generation from deconstructed case."""
    print("=" * 60)
    print("TESTING SCENARIO GENERATION")
    print("=" * 60)
    
    if not deconstructed_case:
        print("✗ No deconstructed case available for testing")
        return None
    
    try:
        # Create scenario generation service
        service = ScenarioGenerationService()
        
        print("Generating comprehensive scenario data...")
        scenario_data = service._generate_comprehensive_scenario_data(deconstructed_case)
        
        print(f"✓ Scenario data generated")
        print(f"  - Characters: {len(scenario_data.get('characters', []))}")
        print(f"  - Timeline phases: {len(scenario_data.get('timeline', {}).get('phases', []))}")
        print(f"  - Decision tree nodes: {len(scenario_data.get('decision_tree', {}).get('nodes', {}))}")
        print(f"  - Learning objectives: {len(scenario_data.get('learning_framework', {}).get('primary_objectives', []))}")
        print()
        
        # Display characters
        print("CHARACTERS:")
        for char in scenario_data.get('characters', []):
            print(f"  - {char['name']} ({char['role']})")
            print(f"    Power: {char['power_level']}, Stance: {char['ethical_stance']}")
            print(f"    Interests: {', '.join(char['primary_interests'][:2])}...")
            print()
        
        # Display timeline
        print("TIMELINE PHASES:")
        for phase in scenario_data.get('timeline', {}).get('phases', []):
            print(f"  - {phase['name']} ({phase.get('duration_minutes', 0)} min)")
            print(f"    {phase['description']}")
            print()
        
        # Display decision tree
        print("DECISION TREE NODES:")
        for node_id, node in scenario_data.get('decision_tree', {}).get('nodes', {}).items():
            print(f"  - {node_id}: {node.get('title', 'Untitled')} ({node['type']})")
            if node['type'] == 'decision':
                print(f"    Options: {len(node.get('options', []))}")
            print()
        
        # Display learning framework
        print("LEARNING OBJECTIVES:")
        objectives = scenario_data.get('learning_framework', {}).get('primary_objectives', [])
        for i, obj in enumerate(objectives[:3], 1):
            print(f"  {i}. {obj}")
        if len(objectives) > 3:
            print(f"    ... and {len(objectives) - 3} more")
        print()
        
        return scenario_data
        
    except Exception as e:
        print(f"✗ Error during scenario generation: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main test function."""
    print("SCENARIO GENERATION SYSTEM TEST")
    print("=" * 60)
    print()
    
    # Test 1: Engineering Ethics Adapter
    deconstructed = test_engineering_adapter()
    
    if deconstructed:
        # Test 2: Scenario Generation
        scenario_data = test_scenario_generation(deconstructed)
        
        if scenario_data:
            print("=" * 60)
            print("✓ ALL TESTS PASSED!")
            print("✓ Engineering adapter successfully deconstructed case")
            print("✓ Scenario generation created comprehensive scenario data")
            print("✓ System is ready for integration testing")
        else:
            print("✗ Scenario generation test failed")
    else:
        print("✗ Engineering adapter test failed")
    
    print("=" * 60)


if __name__ == "__main__":
    main()