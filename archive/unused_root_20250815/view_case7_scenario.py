#!/usr/bin/env python3
"""View the Case 7 scenario that was just created."""

from app import create_app
from app.models import db
from app.models.scenario import Scenario
from app.models.event import Action
import json

app = create_app('config')

with app.app_context():
    try:
        # Get Scenario 5 (Case 7 AI Ethics)
        scenario = Scenario.query.get(5)
        if not scenario:
            print("❌ Scenario 5 not found")
            exit()
            
        print("=" * 100)
        print(f"📋 SCENARIO: {scenario.name}")
        print(f"   ID: {scenario.id}")
        print(f"   Description: {scenario.description}")
        print(f"   World: {scenario.world.name}")
        print(f"   Created: {scenario.created_at}")
        print("=" * 100)
        
        # Show metadata
        if scenario.scenario_metadata:
            print("\n🎯 SCENARIO METADATA:")
            print(f"   Wizard Mode: {scenario.scenario_metadata.get('wizard_mode', False)}")
            print(f"   Protagonist: {scenario.scenario_metadata.get('protagonist', 'Unknown')}")
            print(f"   Case ID: {scenario.scenario_metadata.get('case_id', 'Unknown')}")
            print(f"   Decision Style: {scenario.scenario_metadata.get('decision_style', 'Unknown')}")
            print(f"   NSPE Conclusions Included: {scenario.scenario_metadata.get('nspe_conclusions_included', False)}")
            
            # Show ethical context
            ethical_context = scenario.scenario_metadata.get('ethical_context', {})
            if ethical_context:
                print(f"\n⚖️  ETHICAL CONTEXT:")
                for key, value in ethical_context.items():
                    print(f"   - {key.replace('_', ' ').title()}: {value}")
            
            # Show interactive timeline
            timeline = scenario.scenario_metadata.get('interactive_timeline', [])
            if timeline:
                print(f"\n📅 INTERACTIVE TIMELINE ({len(timeline)} decision points):")
                print("-" * 100)
                
                for item in timeline:
                    print(f"\n   📍 Decision {item['sequence']}: {item['title']}")
                    print(f"      Decision ID: {item['decision_id']}")
                    print(f"      Protagonist: {item['protagonist']}")
                    print(f"      Decision Type: {item['decision_type']}")
                    
                    if item.get('question'):
                        print(f"\n      ❓ QUESTION:")
                        print(f"         {item['question']}")
                    
                    if item.get('narrative_setup'):
                        print(f"\n      📖 NARRATIVE:")
                        print(f"         {item['narrative_setup'][:150]}...")
                    
                    if item.get('ethical_principles'):
                        print(f"\n      ⚖️  PRINCIPLES:")
                        for principle in item['ethical_principles'][:2]:  # Show first 2
                            print(f"         - {principle}")
                        if len(item['ethical_principles']) > 2:
                            print(f"         ... and {len(item['ethical_principles']) - 2} more")
                    
                    if item.get('options'):
                        print(f"\n      💡 OPTIONS ({len(item['options'])}):")
                        for opt in item['options']:
                            nspe_marker = "🟢" if opt.get('is_nspe_conclusion') else "  "
                            print(f"         {nspe_marker} • {opt['title']} (Score: {opt.get('ethical_score', 0):.1f})")
                            if opt.get('is_nspe_conclusion'):
                                print(f"              ⭐ NSPE's Conclusion")
                    
                    print("-" * 100)
        
        # Get decision actions
        decision_actions = Action.query.filter_by(scenario_id=5, is_decision=True).all()
        
        print(f"\n🎮 DECISION ACTIONS ({len(decision_actions)} total):")
        print("=" * 100)
        
        # Group by sequence number
        decisions_by_sequence = {}
        for action in decision_actions:
            seq = action.parameters.get('sequence_number', 0)
            if seq not in decisions_by_sequence:
                decisions_by_sequence[seq] = []
            decisions_by_sequence[seq].append(action)
        
        for seq in sorted(decisions_by_sequence.keys()):
            actions = decisions_by_sequence[seq]
            if actions:
                first_action = actions[0]
                print(f"\n📋 DECISION {seq}:")
                print(f"   Question: {first_action.parameters.get('question_text', 'No question')[:80]}...")
                
                for i, action in enumerate(actions, 1):
                    is_nspe = action.parameters.get('is_nspe_conclusion', False)
                    nspe_marker = "🟢" if is_nspe else "  "
                    print(f"\n   {nspe_marker} Option {i}: {action.name}")
                    print(f"      Justification: {action.description}")
                    if is_nspe:
                        print(f"      ⭐ This is NSPE's conclusion")
        
        # Show characters
        print(f"\n👥 CHARACTERS ({len(scenario.characters)}):")
        for char in scenario.characters:
            print(f"   - {char.name} ({char.role})")
            if char.attributes and char.attributes.get('description'):
                print(f"     {char.attributes['description']}")
        
        # Show resources
        if scenario.resources:
            print(f"\n📚 RESOURCES ({len(scenario.resources)}):")
            for res in scenario.resources[:3]:  # Show first 3
                print(f"   - {res.name}: {res.description[:80]}...")
        
        print("\n✅ Case 7 scenario displayed successfully!")
        print(f"\n🌐 View in browser: http://localhost:3333/scenarios/5")
        
    except Exception as e:
        print(f"❌ Error viewing scenario: {e}")
        import traceback
        traceback.print_exc()