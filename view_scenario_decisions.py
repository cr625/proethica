#!/usr/bin/env python3
"""View the enhanced decision content in Scenario 1."""

from app import create_app
from app.models import db
from app.models.scenario import Scenario
from app.models.event import Action
import json

app = create_app('config')

with app.app_context():
    try:
        # Get Scenario 1
        scenario = Scenario.query.get(1)
        if not scenario:
            print("❌ Scenario 1 not found")
            exit()
            
        print("=" * 100)
        print(f"📋 SCENARIO: {scenario.name}")
        print(f"   ID: {scenario.id}")
        print(f"   World: {scenario.world.name}")
        print(f"   Created: {scenario.created_at}")
        print("=" * 100)
        
        # Show metadata
        if scenario.scenario_metadata:
            print("\n🎯 SCENARIO METADATA:")
            print(f"   Wizard Mode: {scenario.scenario_metadata.get('wizard_mode', False)}")
            print(f"   Protagonist: {scenario.scenario_metadata.get('protagonist', 'Unknown')}")
            
            # Show interactive timeline
            timeline = scenario.scenario_metadata.get('interactive_timeline', [])
            if timeline:
                print(f"\n📅 INTERACTIVE TIMELINE ({len(timeline)} decision points):")
                print("-" * 100)
                
                for item in timeline:
                    print(f"\n   📍 Sequence {item['sequence']}: {item['title']}")
                    print(f"      Protagonist: {item['protagonist']}")
                    print(f"      Decision Type: {item['decision_type']}")
                    print(f"      Urgency: {item['urgency']:.1f} | Complexity: {item['complexity']:.1f}")
                    
                    if item.get('question'):
                        print(f"\n      ❓ QUESTION:")
                        print(f"         {item['question']}")
                    
                    if item.get('narrative_setup'):
                        print(f"\n      📖 NARRATIVE SETUP:")
                        print(f"         {item['narrative_setup']}")
                    
                    if item.get('ethical_principles'):
                        print(f"\n      ⚖️  ETHICAL PRINCIPLES:")
                        for principle in item['ethical_principles']:
                            print(f"         - {principle}")
                    
                    if item.get('context_factors'):
                        print(f"\n      🔍 CONTEXT FACTORS:")
                        for factor in item['context_factors']:
                            print(f"         - {factor}")
                    
                    if item.get('options'):
                        print(f"\n      💡 OPTIONS ({len(item['options'])}):")
                        for opt in item['options']:
                            print(f"         • {opt['title']} (ID: {opt['id']})")
                            if opt.get('description'):
                                print(f"           {opt['description']}")
                    
                    print("-" * 100)
        
        # Get decision actions
        decision_actions = Action.query.filter_by(scenario_id=1, is_decision=True).all()
        
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
                print(f"   Decision ID: {first_action.parameters.get('decision_id', 'Unknown')}")
                print(f"   Protagonist: {first_action.parameters.get('protagonist', 'Unknown')}")
                
                question = first_action.parameters.get('question_text', '')
                if question:
                    print(f"\n   ❓ QUESTION:")
                    print(f"      {question}")
                
                narrative = first_action.parameters.get('narrative_setup', '')
                if narrative:
                    print(f"\n   📖 NARRATIVE:")
                    print(f"      {narrative}")
                
                print(f"\n   🎯 OPTIONS:")
                for i, action in enumerate(actions, 1):
                    print(f"\n      Option {i}: {action.name}")
                    print(f"         Type: {action.action_type}")
                    if action.description:
                        print(f"         Justification: {action.description}")
                    
                    # Show ethical principles if present
                    principles = action.parameters.get('ethical_principles', [])
                    if principles:
                        print(f"         Ethical Principles: {', '.join(principles)}")
                    
                    # Show case sections if present
                    sections = action.parameters.get('case_sections', {})
                    if sections:
                        print(f"         Related Case Sections: {', '.join(sections.keys())}")
                
                print("-" * 80)
        
        # Show summary
        print(f"\n📊 SUMMARY:")
        print(f"   Total Decision Actions: {len(decision_actions)}")
        print(f"   Decision Points: {len(decisions_by_sequence)}")
        print(f"   Interactive Timeline Items: {len(scenario.scenario_metadata.get('interactive_timeline', []))}")
        print(f"   Wizard Mode: {'✅ Enabled' if scenario.scenario_metadata.get('wizard_mode') else '❌ Disabled'}")
        
        print("\n✅ Scenario content displayed successfully!")
        
    except Exception as e:
        print(f"❌ Error viewing scenario: {e}")
        import traceback
        traceback.print_exc()