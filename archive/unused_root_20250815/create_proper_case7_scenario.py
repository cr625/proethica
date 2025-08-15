#!/usr/bin/env python3
"""
Create a properly structured Case 7 scenario with discrete events, actions, and decisions.
This represents the case as it plays out chronologically with clear separation of components.
"""

from app import create_app
from app.models import db
from app.models.scenario import Scenario
from app.models.event import Event, Action
from app.models.character import Character
from app.models.resource import Resource
from datetime import datetime, timedelta
import json

app = create_app('config')

class ProperScenarioCreator:
    """Create a properly structured scenario from Case 7."""
    
    def create_case7_scenario(self):
        """Create the Case 7 scenario with proper event sequence."""
        
        print("🎯 Creating Proper Case 7 Scenario: AI Ethics in Engineering")
        print("=" * 80)
        
        # Create the scenario
        scenario = Scenario(
            name="AI Ethics in Engineering Practice: Engineer A's Dilemma",
            description="Follow Engineer A through a series of ethical challenges when using AI tools in environmental engineering work. Based on NSPE Case 24-02.",
            world_id=1  # Engineering world
        )
        
        # Set up scenario metadata
        scenario.scenario_metadata = {
            'case_id': 7,
            'case_number': '24-02',
            'case_year': 2025,
            'timeline_mode': True,
            'protagonist': 'Engineer A',
            'total_decisions': 3,
            'scenario_type': 'ethical_case_study'
        }
        
        db.session.add(scenario)
        db.session.flush()  # Get scenario ID
        
        print(f"✅ Created scenario {scenario.id}: {scenario.name}")
        
        # Create characters
        self._create_characters(scenario)
        
        # Create resources
        self._create_resources(scenario)
        
        # Create the timeline: Events → Actions → Decisions
        self._create_timeline(scenario)
        
        db.session.commit()
        
        print(f"\n🎮 Scenario completed successfully!")
        print(f"   URL: http://localhost:3333/scenarios/{scenario.id}")
        
        return scenario
    
    def _create_characters(self, scenario):
        """Create the characters involved in the case."""
        
        characters = [
            {
                'name': 'Engineer A',
                'role': 'protagonist',
                'attributes': {
                    'description': 'Environmental engineer with several years of experience and professional license. Known for strong technical expertise but less confident in technical writing.',
                    'license_status': 'Licensed Professional Engineer',
                    'specialty': 'Environmental Engineering',
                    'experience_level': 'Several years',
                    'writing_confidence': 'Low'
                }
            },
            {
                'name': 'Engineer B', 
                'role': 'mentor',
                'attributes': {
                    'description': 'Recently retired mentor and supervisor of Engineer A. Previously provided guidance and quality assurance reviews.',
                    'status': 'Recently Retired',
                    'relationship': 'Former Mentor/Supervisor',
                    'availability': 'No longer available in work capacity'
                }
            },
            {
                'name': 'Client W',
                'role': 'client',
                'attributes': {
                    'description': 'Client who retained Engineer A to prepare comprehensive report on organic compound contamination.',
                    'project_scope': 'Comprehensive report and engineering design documents',
                    'confidentiality_expectations': 'High'
                }
            }
        ]
        
        for char_data in characters:
            character = Character(
                scenario_id=scenario.id,
                name=char_data['name'],
                role=char_data['role'],
                attributes=char_data['attributes']
            )
            db.session.add(character)
            print(f"   + Character: {char_data['name']} ({char_data['role']})")
    
    def _create_resources(self, scenario):
        """Create the resources (tools, documents, systems) involved."""
        
        resources = [
            {
                'name': 'Open-Source AI Report Writing Software',
                'type': 'software_tool',
                'description': 'AI software for generating text content. New to market with no previous experience by Engineer A.'
            },
            {
                'name': 'AI-Assisted Drafting Tools',
                'type': 'software_tool', 
                'description': 'Tools for generating preliminary engineering design documents and technical drawings.'
            },
            {
                'name': 'Groundwater Monitoring Data',
                'type': 'dataset',
                'description': 'Data from a site Engineer A has been observing for over a year. Contains confidential client information.'
            },
            {
                'name': 'Comprehensive Report on Organic Compound',
                'type': 'deliverable',
                'description': 'Report addressing manufacture, use, and characteristics of an emerging contaminant of concern.'
            },
            {
                'name': 'Engineering Design Documents',
                'type': 'deliverable',
                'description': 'Plans and specifications for modifications to groundwater infrastructure at the site.'
            },
            {
                'name': 'NSPE Code of Ethics',
                'type': 'reference_document',
                'description': 'Professional ethical guidelines that govern engineering practice.'
            }
        ]
        
        for res_data in resources:
            resource = Resource(
                scenario_id=scenario.id,
                name=res_data['name'],
                type=res_data['type'],
                description=res_data['description']
            )
            db.session.add(resource)
            print(f"   + Resource: {res_data['name']} ({res_data['type']})")
    
    def _create_timeline(self, scenario):
        """Create the chronological timeline of events, actions, and decisions."""
        
        base_time = datetime.utcnow()
        
        # Event 1: Project Assignment
        event1 = Event(
            scenario_id=scenario.id,
            event_time=base_time,
            description="Engineer A is retained by Client W for a comprehensive environmental project",
            parameters={
                'event_type': 'project_assignment',
                'title': 'Project Assignment',
                'details': 'Client W retains Engineer A to prepare comprehensive report on organic compound contamination and develop engineering design documents for groundwater infrastructure modifications.',
                'scope': ['Comprehensive report on emerging contaminant', 'Engineering design documents', 'Groundwater infrastructure modifications'],
                'timeline_sequence': 1
            }
        )
        db.session.add(event1)
        
        # Event 2: Loss of Mentorship
        event2 = Event(
            scenario_id=scenario.id,
            event_time=base_time + timedelta(days=5),
            description="Engineer B retires, leaving Engineer A without their usual mentor and quality assurance support",
            parameters={
                'event_type': 'context_change',
                'title': 'Loss of Mentorship',
                'details': 'Engineer B recently retired and is no longer available to Engineer A in a work capacity. Engineer A had previously relied on Engineer B for guidance and quality assurance reviews.',
                'impact': 'Loss of writing support and quality assurance',
                'timeline_sequence': 2
            }
        )
        db.session.add(event2)
        
        # Event 3: AI Discovery
        event3 = Event(
            scenario_id=scenario.id,
            event_time=base_time + timedelta(days=10),
            description="Engineer A discovers AI software options to help with technical writing challenges",
            parameters={
                'event_type': 'tool_discovery',
                'title': 'AI Tool Discovery',
                'details': 'Faced with the need to deliver both report and design documents without Engineer B\'s review, Engineer A discovers open-source AI software for text generation and AI-assisted drafting tools.',
                'tools_discovered': ['Open-source AI report writing software', 'AI-assisted drafting tools'],
                'engineer_experience': 'No previous experience with these tools',
                'timeline_sequence': 3
            }
        )
        db.session.add(event3)
        
        # DECISION POINT 1: Report Text Creation
        decision1 = Action(
            scenario_id=scenario.id,
            name="AI Report Text Decision",
            description="Should Engineer A use AI to create the report text?",
            action_type="ethical_decision",
            is_decision=True,
            action_time=base_time + timedelta(days=12),
            parameters={
                'decision_sequence': 1,
                'question_text': "Was Engineer A's use of AI to create the report text ethical, given that Engineer A thoroughly checked the report?",
                'context': 'Engineer A needs to create a comprehensive report but lacks confidence in technical writing and no longer has Engineer B\'s support.',
                'options': [
                    {
                        'id': 'use_ai_with_review',
                        'title': 'Use AI with Thorough Review',
                        'description': 'Use AI to generate initial text, then thoroughly check and verify all content',
                        'ethical_analysis': 'Leverages technology while maintaining professional responsibility'
                    },
                    {
                        'id': 'traditional_methods',
                        'title': 'Use Traditional Writing Methods',
                        'description': 'Write the report manually without AI assistance',
                        'ethical_analysis': 'Conservative approach avoiding potential AI complications'
                    },
                    {
                        'id': 'seek_alternative_help',
                        'title': 'Seek Alternative Human Assistance',
                        'description': 'Find another colleague or hire writing support',
                        'ethical_analysis': 'Maintains human oversight while addressing writing challenges'
                    }
                ],
                'nspe_conclusion': {
                    'verdict': 'Partly Ethical, Partly Unethical',
                    'reasoning': 'Engineer A was competent and thoroughly reviewed the content, but failed to obtain client permission for data disclosure and document required technical citations.',
                    'correct_option': 'use_ai_with_review',
                    'additional_requirements': ['Client permission for data use', 'Proper technical citations']
                }
            }
        )
        db.session.add(decision1)
        
        # Event 4: Report Creation Process
        event4 = Event(
            scenario_id=scenario.id,
            event_time=base_time + timedelta(days=15),
            description="Engineer A proceeds with report creation using AI tools",
            parameters={
                'event_type': 'work_execution',
                'title': 'Report Creation Process',
                'details': 'Engineer A feeds confidential client data to AI software and generates report text, then thoroughly reviews the content for accuracy and compliance.',
                'process_steps': ['Input groundwater monitoring data to AI', 'Generate report text', 'Thorough content review', 'Accuracy verification'],
                'concerns': ['Confidential client data used', 'Technical citations needed'],
                'timeline_sequence': 4
            }
        )
        db.session.add(event4)
        
        # DECISION POINT 2: Design Document Creation
        decision2 = Action(
            scenario_id=scenario.id,
            name="AI Design Document Decision",
            description="Should Engineer A use AI-assisted drafting tools for engineering design documents?",
            action_type="ethical_decision",
            is_decision=True,
            action_time=base_time + timedelta(days=18),
            parameters={
                'decision_sequence': 2,
                'question_text': "Was Engineer A's use of AI-assisted drafting tools to create the engineering design documents ethical, given that Engineer A reviewed the design at a high level?",
                'context': 'Engineer A needs to create engineering design documents (plans and specifications) for groundwater infrastructure modifications.',
                'options': [
                    {
                        'id': 'use_ai_with_oversight',
                        'title': 'Use AI Tools with Professional Oversight',
                        'description': 'Use AI-assisted drafting while maintaining responsible charge and detailed review',
                        'ethical_analysis': 'Acceptable if engineer maintains full professional responsibility'
                    },
                    {
                        'id': 'traditional_drafting',
                        'title': 'Use Traditional Drafting Methods',
                        'description': 'Create design documents manually using conventional tools',
                        'ethical_analysis': 'Conservative approach ensuring full human control'
                    },
                    {
                        'id': 'hybrid_approach',
                        'title': 'Hybrid Human-AI Approach',
                        'description': 'Use AI for preliminary work, then extensive human refinement',
                        'ethical_analysis': 'Balanced approach leveraging AI efficiency with human expertise'
                    }
                ],
                'nspe_conclusion': {
                    'verdict': 'Not Unethical Per Se, But Misused',
                    'reasoning': 'Using AI drafting tools is not inherently unethical, but Engineer A failed to maintain "Responsible Charge" over the AI output before sealing documents.',
                    'correct_option': 'use_ai_with_oversight',
                    'key_requirement': 'Must maintain Responsible Charge over all AI output'
                }
            }
        )
        db.session.add(decision2)
        
        # Event 5: Design Document Creation
        event5 = Event(
            scenario_id=scenario.id,
            event_time=base_time + timedelta(days=22),
            description="Engineer A creates engineering design documents using AI-assisted tools",
            parameters={
                'event_type': 'work_execution',
                'title': 'Design Document Creation',
                'details': 'Engineer A uses AI-assisted drafting tools to generate preliminary design documents, then reviews the designs at a high level.',
                'deliverables': ['Plans for groundwater infrastructure', 'Technical specifications', 'Modification drawings'],
                'review_level': 'High-level review conducted',
                'professional_seal': 'Documents will require professional seal',
                'timeline_sequence': 5
            }
        )
        db.session.add(event5)
        
        # DECISION POINT 3: Disclosure to Client
        decision3 = Action(
            scenario_id=scenario.id,
            name="AI Disclosure Decision",
            description="Should Engineer A disclose the use of AI to Client W?",
            action_type="ethical_decision",
            is_decision=True,
            action_time=base_time + timedelta(days=25),
            parameters={
                'decision_sequence': 3,
                'question_text': "If the use of AI was acceptable, did Engineer A have an ethical obligation to disclose the use of AI in any form to the Client?",
                'context': 'Engineer A has completed both deliverables using AI assistance and must decide whether to inform Client W about the AI usage.',
                'options': [
                    {
                        'id': 'full_disclosure',
                        'title': 'Full Disclosure of AI Use',
                        'description': 'Inform Client W about all AI assistance used in both report and design documents',
                        'ethical_analysis': 'Maximum transparency approach'
                    },
                    {
                        'id': 'no_disclosure',
                        'title': 'No Disclosure Required',
                        'description': 'Treat AI as a professional tool like CAD software - no disclosure needed',
                        'ethical_analysis': 'Standard professional tool approach'
                    },
                    {
                        'id': 'substantial_role_disclosure',
                        'title': 'Disclose When AI Role is Substantial',
                        'description': 'Inform client only when AI plays a significant role in work products',
                        'ethical_analysis': 'Balanced transparency based on AI significance'
                    }
                ],
                'nspe_conclusion': {
                    'verdict': 'No Obligation, But Transparency Favored',
                    'reasoning': 'Engineer A has no professional or ethical obligation to disclose AI use unless required by contract. However, ethical principles favor transparency when AI plays substantial role.',
                    'correct_option': 'substantial_role_disclosure',
                    'principle': 'Transparency favored when AI plays substantial role in work products'
                }
            }
        )
        db.session.add(decision3)
        
        # Final Event: Project Completion
        event6 = Event(
            scenario_id=scenario.id,
            event_time=base_time + timedelta(days=30),
            description="Engineer A completes the project and delivers all work products to Client W",
            parameters={
                'event_type': 'project_completion',
                'title': 'Project Delivery',
                'details': 'Engineer A delivers the comprehensive report and engineering design documents to Client W, having made decisions about AI use and disclosure.',
                'deliverables_completed': ['Comprehensive report on organic compound', 'Engineering design documents', 'Professional certification'],
                'ethical_decisions_made': 3,
                'timeline_sequence': 6
            }
        )
        db.session.add(event6)
        
        print(f"\n📅 Timeline created:")
        print(f"   - 6 Events (project progression)")
        print(f"   - 3 Decision Points (ethical choices)")
        print(f"   - Chronological sequence over 30-day period")


# Create the scenario
if __name__ == "__main__":
    with app.app_context():
        try:
            creator = ProperScenarioCreator()
            scenario = creator.create_case7_scenario()
            
        except Exception as e:
            print(f"❌ Error creating scenario: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()