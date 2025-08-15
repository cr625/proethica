#!/usr/bin/env python3
"""
Direct scenario creation from deconstructed cases.
This bypasses the template layer and creates playable scenarios immediately.
"""

from app import create_app
from app.models import db
from app.models.scenario import Scenario
from app.models.deconstructed_case import DeconstructedCase
from app.models.event import Event, Action
from app.models.character import Character
from app.models.resource import Resource
from app.models.condition import Condition
from sqlalchemy.exc import IntegrityError
import json

app = create_app('config')

class DirectScenarioCreator:
    """Create scenarios directly from deconstructed cases."""
    
    def create_scenario_from_deconstructed_case(self, deconstructed_case_id: int) -> Scenario:
        """Create a playable scenario directly from a deconstructed case."""
        
        # Get the deconstructed case
        deconstructed = DeconstructedCase.query.get(deconstructed_case_id)
        if not deconstructed:
            raise ValueError(f"Deconstructed case {deconstructed_case_id} not found")
        
        case = deconstructed.case
        print(f"Creating scenario from: {case.title}")
        
        # Create the scenario
        scenario = Scenario(
            name=f"Interactive Scenario: {case.title}",
            description=f"An interactive ethical decision-making scenario based on {case.title}. "
                       f"You will step into the role of the protagonist and make key decisions.",
            world_id=case.world_id
        )
        
        # Set up scenario metadata for wizard mode
        scenario.scenario_metadata = {
            'wizard_mode': True,
            'case_id': case.id,
            'deconstructed_case_id': deconstructed.id,
            'interactive_timeline': [],
            'protagonist': None,
            'decision_style': 'question_based',
            'nspe_conclusions_included': True
        }
        
        db.session.add(scenario)
        db.session.flush()  # Get scenario ID
        
        # Process stakeholders as characters
        protagonist = None
        for stakeholder_data in deconstructed.stakeholders:
            character = Character(
                scenario_id=scenario.id,
                name=stakeholder_data.get('name', 'Unknown'),
                role=stakeholder_data.get('role', 'professional'),
                attributes={
                    'description': stakeholder_data.get('description', ''),
                    'interests': stakeholder_data.get('interests', []),
                    'power_level': stakeholder_data.get('power_level', 0.5),
                    'influence_level': stakeholder_data.get('influence_level', 0.5)
                }
            )
            db.session.add(character)
            
            # Identify protagonist
            if 'engineer' in character.name.lower() and not protagonist:
                protagonist = character.name
        
        scenario.scenario_metadata['protagonist'] = protagonist or 'Engineer'
        
        # Create timeline and decision actions from decision points
        timeline = []
        for i, dp in enumerate(deconstructed.decision_points):
            # Create timeline entry
            timeline_item = {
                'sequence': i + 1,
                'decision_id': dp.get('decision_id', f'decision_{i+1}'),
                'title': dp.get('title', f'Decision {i+1}'),
                'description': dp.get('description', ''),
                'question': dp.get('question_text', ''),
                'protagonist': dp.get('protagonist', protagonist),
                'narrative_setup': dp.get('narrative_setup', ''),
                'decision_type': dp.get('decision_type', 'ethical_decision'),
                'ethical_principles': dp.get('ethical_principles', []),
                'context_factors': dp.get('context_factors', []),
                'urgency': dp.get('urgency_level', 0.5),
                'complexity': dp.get('complexity_level', 0.5),
                'options': []
            }
            
            # Create decision actions for each option
            for j, option in enumerate(dp.get('primary_options', [])):
                # Check if this is the NSPE conclusion
                is_nspe_conclusion = option.get('alignment_with_principles', {}).get('nspe_conclusion', 0) == 1.0
                
                action = Action(
                    scenario_id=scenario.id,
                    name=option.get('title', f'Option {j+1}'),
                    description=option.get('ethical_justification', ''),
                    action_type=dp.get('decision_type', 'ethical_decision'),
                    is_decision=True,
                    parameters={
                        'decision_id': dp.get('decision_id'),
                        'sequence_number': i + 1,
                        'option_id': option.get('option_id', f'option_{j+1}'),
                        'protagonist': dp.get('protagonist', protagonist),
                        'question_text': dp.get('question_text', ''),
                        'narrative_setup': dp.get('narrative_setup', ''),
                        'ethical_principles': dp.get('ethical_principles', []),
                        'context_factors': dp.get('context_factors', []),
                        'case_sections': dp.get('case_sections', {}),
                        'is_nspe_conclusion': is_nspe_conclusion,
                        'alignment_with_principles': option.get('alignment_with_principles', {})
                    }
                )
                db.session.add(action)
                
                # Add option to timeline
                timeline_option = {
                    'id': option.get('option_id', f'option_{j+1}'),
                    'title': option.get('title', f'Option {j+1}'),
                    'description': option.get('ethical_justification', ''),
                    'is_nspe_conclusion': is_nspe_conclusion,
                    'ethical_score': 0.8 if is_nspe_conclusion else 0.5
                }
                timeline_item['options'].append(timeline_option)
            
            timeline.append(timeline_item)
        
        # Store the interactive timeline
        scenario.scenario_metadata['interactive_timeline'] = timeline
        
        # Create initial event (scenario start)
        start_event = Event(
            scenario_id=scenario.id,
            description=f"You are {protagonist}, facing an ethical dilemma that will test your professional judgment.",
            parameters={
                'event_type': 'scenario_start',
                'event_name': 'Scenario Start',
                'protagonist': protagonist,
                'case_title': case.title,
                'case_number': case.doc_metadata.get('case_number', 'Unknown')
            }
        )
        db.session.add(start_event)
        
        # Add any relevant resources from case facts
        if deconstructed.reasoning_chain:
            facts = deconstructed.reasoning_chain.get('case_facts', [])
            for i, fact in enumerate(facts[:3]):  # Limit to first 3 facts as resources
                resource = Resource(
                    scenario_id=scenario.id,
                    name=f"Case Fact {i+1}",
                    type='information',
                    description=fact[:200] + '...' if len(fact) > 200 else fact
                )
                db.session.add(resource)
        
        # Store ethical context in scenario metadata instead of conditions
        scenario.scenario_metadata['ethical_context'] = {
            'professional_responsibility': 'Your duty to uphold professional standards',
            'public_safety': 'The paramount obligation to protect public welfare',
            'client_relationship': 'Your contractual obligations to the client'
        }
        
        db.session.commit()
        
        print(f"✅ Created scenario {scenario.id}: {scenario.name}")
        print(f"   - {len(timeline)} decision points")
        print(f"   - {len(deconstructed.stakeholders)} characters")
        print(f"   - Protagonist: {protagonist}")
        print(f"   - Wizard mode: enabled")
        
        return scenario


# Test with Case 7
if __name__ == "__main__":
    with app.app_context():
        try:
            # Find the most recent deconstructed case for Case 7
            deconstructed = DeconstructedCase.query.filter_by(case_id=7).order_by(
                DeconstructedCase.created_at.desc()
            ).first()
            
            if not deconstructed:
                print("❌ No deconstructed case found for Case 7")
                exit()
            
            print(f"Found deconstructed case {deconstructed.id} for Case 7")
            
            creator = DirectScenarioCreator()
            scenario = creator.create_scenario_from_deconstructed_case(deconstructed.id)
            
            print(f"\n🎮 Scenario created successfully!")
            print(f"   URL: http://localhost:3333/scenarios/{scenario.id}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()