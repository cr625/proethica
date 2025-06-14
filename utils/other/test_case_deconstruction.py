#!/usr/bin/env python3
"""
Test script for case deconstruction system.
"""

import os
import sys

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.case_deconstruction.engineering_ethics_adapter import EngineeringEthicsAdapter

def test_engineering_adapter():
    """Test the engineering ethics adapter with sample case data."""
    
    # Sample NSPE-style case data
    sample_case = {
        'id': 1,
        'title': 'Bridge Safety Inspection Case',
        'doc_metadata': {
            'sections': {
                'facts': {
                    'content': '''Engineer Smith was hired by ABC Company to inspect a bridge. 
                    During the inspection, Smith discovered significant structural defects that could 
                    pose a safety risk to the public. The client requested that Smith not report 
                    these findings to regulatory authorities, citing financial constraints.'''
                },
                'discussion': {
                    'content': '''This case involves a conflict between the engineer's duty to the client 
                    and the paramount obligation to protect public safety. The NSPE Code requires 
                    engineers to hold paramount the safety, health, and welfare of the public. 
                    However, engineers also have obligations to act as faithful agents for their clients.'''
                },
                'conclusion': {
                    'content': '''The engineer must prioritize public safety and report the structural 
                    defects to the appropriate authorities, despite the client's request for confidentiality.'''
                }
            }
        }
    }
    
    print("🧪 Testing Engineering Ethics Adapter")
    print("=" * 50)
    
    # Initialize adapter
    adapter = EngineeringEthicsAdapter()
    print(f"✅ Adapter initialized: {adapter.get_adapter_info()}")
    
    # Test case validation
    is_valid = adapter.validate_case_content(sample_case)
    print(f"✅ Case validation: {'PASSED' if is_valid else 'FAILED'}")
    
    # Test deconstruction
    try:
        deconstructed = adapter.deconstruct_case(sample_case)
        
        print(f"\n📊 Deconstruction Results:")
        print(f"   Case ID: {deconstructed.case_id}")
        print(f"   Adapter Type: {deconstructed.adapter_type}")
        
        analysis = deconstructed.analysis
        print(f"\n👥 Stakeholders ({len(analysis.stakeholders)}):")
        for stakeholder in analysis.stakeholders:
            print(f"   - {stakeholder.name} ({stakeholder.role.value})")
            print(f"     Interests: {', '.join(stakeholder.interests)}")
        
        print(f"\n⚖️  Decision Points ({len(analysis.decision_points)}):")
        for dp in analysis.decision_points:
            print(f"   - {dp.title} ({dp.decision_type.value})")
            print(f"     Options: {len(dp.primary_options)}")
            for option in dp.primary_options:
                print(f"       • {option.title}")
        
        print(f"\n🧠 Reasoning Chain:")
        if analysis.reasoning_chain:
            rc = analysis.reasoning_chain
            print(f"   Facts: {len(rc.case_facts)}")
            print(f"   Principles: {len(rc.applicable_principles)}")
            print(f"   Steps: {len(rc.reasoning_steps)}")
            print(f"   Predicted Outcome: {rc.predicted_outcome}")
        
        print(f"\n📈 Confidence Scores:")
        print(f"   Stakeholders: {analysis.stakeholder_confidence:.2f}")
        print(f"   Decision Points: {analysis.decision_points_confidence:.2f}")
        print(f"   Reasoning: {analysis.reasoning_confidence:.2f}")
        
        print(f"\n✅ Test completed successfully!")
        return deconstructed
        
    except Exception as e:
        print(f"❌ Error during deconstruction: {e}")
        raise

if __name__ == '__main__':
    test_engineering_adapter()