#!/usr/bin/env python3
"""
Create an enhanced Case 7 scenario with proper question-derived options,
NSPE Code references, precedent cases, and nuanced reasoning.
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

class EnhancedCase7Creator:
    """Create enhanced Case 7 scenario with comprehensive decision options."""
    
    def create_enhanced_scenario(self):
        """Create the enhanced Case 7 scenario."""
        
        print("🎯 Creating Enhanced Case 7 Scenario: AI Ethics with NSPE Analysis")
        print("=" * 80)
        
        # Create the scenario
        scenario = Scenario(
            name="Enhanced AI Ethics: Engineer A's Professional Dilemma",
            description="Experience the complex ethical challenges of AI use in engineering practice. Navigate through Engineer A's decisions with comprehensive analysis based on NSPE Code of Ethics and precedent cases. Based on NSPE Case 24-02.",
            world_id=1  # Engineering world
        )
        
        # Set up enhanced scenario metadata
        scenario.scenario_metadata = {
            'case_id': 7,
            'case_number': '24-02',
            'case_year': 2025,
            'timeline_mode': True,
            'protagonist': 'Engineer A',
            'total_decisions': 3,
            'scenario_type': 'enhanced_ethical_case_study',
            'nspe_code_sections': ['I.1', 'I.2', 'I.5', 'II.1.c', 'II.2.a', 'II.2.b', 'III.3', 'III.8.a', 'III.9'],
            'precedent_cases': ['BER Case 90-6', 'BER Case 98-3'],
            'position_statements': ['NSPE Position Statement 10-1778']
        }
        
        db.session.add(scenario)
        db.session.flush()  # Get scenario ID
        
        print(f"✅ Created enhanced scenario {scenario.id}: {scenario.name}")
        
        # Create characters (same as before)
        self._create_characters(scenario)
        
        # Create resources (same as before) 
        self._create_resources(scenario)
        
        # Create enhanced timeline with detailed decision options
        self._create_enhanced_timeline(scenario)
        
        db.session.commit()
        
        print(f"\n🎮 Enhanced scenario completed successfully!")
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
                    'writing_confidence': 'Low',
                    'technical_competence': 'High'
                }
            },
            {
                'name': 'Engineer B', 
                'role': 'mentor',
                'attributes': {
                    'description': 'Recently retired mentor and supervisor of Engineer A. Previously provided guidance and quality assurance reviews.',
                    'status': 'Recently Retired',
                    'relationship': 'Former Mentor/Supervisor',
                    'availability': 'No longer available in work capacity',
                    'role_in_case': 'Absent but contextually important'
                }
            },
            {
                'name': 'Client W',
                'role': 'client',
                'attributes': {
                    'description': 'Client who retained Engineer A to prepare comprehensive report on organic compound contamination.',
                    'project_scope': 'Comprehensive report and engineering design documents',
                    'confidentiality_expectations': 'High',
                    'data_provided': 'Confidential groundwater monitoring data'
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
                'description': 'AI software for generating text content. New to market with no previous experience by Engineer A. Requires input of project data to generate relevant content.'
            },
            {
                'name': 'AI-Assisted Drafting Tools',
                'type': 'software_tool', 
                'description': 'Tools for generating preliminary engineering design documents and technical drawings. Similar to advanced CAD software but with AI-driven content generation.'
            },
            {
                'name': 'Groundwater Monitoring Data',
                'type': 'dataset',
                'description': 'Confidential data from a site Engineer A has been observing for over a year. Contains sensitive client information about contamination levels and site conditions.'
            },
            {
                'name': 'Comprehensive Report on Organic Compound',
                'type': 'deliverable',
                'description': 'Report addressing manufacture, use, and characteristics of an emerging contaminant of concern. Requires professional engineering judgment and technical writing.'
            },
            {
                'name': 'Engineering Design Documents',
                'type': 'deliverable',
                'description': 'Plans and specifications for modifications to groundwater infrastructure at the site. Requires professional seal and Engineer\'s responsible charge.'
            },
            {
                'name': 'NSPE Code of Ethics',
                'type': 'reference_document',
                'description': 'Professional ethical guidelines that govern engineering practice. Contains specific sections relevant to competence, confidentiality, and professional responsibility.'
            },
            {
                'name': 'NSPE Position Statement 10-1778',
                'type': 'reference_document',
                'description': 'Defines "Responsible Charge" requirements for professional engineering work, particularly relevant to document sealing and oversight.'
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
    
    def _create_enhanced_timeline(self, scenario):
        """Create the chronological timeline with enhanced decision options."""
        
        base_time = datetime.now()
        
        # Events 1-3: Same as before (Project Assignment, Loss of Mentorship, AI Discovery)
        self._create_initial_events(scenario, base_time)
        
        # ENHANCED DECISION 1: AI Report Text Ethics
        self._create_decision_1_enhanced(scenario, base_time + timedelta(days=12))
        
        # Event 4: Report Creation Process
        self._create_report_creation_event(scenario, base_time + timedelta(days=15))
        
        # ENHANCED DECISION 2: AI Design Document Ethics
        self._create_decision_2_enhanced(scenario, base_time + timedelta(days=18))
        
        # Event 5: Design Document Creation
        self._create_design_creation_event(scenario, base_time + timedelta(days=22))
        
        # ENHANCED DECISION 3: AI Disclosure Ethics
        self._create_decision_3_enhanced(scenario, base_time + timedelta(days=25))
        
        # Final Event: Project Completion
        self._create_completion_event(scenario, base_time + timedelta(days=30))
        
        print(f"\n📅 Enhanced timeline created:")
        print(f"   - 6 Events (project progression)")
        print(f"   - 3 Enhanced Decision Points with detailed NSPE analysis")
        print(f"   - 11 total decision options with Code references")
    
    def _create_initial_events(self, scenario, base_time):
        """Create the initial 3 events."""
        
        events = [
            {
                'time_offset': 0,
                'title': 'Project Assignment',
                'description': 'Engineer A is retained by Client W for a comprehensive environmental project',
                'details': 'Client W retains Engineer A to prepare comprehensive report on organic compound contamination and develop engineering design documents for groundwater infrastructure modifications.',
                'scope': ['Comprehensive report on emerging contaminant', 'Engineering design documents', 'Groundwater infrastructure modifications']
            },
            {
                'time_offset': 5,
                'title': 'Loss of Mentorship',
                'description': 'Engineer B retires, leaving Engineer A without their usual mentor and quality assurance support',
                'details': 'Engineer B recently retired and is no longer available to Engineer A in a work capacity. Engineer A had previously relied on Engineer B for guidance and quality assurance reviews.',
                'impact': 'Loss of writing support and quality assurance'
            },
            {
                'time_offset': 10,
                'title': 'AI Tool Discovery',
                'description': 'Engineer A discovers AI software options to help with technical writing challenges',
                'details': 'Faced with the need to deliver both report and design documents without Engineer B\'s review, Engineer A discovers open-source AI software for text generation and AI-assisted drafting tools.',
                'tools_discovered': ['Open-source AI report writing software', 'AI-assisted drafting tools']
            }
        ]
        
        for i, event_data in enumerate(events):
            event = Event(
                scenario_id=scenario.id,
                event_time=base_time + timedelta(days=event_data['time_offset']),
                description=event_data['description'],
                parameters={
                    'event_type': ['project_assignment', 'context_change', 'tool_discovery'][i],
                    'title': event_data['title'],
                    'details': event_data['details'],
                    'timeline_sequence': i + 1,
                    **{k: v for k, v in event_data.items() if k not in ['time_offset', 'title', 'description', 'details']}
                }
            )
            db.session.add(event)
    
    def _create_decision_1_enhanced(self, scenario, decision_time):
        """Create enhanced Decision 1: AI Report Text Ethics."""
        
        # Create 4 separate Action entries for each option
        options = [
            {
                'id': 'ethical_aspects',
                'title': 'Ethical aspects: Competent review maintained professional standards',
                'nspe_status': 'nspe_positive',
                'description': 'Engineer A was competent and thoroughly reviewed the AI-generated content, ensuring accuracy and compliance with professional standards.',
                'ethical_analysis': 'NSPE found this aspect ethical because Engineer A maintained professional competence through thorough review.',
                'code_references': ['I.2 (Perform services only in areas of their competence)'],
                'precedent_cases': ['BER Case 90-6: Established that engineers can use computer tools with proper oversight'],
                'reasoning_quote': 'Engineer A was competent and did thoroughly review and verify the AI-generated content, ensuring accuracy and compliance with professional standards'
            },
            {
                'id': 'unethical_aspects',
                'title': 'Unethical aspects: Violated confidentiality and citation requirements',
                'nspe_status': 'nspe_negative',
                'description': 'Engineer A violated client confidentiality by feeding private data to external AI without permission and failed to document required technical citations.',
                'ethical_analysis': 'NSPE found this aspect unethical due to clear violations of confidentiality and professional attribution standards.',
                'code_references': ['II.1.c (Confidentiality of client information)', 'III.9 (Give credit for engineering work)'],
                'precedent_cases': [],
                'reasoning_quote': 'Engineer A did not obtain client permission to disclose private information, nor did Engineer A document required technical citations'
            },
            {
                'id': 'completely_ethical',
                'title': 'Completely ethical - AI is just a writing tool',
                'nspe_status': 'alternative',
                'description': 'AI for text generation is like spell-check or grammar software - a professional writing aid that doesn\'t compromise engineering judgment.',
                'ethical_analysis': 'This view treats AI as standard professional software, emphasizing that Engineer A\'s expertise and review ensure quality.',
                'code_references': ['I.2 (Competence)'],
                'precedent_cases': ['BER Case 90-6: Supported technology use with engineer oversight'],
                'reasoning_quote': 'Professional writing aids don\'t compromise engineering responsibility when properly supervised'
            },
            {
                'id': 'completely_unethical',
                'title': 'Completely unethical - Cannot delegate technical writing',
                'nspe_status': 'alternative',
                'description': 'Professional engineering reports must be personally authored to maintain accountability and professional responsibility.',
                'ethical_analysis': 'This strict interpretation holds that AI generation compromises professional responsibility regardless of review quality.',
                'code_references': ['II.2.b (Personal direction and control)'],
                'precedent_cases': [],
                'reasoning_quote': 'Professional engineering work products must be under complete personal direction and control'
            }
        ]
        
        for i, option in enumerate(options):
            action = Action(
                scenario_id=scenario.id,
                name=f"Report AI Ethics Option {i+1}",
                description=option['title'],
                action_type="ethical_decision",
                is_decision=True,
                action_time=decision_time,
                parameters={
                    'decision_sequence': 1,
                    'decision_title': 'AI Report Text Ethics',
                    'question_text': "Was Engineer A's use of AI to create the report text ethical, given that Engineer A thoroughly checked the report?",
                    'option_id': option['id'],
                    'option_number': i + 1,
                    'nspe_status': option['nspe_status'],
                    'detailed_description': option['description'],
                    'ethical_analysis': option['ethical_analysis'],
                    'code_references': option['code_references'],
                    'precedent_cases': option['precedent_cases'],
                    'reasoning_quote': option['reasoning_quote'],
                    'context': 'Engineer A needs to create a comprehensive report but lacks confidence in technical writing and no longer has Engineer B\'s support.'
                }
            )
            db.session.add(action)
    
    def _create_decision_2_enhanced(self, scenario, decision_time):
        """Create enhanced Decision 2: AI Design Document Ethics."""
        
        options = [
            {
                'id': 'ethical_tool_use',
                'title': 'Ethical tool use: AI drafting tools are like advanced CAD',
                'nspe_status': 'alternative',
                'description': 'AI-assisted drafting is similar to computer-aided design tools already accepted in engineering practice.',
                'ethical_analysis': 'This view treats AI drafting as an evolution of established CAD technology, with engineer competence validating output.',
                'code_references': ['I.2 (Competence)'],
                'precedent_cases': ['BER Case 90-6: Established acceptability of computer drafting tools with engineer review'],
                'reasoning_quote': 'Computer-aided design tools with proper engineer oversight have established precedent'
            },
            {
                'id': 'failed_responsible_charge',
                'title': 'Unethical application: Failed to maintain Responsible Charge',
                'nspe_status': 'nspe_negative',
                'description': 'Engineer A failed to maintain Responsible Charge over the AI tool and its output before sealing the document.',
                'ethical_analysis': 'NSPE found this unethical because proper Responsible Charge requires detailed oversight before sealing documents.',
                'code_references': ['II.2.b (Do not affix signatures to documents not under personal direction/control)'],
                'precedent_cases': [],
                'reasoning_quote': 'Engineer A\'s misuse of the tool, by failing to maintain Responsible Charge over the AI tool and its output before sealing the document',
                'standards_referenced': ['NSPE Position Statement 10-1778 (Responsible Charge definition)']
            },
            {
                'id': 'adequate_review',
                'title': 'Ethical with adequate review - High-level review sufficient',
                'nspe_status': 'alternative',
                'description': 'Engineer\'s professional competence and high-level review ensure document quality and meet professional standards.',
                'ethical_analysis': 'This position holds that a licensed engineer\'s review validates technical content regardless of generation method.',
                'code_references': ['I.2 (Competence)'],
                'precedent_cases': [],
                'reasoning_quote': 'Professional competence and review validate technical content quality'
            },
            {
                'id': 'personal_creation_required',
                'title': 'Unethical regardless - Design documents require personal creation',
                'nspe_status': 'alternative',
                'description': 'Documents requiring professional seal must be under complete personal direction and control from creation to completion.',
                'ethical_analysis': 'This strict interpretation requires that sealed documents represent entirely personal professional work.',
                'code_references': ['II.2.b (Personal direction and control)'],
                'precedent_cases': [],
                'reasoning_quote': 'Professional seal implies engineer personally directed all design work from conception'
            }
        ]
        
        for i, option in enumerate(options):
            action = Action(
                scenario_id=scenario.id,
                name=f"Design AI Ethics Option {i+1}",
                description=option['title'],
                action_type="ethical_decision",
                is_decision=True,
                action_time=decision_time,
                parameters={
                    'decision_sequence': 2,
                    'decision_title': 'AI Design Document Ethics',
                    'question_text': "Was Engineer A's use of AI-assisted drafting tools to create the engineering design documents ethical, given that Engineer A reviewed the design at a high level?",
                    'option_id': option['id'],
                    'option_number': i + 1,
                    'nspe_status': option['nspe_status'],
                    'detailed_description': option['description'],
                    'ethical_analysis': option['ethical_analysis'],
                    'code_references': option['code_references'],
                    'precedent_cases': option['precedent_cases'],
                    'reasoning_quote': option['reasoning_quote'],
                    'standards_referenced': option.get('standards_referenced', []),
                    'context': 'Engineer A needs to create engineering design documents (plans and specifications) for groundwater infrastructure modifications.'
                }
            )
            db.session.add(action)
    
    def _create_decision_3_enhanced(self, scenario, decision_time):
        """Create enhanced Decision 3: AI Disclosure Ethics."""
        
        options = [
            {
                'id': 'no_obligation_transparency_favored',
                'title': 'No obligation, but transparency favored',
                'nspe_status': 'nspe_conclusion',
                'description': 'Engineer A has no professional or ethical obligation to disclose AI use unless required by contract, but ethical principles favor transparency when AI plays a substantial role.',
                'ethical_analysis': 'NSPE\'s balanced conclusion recognizes no explicit requirement while encouraging transparency for substantial AI involvement.',
                'code_references': ['I.5 (Avoid deceptive acts) - supports transparency'],
                'precedent_cases': [],
                'reasoning_quote': 'Engineer A has no professional or ethical obligation to disclose AI use unless required by contract. However, ethical principles favor transparency when AI plays a substantial role',
                'current_state': 'No universal guideline mandating AI disclosure in engineering work'
            },
            {
                'id': 'must_disclose',
                'title': 'Must disclose - Client has right to know methodology',
                'nspe_status': 'alternative',
                'description': 'Clients should be informed about significant tools and methods affecting their project to maintain trust and transparency.',
                'ethical_analysis': 'This position emphasizes client rights and transparency, viewing AI disclosure as preventing deception.',
                'code_references': ['I.5 (Avoid deceptive acts)', 'III.3 (Avoid conduct deceiving the public)'],
                'precedent_cases': [],
                'reasoning_quote': 'Full disclosure prevents any perception of deception and honors client relationship'
            },
            {
                'id': 'no_disclosure_needed',
                'title': 'No disclosure needed - AI is standard professional software',
                'nspe_status': 'alternative',
                'description': 'AI tools are professional software like CAD, analysis programs, or design databases - routine tools that don\'t require client disclosure.',
                'ethical_analysis': 'This view treats AI as standard professional software, similar to other computational tools routinely used without disclosure.',
                'code_references': [],
                'precedent_cases': ['BER Case 90-6 (CADD systems)', 'BER Case 98-3 (CD-ROM tools) - software tools don\'t require client disclosure'],
                'reasoning_quote': 'Engineers routinely use software tools without disclosing every program to clients'
            }
        ]
        
        for i, option in enumerate(options):
            action = Action(
                scenario_id=scenario.id,
                name=f"Disclosure Ethics Option {i+1}",
                description=option['title'],
                action_type="ethical_decision",
                is_decision=True,
                action_time=decision_time,
                parameters={
                    'decision_sequence': 3,
                    'decision_title': 'AI Disclosure Ethics',
                    'question_text': "If the use of AI was acceptable, did Engineer A have an ethical obligation to disclose the use of AI in any form to the Client?",
                    'option_id': option['id'],
                    'option_number': i + 1,
                    'nspe_status': option['nspe_status'],
                    'detailed_description': option['description'],
                    'ethical_analysis': option['ethical_analysis'],
                    'code_references': option['code_references'],
                    'precedent_cases': option['precedent_cases'],
                    'reasoning_quote': option['reasoning_quote'],
                    'current_state': option.get('current_state', ''),
                    'context': 'Engineer A has completed both deliverables using AI assistance and must decide whether to inform Client W about the AI usage.'
                }
            )
            db.session.add(action)
    
    def _create_report_creation_event(self, scenario, event_time):
        """Create the report creation event."""
        event = Event(
            scenario_id=scenario.id,
            event_time=event_time,
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
        db.session.add(event)
    
    def _create_design_creation_event(self, scenario, event_time):
        """Create the design document creation event."""
        event = Event(
            scenario_id=scenario.id,
            event_time=event_time,
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
        db.session.add(event)
    
    def _create_completion_event(self, scenario, event_time):
        """Create the project completion event."""
        event = Event(
            scenario_id=scenario.id,
            event_time=event_time,
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
        db.session.add(event)


# Create the enhanced scenario
if __name__ == "__main__":
    with app.app_context():
        try:
            creator = EnhancedCase7Creator()
            scenario = creator.create_enhanced_scenario()
            
        except Exception as e:
            print(f"❌ Error creating enhanced scenario: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()