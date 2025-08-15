#!/usr/bin/env python3
"""
Fix Case 7 scenario to consolidate options under single decisions.
Instead of multiple Action entries, create one Action per decision with all options in the options field.
"""

from app import create_app
from app.models import db
from app.models.scenario import Scenario
from app.models.event import Event, Action
from datetime import datetime, timedelta

app = create_app('config')

class ConsolidatedCase7Fixer:
    """Fix Case 7 scenario to have consolidated decision options."""
    
    def fix_scenario_7(self):
        """Fix the existing Scenario 7 to consolidate options."""
        
        print("🔧 Fixing Scenario 7: Consolidating decision options")
        print("=" * 80)
        
        # Get existing scenario
        scenario = Scenario.query.get(7)
        if not scenario:
            print("❌ Scenario 7 not found")
            return
        
        print(f"✅ Found scenario: {scenario.name}")
        
        # Delete existing decision actions
        existing_actions = Action.query.filter_by(scenario_id=7, is_decision=True).all()
        print(f"🗑️  Deleting {len(existing_actions)} existing decision actions")
        for action in existing_actions:
            db.session.delete(action)
        
        # Create consolidated decisions
        base_time = datetime.now()
        self._create_consolidated_decision_1(scenario, base_time + timedelta(days=12))
        self._create_consolidated_decision_2(scenario, base_time + timedelta(days=18))
        self._create_consolidated_decision_3(scenario, base_time + timedelta(days=25))
        
        db.session.commit()
        
        print(f"\n✅ Fixed scenario 7 successfully!")
        print(f"   - 3 consolidated decisions created")
        print(f"   - Each decision contains all options in the options field")
        print(f"   URL: http://localhost:3333/scenarios/7")
    
    def _create_consolidated_decision_1(self, scenario, decision_time):
        """Create consolidated Decision 1: AI Report Text Ethics."""
        
        # All options for Decision 1
        options = [
            {
                'id': 'ethical_aspects',
                'title': 'Ethical aspects: Competent review maintained professional standards',
                'nspe_status': 'nspe_positive',
                'description': 'Engineer A was competent and thoroughly reviewed the AI-generated content, ensuring accuracy and compliance with professional standards.',
                'ethical_analysis': 'NSPE found this aspect ethical because Engineer A maintained professional competence through thorough review.',
                'code_references': ['I.2 (Perform services only in areas of their competence)'],
                'precedent_cases': ['BER Case 90-6: Established that engineers can use computer tools with proper oversight'],
                'reasoning_quote': 'Engineer A was competent and did thoroughly review and verify the AI-generated content, ensuring accuracy and compliance with professional standards',
                'color': 'green'
            },
            {
                'id': 'unethical_aspects',
                'title': 'Unethical aspects: Violated confidentiality and citation requirements',
                'nspe_status': 'nspe_negative',
                'description': 'Engineer A violated client confidentiality by feeding private data to external AI without permission and failed to document required technical citations.',
                'ethical_analysis': 'NSPE found this aspect unethical due to clear violations of confidentiality and professional attribution standards.',
                'code_references': ['II.1.c (Confidentiality of client information)', 'III.9 (Give credit for engineering work)'],
                'precedent_cases': [],
                'reasoning_quote': 'Engineer A did not obtain client permission to disclose private information, nor did Engineer A document required technical citations',
                'color': 'red'
            },
            {
                'id': 'completely_ethical',
                'title': 'Completely ethical - AI is just a writing tool',
                'nspe_status': 'alternative',
                'description': 'AI for text generation is like spell-check or grammar software - a professional writing aid that doesn\'t compromise engineering judgment.',
                'ethical_analysis': 'This view treats AI as standard professional software, emphasizing that Engineer A\'s expertise and review ensure quality.',
                'code_references': ['I.2 (Competence)'],
                'precedent_cases': ['BER Case 90-6: Supported technology use with engineer oversight'],
                'reasoning_quote': 'Professional writing aids don\'t compromise engineering responsibility when properly supervised',
                'color': 'yellow'
            },
            {
                'id': 'completely_unethical',
                'title': 'Completely unethical - Cannot delegate technical writing',
                'nspe_status': 'alternative',
                'description': 'Professional engineering reports must be personally authored to maintain accountability and professional responsibility.',
                'ethical_analysis': 'This strict interpretation holds that AI generation compromises professional responsibility regardless of review quality.',
                'code_references': ['II.2.b (Personal direction and control)'],
                'precedent_cases': [],
                'reasoning_quote': 'Professional engineering work products must be under complete personal direction and control',
                'color': 'yellow'
            }
        ]
        
        action = Action(
            scenario_id=scenario.id,
            name="AI Report Text Ethics Decision",
            description="Should Engineer A use AI to create the report text, and was this approach ethical?",
            action_type="ethical_decision",
            is_decision=True,
            action_time=decision_time,
            options=options,  # Store all options in the options field
            parameters={
                'decision_sequence': 1,
                'decision_title': 'AI Report Text Ethics',
                'question_text': "Was Engineer A's use of AI to create the report text ethical, given that Engineer A thoroughly checked the report?",
                'context': 'Engineer A needs to create a comprehensive report but lacks confidence in technical writing and no longer has Engineer B\'s support.',
                'total_options': len(options),
                'nspe_aspects': {
                    'positive': 'Competent review maintained professional standards',
                    'negative': 'Violated confidentiality and citation requirements'
                }
            }
        )
        db.session.add(action)
        print(f"   ✅ Decision 1: {len(options)} options consolidated")
    
    def _create_consolidated_decision_2(self, scenario, decision_time):
        """Create consolidated Decision 2: AI Design Document Ethics."""
        
        options = [
            {
                'id': 'ethical_tool_use',
                'title': 'Ethical tool use: AI drafting tools are like advanced CAD',
                'nspe_status': 'alternative',
                'description': 'AI-assisted drafting is similar to computer-aided design tools already accepted in engineering practice.',
                'ethical_analysis': 'This view treats AI drafting as an evolution of established CAD technology, with engineer competence validating output.',
                'code_references': ['I.2 (Competence)'],
                'precedent_cases': ['BER Case 90-6: Established acceptability of computer drafting tools with engineer review'],
                'reasoning_quote': 'Computer-aided design tools with proper engineer oversight have established precedent',
                'color': 'yellow'
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
                'standards_referenced': ['NSPE Position Statement 10-1778 (Responsible Charge definition)'],
                'color': 'red'
            },
            {
                'id': 'adequate_review',
                'title': 'Ethical with adequate review - High-level review sufficient',
                'nspe_status': 'alternative',
                'description': 'Engineer\'s professional competence and high-level review ensure document quality and meet professional standards.',
                'ethical_analysis': 'This position holds that a licensed engineer\'s review validates technical content regardless of generation method.',
                'code_references': ['I.2 (Competence)'],
                'precedent_cases': [],
                'reasoning_quote': 'Professional competence and review validate technical content quality',
                'color': 'yellow'
            },
            {
                'id': 'personal_creation_required',
                'title': 'Unethical regardless - Design documents require personal creation',
                'nspe_status': 'alternative',
                'description': 'Documents requiring professional seal must be under complete personal direction and control from creation to completion.',
                'ethical_analysis': 'This strict interpretation requires that sealed documents represent entirely personal professional work.',
                'code_references': ['II.2.b (Personal direction and control)'],
                'precedent_cases': [],
                'reasoning_quote': 'Professional seal implies engineer personally directed all design work from conception',
                'color': 'yellow'
            }
        ]
        
        action = Action(
            scenario_id=scenario.id,
            name="AI Design Document Ethics Decision",
            description="Should Engineer A use AI-assisted drafting tools for engineering design documents, and was this approach ethical?",
            action_type="ethical_decision",
            is_decision=True,
            action_time=decision_time,
            options=options,
            parameters={
                'decision_sequence': 2,
                'decision_title': 'AI Design Document Ethics',
                'question_text': "Was Engineer A's use of AI-assisted drafting tools to create the engineering design documents ethical, given that Engineer A reviewed the design at a high level?",
                'context': 'Engineer A needs to create engineering design documents (plans and specifications) for groundwater infrastructure modifications.',
                'total_options': len(options),
                'nspe_concern': 'Failed to maintain Responsible Charge over AI output before sealing documents'
            }
        )
        db.session.add(action)
        print(f"   ✅ Decision 2: {len(options)} options consolidated")
    
    def _create_consolidated_decision_3(self, scenario, decision_time):
        """Create consolidated Decision 3: AI Disclosure Ethics."""
        
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
                'current_state': 'No universal guideline mandating AI disclosure in engineering work',
                'color': 'green'
            },
            {
                'id': 'must_disclose',
                'title': 'Must disclose - Client has right to know methodology',
                'nspe_status': 'alternative',
                'description': 'Clients should be informed about significant tools and methods affecting their project to maintain trust and transparency.',
                'ethical_analysis': 'This position emphasizes client rights and transparency, viewing AI disclosure as preventing deception.',
                'code_references': ['I.5 (Avoid deceptive acts)', 'III.3 (Avoid conduct deceiving the public)'],
                'precedent_cases': [],
                'reasoning_quote': 'Full disclosure prevents any perception of deception and honors client relationship',
                'color': 'yellow'
            },
            {
                'id': 'no_disclosure_needed',
                'title': 'No disclosure needed - AI is standard professional software',
                'nspe_status': 'alternative',
                'description': 'AI tools are professional software like CAD, analysis programs, or design databases - routine tools that don\'t require client disclosure.',
                'ethical_analysis': 'This view treats AI as standard professional software, similar to other computational tools routinely used without disclosure.',
                'code_references': [],
                'precedent_cases': ['BER Case 90-6 (CADD systems)', 'BER Case 98-3 (CD-ROM tools) - software tools don\'t require client disclosure'],
                'reasoning_quote': 'Engineers routinely use software tools without disclosing every program to clients',
                'color': 'yellow'
            }
        ]
        
        action = Action(
            scenario_id=scenario.id,
            name="AI Disclosure Ethics Decision",
            description="Should Engineer A disclose the use of AI to Client W, and what are the ethical obligations around disclosure?",
            action_type="ethical_decision",
            is_decision=True,
            action_time=decision_time,
            options=options,
            parameters={
                'decision_sequence': 3,
                'decision_title': 'AI Disclosure Ethics',
                'question_text': "If the use of AI was acceptable, did Engineer A have an ethical obligation to disclose the use of AI in any form to the Client?",
                'context': 'Engineer A has completed both deliverables using AI assistance and must decide whether to inform Client W about the AI usage.',
                'total_options': len(options),
                'nspe_conclusion': 'No obligation, but transparency favored when AI plays substantial role'
            }
        )
        db.session.add(action)
        print(f"   ✅ Decision 3: {len(options)} options consolidated")


# Fix the scenario
if __name__ == "__main__":
    with app.app_context():
        try:
            fixer = ConsolidatedCase7Fixer()
            fixer.fix_scenario_7()
            
        except Exception as e:
            print(f"❌ Error fixing scenario: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()