#!/usr/bin/env python3
"""View the properly structured Case 7 scenario."""

from app import create_app
from app.models import db
from app.models.scenario import Scenario
from app.models.event import Event, Action
from app.models.character import Character
from app.models.resource import Resource

app = create_app('config')

with app.app_context():
    try:
        # Get Scenario 6 (Proper Case 7)
        scenario = Scenario.query.get(6)
        if not scenario:
            print("❌ Scenario 6 not found")
            exit()
            
        print("=" * 100)
        print(f"📋 SCENARIO: {scenario.name}")
        print(f"   ID: {scenario.id}")
        print(f"   Description: {scenario.description}")
        print("=" * 100)
        
        # Show characters
        print(f"\n👥 CHARACTERS:")
        for char in scenario.characters:
            print(f"   🧑 {char.name} ({char.role})")
            if char.attributes.get('description'):
                print(f"      {char.attributes['description']}")
            if char.attributes.get('license_status'):
                print(f"      License: {char.attributes['license_status']}")
            if char.attributes.get('status'):
                print(f"      Status: {char.attributes['status']}")
            print()
        
        # Show resources
        print(f"\n📚 RESOURCES:")
        for resource in scenario.resources:
            print(f"   📁 {resource.name} ({resource.type})")
            print(f"      {resource.description}")
            print()
        
        # Get timeline elements (Events and Actions) sorted by time
        events = Event.query.filter_by(scenario_id=6).order_by(Event.event_time).all()
        actions = Action.query.filter_by(scenario_id=6, is_decision=True).order_by(Action.action_time).all()
        
        # Combine and sort by time
        timeline_items = []
        for event in events:
            timeline_items.append(('EVENT', event.event_time, event))
        for action in actions:
            timeline_items.append(('DECISION', action.action_time, action))
        
        timeline_items.sort(key=lambda x: x[1])
        
        print(f"\n📅 TIMELINE ({len(timeline_items)} items):")
        print("=" * 100)
        
        for item_type, time, item in timeline_items:
            if item_type == 'EVENT':
                print(f"\n🎬 EVENT: {item.parameters.get('title', 'Event')}")
                print(f"   Time: {time.strftime('%Y-%m-%d %H:%M')}")
                print(f"   Description: {item.description}")
                
                details = item.parameters.get('details', '')
                if details:
                    print(f"   Details: {details}")
                
                # Show additional parameters
                if 'scope' in item.parameters:
                    print(f"   Scope: {', '.join(item.parameters['scope'])}")
                if 'impact' in item.parameters:
                    print(f"   Impact: {item.parameters['impact']}")
                if 'tools_discovered' in item.parameters:
                    print(f"   Tools: {', '.join(item.parameters['tools_discovered'])}")
                if 'process_steps' in item.parameters:
                    print(f"   Process: {', '.join(item.parameters['process_steps'])}")
                if 'deliverables_completed' in item.parameters:
                    print(f"   Deliverables: {', '.join(item.parameters['deliverables_completed'])}")
                
                print("-" * 80)
                
            elif item_type == 'DECISION':
                decision_seq = item.parameters.get('decision_sequence', '?')
                print(f"\n⚖️  DECISION POINT {decision_seq}: {item.name}")
                print(f"   Time: {time.strftime('%Y-%m-%d %H:%M')}")
                print(f"   Question: {item.parameters.get('question_text', 'No question')}")
                print(f"   Context: {item.parameters.get('context', 'No context')}")
                
                # Show options
                options = item.parameters.get('options', [])
                if options:
                    print(f"   \n   💡 OPTIONS:")
                    for i, option in enumerate(options, 1):
                        print(f"      {i}. {option['title']}")
                        print(f"         {option['description']}")
                        print(f"         Analysis: {option['ethical_analysis']}")
                
                # Show NSPE conclusion
                nspe = item.parameters.get('nspe_conclusion', {})
                if nspe:
                    print(f"\n   🟢 NSPE CONCLUSION: {nspe.get('verdict', 'Unknown')}")
                    print(f"      Reasoning: {nspe.get('reasoning', 'No reasoning')}")
                    if 'correct_option' in nspe:
                        print(f"      Correct Choice: {nspe['correct_option']}")
                    if 'key_requirement' in nspe:
                        print(f"      Key Requirement: {nspe['key_requirement']}")
                    if 'additional_requirements' in nspe:
                        print(f"      Additional Requirements: {', '.join(nspe['additional_requirements'])}")
                
                print("-" * 80)
        
        print(f"\n📊 SUMMARY:")
        print(f"   Total Events: {len(events)}")
        print(f"   Total Decisions: {len(actions)}")
        print(f"   Characters: {len(scenario.characters)}")
        print(f"   Resources: {len(scenario.resources)}")
        print(f"   Timeline Span: 30 days")
        
        print(f"\n🌐 View in browser: http://localhost:3333/scenarios/6")
        
    except Exception as e:
        print(f"❌ Error viewing scenario: {e}")
        import traceback
        traceback.print_exc()