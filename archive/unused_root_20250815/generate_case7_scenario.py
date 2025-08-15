#!/usr/bin/env python3
"""Generate an interactive scenario from Case 7 with enhanced decision points."""

from app import create_app
from app.models import db, Document, World
from app.services.case_to_scenario_service import CaseToScenarioService

app = create_app('config')

with app.app_context():
    try:
        print("🎯 Generating Interactive Scenario from Case 7: AI Ethics")
        print("=" * 80)
        
        # Get Case 7
        case = Document.query.get(7)
        if not case:
            print("❌ Case 7 not found")
            exit()
        
        print(f"📋 Case: {case.title}")
        print(f"   Document Type: {case.document_type}")
        print(f"   World: {case.world.name}")
        
        # Get engineering world
        engineering_world = World.query.filter_by(name='Engineering').first()
        if not engineering_world:
            print("❌ Engineering world not found")
            exit()
        
        print(f"   Target World: {engineering_world.name}")
        print()
        
        # Use CaseToScenarioService to generate scenario
        service = CaseToScenarioService()
        
        print("🔄 Deconstructing case with enhanced decision extraction...")
        # First deconstruct the case
        deconstructed_case = service.deconstruct_case_sync(case)
        
        if not deconstructed_case:
            print("❌ Failed to deconstruct case")
            exit()
        
        print(f"✅ Case deconstructed successfully!")
        print(f"   Decision Points: {len(deconstructed_case.decision_points)}")
        print(f"   Stakeholders: {len(deconstructed_case.stakeholders)}")
        
        # Show decision points preview
        print(f"\n🎯 DECISION POINTS PREVIEW:")
        for i, dp in enumerate(deconstructed_case.decision_points, 1):
            print(f"   {i}. {dp.get('title', 'Unknown Decision')}")
            print(f"      Question: {dp.get('question_text', 'No question')[:60]}...")
            print(f"      Options: {len(dp.get('primary_options', []))}")
            
            # Check for NSPE conclusions
            nspe_options = [opt for opt in dp.get('primary_options', []) 
                          if opt.get('alignment_with_principles', {}).get('nspe_conclusion')]
            if nspe_options:
                print(f"      🟢 NSPE Conclusion: {nspe_options[0].get('title')}")
            print()
        
        print("🔄 Generating scenario from deconstructed case...")
        # Generate scenario template first
        scenario_template = service.generate_scenario_from_deconstruction(deconstructed_case)
        
        if scenario_template:
            print(f"✅ Scenario template generated!")
            print(f"   Template ID: {scenario_template.id}")
            print(f"   Template Title: {scenario_template.title}")
            print(f"   Template Description: {scenario_template.description}")
            
            # Show template data preview
            if scenario_template.template_data:
                template_data = scenario_template.template_data
                print(f"   Decision Points in Template: {len(template_data.get('decision_points', []))}")
                print(f"   Learning Objectives: {len(template_data.get('learning_objectives', []))}")
            
            # For now, we'll work with the deconstructed case directly since we have enhanced it
            scenario = None  # Would need scenario creation from template
        else:
            print("❌ Failed to generate scenario template")
            scenario = None
        
        if scenario:
            print(f"✅ Scenario created successfully!")
            print(f"   Scenario ID: {scenario.id}")
            print(f"   Name: {scenario.name}")
            print(f"   URL: http://localhost:3333/scenarios/{scenario.id}")
            
            # Show scenario metadata
            if scenario.scenario_metadata:
                timeline = scenario.scenario_metadata.get('interactive_timeline', [])
                print(f"   Interactive Timeline: {len(timeline)} decision points")
                print(f"   Wizard Mode: {scenario.scenario_metadata.get('wizard_mode', False)}")
                print(f"   Protagonist: {scenario.scenario_metadata.get('protagonist', 'Unknown')}")
            
            # Show actions created
            decision_actions = [action for action in scenario.actions if action.is_decision]
            print(f"   Decision Actions: {len(decision_actions)}")
            
            print(f"\n🎮 SCENARIO ACTIONS CREATED:")
            actions_by_sequence = {}
            for action in decision_actions:
                seq = action.parameters.get('sequence_number', 0)
                if seq not in actions_by_sequence:
                    actions_by_sequence[seq] = []
                actions_by_sequence[seq].append(action)
            
            for seq in sorted(actions_by_sequence.keys()):
                actions = actions_by_sequence[seq]
                if actions:
                    first_action = actions[0]
                    question = first_action.parameters.get('question_text', 'No question')
                    print(f"\n   Decision {seq}: {question[:60]}...")
                    for i, action in enumerate(actions, 1):
                        nspe_marker = "🟢" if action.parameters.get('alignment_with_principles', {}).get('nspe_conclusion') else "  "
                        print(f"      {nspe_marker} {i}. {action.name}")
        else:
            print("❌ Failed to create scenario")
        
        print("\n✅ Case 7 scenario generation completed!")
        
    except Exception as e:
        print(f"❌ Error generating scenario: {e}")
        import traceback
        traceback.print_exc()