#!/usr/bin/env python3
"""Test script for the FIRAC analysis and Ethics Committee system."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables for testing
os.environ['BYPASS_AUTH'] = 'true'
os.environ['ENVIRONMENT'] = 'development'

from app import create_app
from app.models import db
from app.models.document import Document


def test_firac_system():
    """Test the FIRAC analysis and Ethics Committee functionality."""
    print("=" * 60)
    print("FIRAC Analysis & Ethics Committee Test")
    print("=" * 60)
    
    # Create app context
    app = create_app('config')
    
    with app.app_context():
        print("\n1. Testing FIRAC analysis service import:")
        try:
            from app.services.firac_analysis_service import firac_analysis_service, FIRACAnalysisService
            print("   ✓ Successfully imported FIRAC analysis service")
            print(f"   ✓ Service type: {type(firac_analysis_service)}")
        except Exception as e:
            print(f"   ✗ Error importing FIRAC service: {e}")
            return
        
        print("\n2. Testing Ethics Committee agent import:")
        try:
            from app.services.ethics_committee_agent import ethics_committee_agent, EthicsCommitteeAgent
            print("   ✓ Successfully imported Ethics Committee agent")
            print(f"   ✓ Agent type: {type(ethics_committee_agent)}")
            print(f"   ✓ Committee has {len(ethics_committee_agent.committee_members)} members")
        except Exception as e:
            print(f"   ✗ Error importing Ethics Committee agent: {e}")
            return
        
        print("\n3. Finding cases for FIRAC analysis:")
        try:
            # Find cases that might have sections for analysis
            cases = Document.query.filter(
                Document.doc_metadata.op('->>')('case_number').isnot(None)
            ).limit(3).all()
            
            print(f"   ✓ Found {len(cases)} cases in database")
            
            for case in cases:
                case_number = case.doc_metadata.get('case_number', 'Unknown')
                print(f"     - Case {case.id}: {case.title[:50]}... (Case #{case_number})")
        except Exception as e:
            print(f"   ✗ Error finding cases: {e}")
            cases = []
        
        print("\n4. Testing FIRAC analysis generation:")
        if cases:
            test_case = cases[0]
            print(f"   Testing with case {test_case.id}: {test_case.title}")
            
            try:
                # Test the FIRAC analysis
                firac_analysis = firac_analysis_service.analyze_case(test_case.id)
                
                print("   ✓ Successfully generated FIRAC analysis!")
                print(f"   - Case: {firac_analysis.case_title}")
                print(f"   - Facts: {len(firac_analysis.facts.factual_statements)} statements")
                print(f"   - Issues: {len(firac_analysis.issues.primary_ethical_issues)} primary issues")
                print(f"   - Rules: {len(firac_analysis.rules.applicable_guidelines)} guidelines")
                print(f"   - Analysis: {len(firac_analysis.analysis.reasoning_chain)} reasoning steps")
                print(f"   - Committee needed: {firac_analysis.conclusion.committee_consultation_needed}")
                print(f"   - Overall confidence: {firac_analysis.confidence_overview['overall_confidence']:.1%}")
                
                # Test Ethics Committee if consultation is needed or force it for testing
                print("\n5. Testing Ethics Committee consultation:")
                try:
                    committee_discussion = ethics_committee_agent.conduct_committee_consultation(firac_analysis)
                    
                    print("   ✓ Successfully conducted committee consultation!")
                    print(f"   - Committee members: {len(committee_discussion.member_positions)}")
                    print(f"   - Discussion phases: {len(committee_discussion.discussion_phases)}")
                    print(f"   - Areas of agreement: {len(committee_discussion.areas_of_agreement)}")
                    print(f"   - Consensus confidence: {committee_discussion.confidence_in_consensus:.1%}")
                    
                    # Show committee member positions
                    print(f"\n   Committee Member Positions:")
                    for pos in committee_discussion.member_positions:
                        print(f"     - {pos.member.name} ({pos.member.role}): {pos.position}")
                        print(f"       Confidence: {pos.confidence:.1%}")
                    
                    # Show consensus recommendation
                    print(f"\n   Final Recommendation:")
                    print(f"   {committee_discussion.consensus_recommendation}")
                    
                except Exception as e:
                    print(f"   ✗ Error in committee consultation: {e}")
                
            except Exception as e:
                print(f"   ✗ Error generating FIRAC analysis: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("   ⚠ No cases found to test with")
            print("   💡 Try importing some NSPE cases first")
        
        print("\n6. Testing FIRAC system capabilities:")
        try:
            # Test FIRAC service components
            service = FIRACAnalysisService()
            print("   ✓ Can create new FIRAC service instance")
            
            # Test Ethics Committee components
            agent = EthicsCommitteeAgent()
            print(f"   ✓ Can create new Ethics Committee agent")
            print(f"   ✓ Committee composition: {len(agent.committee_members)} members")
            
            # Show committee member expertise
            print(f"\n   Committee Member Expertise:")
            for member in agent.committee_members:
                print(f"     - {member.name}: {', '.join(member.expertise)}")
            
        except Exception as e:
            print(f"   ✗ Error testing system capabilities: {e}")
    
    print("\n" + "=" * 60)
    print("FIRAC Analysis & Ethics Committee Test Complete")
    print("=" * 60)
    
    print("\n🎯 Next Steps:")
    print("1. Start the app: python run.py --port 3333")
    print("2. Visit: http://localhost:3333/dashboard")
    print("3. Click 'Test FIRAC Analysis' button")
    print("4. Generate FIRAC analysis for real cases!")
    print("5. Use 'Ethics Committee' button for committee consultation!")


if __name__ == "__main__":
    test_firac_system()