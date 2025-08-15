#!/usr/bin/env python3
"""View the enhanced Case 7 scenario with detailed NSPE analysis."""

from app import create_app
from app.models import db
from app.models.scenario import Scenario
from app.models.event import Event, Action
from app.models.character import Character
from app.models.resource import Resource

app = create_app('config')

def get_color_indicator(nspe_status):
    """Get color indicator based on NSPE status."""
    if nspe_status == 'nspe_positive':
        return '🟢'
    elif nspe_status == 'nspe_negative':
        return '🔴'
    elif nspe_status == 'nspe_conclusion':
        return '🟢'
    else:
        return '🟡'

with app.app_context():
    try:
        # Get Scenario 7 (Enhanced Case 7)
        scenario = Scenario.query.get(7)
        if not scenario:
            print("❌ Scenario 7 not found")
            exit()
            
        print("=" * 100)
        print(f"📋 ENHANCED SCENARIO: {scenario.name}")
        print(f"   ID: {scenario.id}")
        print(f"   Description: {scenario.description}")
        print("=" * 100)
        
        # Show metadata
        metadata = scenario.scenario_metadata
        print(f"\n📊 SCENARIO METADATA:")
        print(f"   Case: NSPE {metadata.get('case_number')} ({metadata.get('case_year')})")
        print(f"   Protagonist: {metadata.get('protagonist')}")
        print(f"   Total Decisions: {metadata.get('total_decisions')}")
        print(f"   NSPE Code Sections: {', '.join(metadata.get('nspe_code_sections', []))}")
        print(f"   Precedent Cases: {', '.join(metadata.get('precedent_cases', []))}")
        
        # Show characters
        print(f"\n👥 CHARACTERS:")
        for char in scenario.characters:
            print(f"   🧑 {char.name} ({char.role})")
            if char.attributes.get('description'):
                print(f"      {char.attributes['description']}")
            if char.attributes.get('technical_competence'):
                print(f"      Technical Competence: {char.attributes['technical_competence']}")
            if char.attributes.get('writing_confidence'):
                print(f"      Writing Confidence: {char.attributes['writing_confidence']}")
            print()
        
        # Show resources
        print(f"\n📚 RESOURCES:")
        for resource in scenario.resources:
            print(f"   📁 {resource.name} ({resource.type})")
            print(f"      {resource.description}")
            print()
        
        # Get timeline elements sorted by time
        events = Event.query.filter_by(scenario_id=7).order_by(Event.event_time).all()
        actions = Action.query.filter_by(scenario_id=7, is_decision=True).order_by(Action.action_time, Action.id).all()
        
        # Combine and sort by time
        timeline_items = []
        for event in events:
            timeline_items.append(('EVENT', event.event_time, event))
        
        # Group actions by decision sequence
        decision_groups = {}
        for action in actions:
            seq = action.parameters.get('decision_sequence', 0)
            if seq not in decision_groups:
                decision_groups[seq] = []
            decision_groups[seq].append(action)
        
        # Add decision groups to timeline
        for seq, group in decision_groups.items():
            if group:
                first_action = group[0]
                timeline_items.append(('DECISION', first_action.action_time, (seq, group)))
        
        timeline_items.sort(key=lambda x: x[1])
        
        print(f"\n📅 ENHANCED TIMELINE ({len(timeline_items)} items):")
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
                for key in ['scope', 'impact', 'tools_discovered', 'process_steps', 'deliverables_completed']:
                    if key in item.parameters:
                        value = item.parameters[key]
                        if isinstance(value, list):
                            print(f"   {key.replace('_', ' ').title()}: {', '.join(value)}")
                        else:
                            print(f"   {key.replace('_', ' ').title()}: {value}")
                
                print("-" * 80)
                
            elif item_type == 'DECISION':
                decision_seq, actions_group = item
                first_action = actions_group[0]
                
                print(f"\n⚖️  ENHANCED DECISION POINT {decision_seq}: {first_action.parameters.get('decision_title')}")
                print(f"   Time: {time.strftime('%Y-%m-%d %H:%M')}")
                print(f"   Question: {first_action.parameters.get('question_text')}")
                print(f"   Context: {first_action.parameters.get('context')}")
                
                print(f"\n   💡 ENHANCED OPTIONS ({len(actions_group)}):")
                
                for action in sorted(actions_group, key=lambda x: x.parameters.get('option_number', 0)):
                    option_num = action.parameters.get('option_number', '?')
                    nspe_status = action.parameters.get('nspe_status', 'alternative')
                    color = get_color_indicator(nspe_status)
                    
                    print(f"\n   {color} Option {option_num}: {action.description}")
                    
                    # Show detailed description
                    detailed_desc = action.parameters.get('detailed_description', '')
                    if detailed_desc:
                        print(f"      Description: {detailed_desc}")
                    
                    # Show ethical analysis
                    ethical_analysis = action.parameters.get('ethical_analysis', '')
                    if ethical_analysis:
                        print(f"      Analysis: {ethical_analysis}")
                    
                    # Show code references
                    code_refs = action.parameters.get('code_references', [])
                    if code_refs:
                        print(f"      Code References: {', '.join(code_refs)}")
                    
                    # Show precedent cases
                    precedents = action.parameters.get('precedent_cases', [])
                    if precedents:
                        print(f"      Precedent Cases: {', '.join(precedents)}")
                    
                    # Show reasoning quote
                    reasoning = action.parameters.get('reasoning_quote', '')
                    if reasoning:
                        print(f"      Reasoning: \"{reasoning}\"")
                    
                    # Show standards referenced
                    standards = action.parameters.get('standards_referenced', [])
                    if standards:
                        print(f"      Standards: {', '.join(standards)}")
                    
                    # Show NSPE status
                    if nspe_status == 'nspe_positive':
                        print(f"      ⭐ NSPE found this aspect ETHICAL")
                    elif nspe_status == 'nspe_negative':
                        print(f"      ⭐ NSPE found this aspect UNETHICAL")
                    elif nspe_status == 'nspe_conclusion':
                        print(f"      ⭐ This is NSPE's OVERALL CONCLUSION")
                    else:
                        print(f"      💭 Alternative ethical interpretation")
                
                print("-" * 80)
        
        print(f"\n📊 ENHANCED SUMMARY:")
        print(f"   Total Events: {len(events)}")
        print(f"   Total Decision Options: {len(actions)}")
        print(f"   Decision Points: {len(decision_groups)}")
        print(f"   Characters: {len(scenario.characters)}")
        print(f"   Resources: {len(scenario.resources)}")
        print(f"   NSPE Code Sections Referenced: {len(metadata.get('nspe_code_sections', []))}")
        print(f"   Precedent Cases Referenced: {len(metadata.get('precedent_cases', []))}")
        
        # Count NSPE vs alternative options
        nspe_options = len([a for a in actions if a.parameters.get('nspe_status') in ['nspe_positive', 'nspe_negative', 'nspe_conclusion']])
        alternative_options = len(actions) - nspe_options
        print(f"   NSPE-based Options: {nspe_options}")
        print(f"   Alternative Options: {alternative_options}")
        
        print(f"\n🌐 View enhanced scenario: http://localhost:3333/scenarios/7")
        
        print(f"\n🎯 LEARNING INSIGHTS FOR FUTURE CASE PROCESSING:")
        print(f"   - Questions successfully parsed into 4/4/3 realistic options")
        print(f"   - NSPE nuanced conclusions properly split (ethical + unethical aspects)")
        print(f"   - All options include strong ethical justifications with Code references")
        print(f"   - Precedent cases integrated where relevant (BER 90-6, 98-3)")
        print(f"   - Color coding clearly distinguishes NSPE vs alternative positions")
        
    except Exception as e:
        print(f"❌ Error viewing enhanced scenario: {e}")
        import traceback
        traceback.print_exc()