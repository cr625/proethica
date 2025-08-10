#!/usr/bin/env python3
"""Update Scenario 1 with enhanced decision points from the updated deconstructed case."""

from app import create_app
from app.models import db
from app.models.scenario import Scenario
from app.models.deconstructed_case import DeconstructedCase
from app.models.event import Action
from app.services.scenario_population_service import ScenarioPopulationService

app = create_app('config')

with app.app_context():
    try:
        # Get Scenario 1 and the deconstructed case
        scenario = Scenario.query.get(1)
        deconstructed_case = DeconstructedCase.query.filter_by(case_id=8).first()
        
        if not scenario or not deconstructed_case:
            print("❌ Scenario 1 or deconstructed case not found")
            exit()
            
        print(f"📋 Updating Scenario: {scenario.name}")
        print(f"   Using deconstructed case: {deconstructed_case.id}")
        print("=" * 80)
        
        # Clear existing decision actions
        existing_decisions = Action.query.filter_by(scenario_id=1, is_decision=True).all()
        print(f"🗑️  Removing {len(existing_decisions)} old decision actions")
        for action in existing_decisions:
            db.session.delete(action)
        
        # Add new decision actions from enhanced decision points
        print("\n➕ Adding enhanced decision actions:")
        for i, dp in enumerate(deconstructed_case.decision_points):
            print(f"\n📋 Decision {i+1}: {dp.get('title', 'Unknown')}")
            print(f"   Question: {dp.get('question_text', 'No question')[:80]}...")
            print(f"   Protagonist: {dp.get('protagonist', 'Unknown')}")
            
            # Create decision action
            for j, option in enumerate(dp.get('primary_options', [])):
                action = Action(
                    scenario_id=scenario.id,
                    name=option.get('title', f'Option {j+1}'),
                    description=option.get('ethical_justification', ''),
                    action_type=dp.get('decision_type', 'ethical_decision'),
                    is_decision=True,
                    parameters={
                        'decision_id': dp.get('decision_id'),
                        'sequence_number': dp.get('sequence_number', i+1),
                        'protagonist': dp.get('protagonist', 'Engineer'),
                        'question_text': dp.get('question_text', ''),
                        'narrative_setup': dp.get('narrative_setup', ''),
                        'option_id': option.get('option_id'),
                        'ethical_principles': dp.get('ethical_principles', []),
                        'context_factors': dp.get('context_factors', []),
                        'case_sections': dp.get('case_sections', {})
                    }
                )
                db.session.add(action)
                print(f"     ✅ Added: {option.get('title', 'Unknown option')}")
        
        # Update scenario metadata with interactive timeline
        if not scenario.scenario_metadata:
            scenario.scenario_metadata = {}
            
        # Create interactive timeline from decision points
        interactive_timeline = []
        for i, dp in enumerate(deconstructed_case.decision_points):
            timeline_item = {
                'sequence': i + 1,
                'title': dp.get('title', f'Decision {i+1}'),
                'description': dp.get('description', ''),
                'question': dp.get('question_text', ''),
                'protagonist': dp.get('protagonist', 'Engineer'),
                'narrative_setup': dp.get('narrative_setup', ''),
                'decision_type': dp.get('decision_type', 'ethical_decision'),
                'ethical_principles': dp.get('ethical_principles', []),
                'options': [
                    {
                        'id': opt.get('option_id', f'opt_{j}'),
                        'title': opt.get('title', f'Option {j+1}'),
                        'description': opt.get('ethical_justification', ''),
                        'ethical_score': 0.7  # Default score
                    }
                    for j, opt in enumerate(dp.get('primary_options', []))
                ],
                'context_factors': dp.get('context_factors', []),
                'urgency': dp.get('urgency_level', 0.5),
                'complexity': dp.get('complexity_level', 0.5)
            }
            interactive_timeline.append(timeline_item)
        
        scenario.scenario_metadata['interactive_timeline'] = interactive_timeline
        scenario.scenario_metadata['wizard_mode'] = True
        scenario.scenario_metadata['protagonist'] = 'Engineer L'
        
        db.session.commit()
        
        print("\n✅ Scenario updated successfully!")
        print(f"   - Added {len(deconstructed_case.decision_points) * 3} decision actions")
        print(f"   - Created interactive timeline with {len(interactive_timeline)} decision points")
        print(f"   - Enabled wizard mode with protagonist: Engineer L")
        
    except Exception as e:
        print(f"❌ Error updating scenario: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()