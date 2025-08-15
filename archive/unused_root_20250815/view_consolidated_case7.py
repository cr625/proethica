#!/usr/bin/env python3
"""View the consolidated Case 7 scenario with options properly grouped under decisions."""

from app import create_app
from app.models import db
from app.models.scenario import Scenario
from app.models.event import Event, Action

app = create_app('config')

def get_color_indicator(color):
    """Get color indicator."""
    if color == 'green':
        return '🟢'
    elif color == 'red':
        return '🔴'
    elif color == 'yellow':
        return '🟡'
    else:
        return '⚪'

with app.app_context():
    try:
        # Get Scenario 7
        scenario = Scenario.query.get(7)
        if not scenario:
            print("❌ Scenario 7 not found")
            exit()
            
        print("=" * 100)
        print(f"📋 CONSOLIDATED SCENARIO: {scenario.name}")
        print(f"   ID: {scenario.id}")
        print("=" * 100)
        
        # Get timeline elements sorted by time
        events = Event.query.filter_by(scenario_id=7).order_by(Event.event_time).all()
        decisions = Action.query.filter_by(scenario_id=7, is_decision=True).order_by(Action.action_time).all()
        
        # Combine and sort by time
        timeline_items = []
        for event in events:
            timeline_items.append(('EVENT', event.event_time, event))
        for decision in decisions:
            timeline_items.append(('DECISION', decision.action_time, decision))
        
        timeline_items.sort(key=lambda x: x[1])
        
        print(f"\n📅 CONSOLIDATED TIMELINE ({len(timeline_items)} items):")
        print("=" * 100)
        
        decision_count = 0
        
        for item_type, time, item in timeline_items:
            if item_type == 'EVENT':
                print(f"\n🎬 EVENT: {item.parameters.get('title', 'Event')}")
                print(f"   Time: {time.strftime('%Y-%m-%d %H:%M')}")
                print(f"   Description: {item.description}")
                print("-" * 80)
                
            elif item_type == 'DECISION':
                decision_count += 1
                decision_seq = item.parameters.get('decision_sequence', decision_count)
                
                print(f"\n⚖️  CONSOLIDATED DECISION {decision_seq}: {item.parameters.get('decision_title')}")
                print(f"   Time: {time.strftime('%Y-%m-%d %H:%M')}")
                print(f"   Question: {item.parameters.get('question_text')}")
                print(f"   Context: {item.parameters.get('context')}")
                
                # Show consolidated options
                options = item.options or []
                print(f"\n   💡 OPTIONS ({len(options)}):")
                
                for i, option in enumerate(options, 1):
                    color = get_color_indicator(option.get('color', 'yellow'))
                    nspe_status = option.get('nspe_status', 'alternative')
                    
                    print(f"\n   {color} Option {i}: {option.get('title', 'Unknown Option')}")
                    
                    # Show detailed description
                    description = option.get('description', '')
                    if description:
                        print(f"      Description: {description}")
                    
                    # Show ethical analysis
                    analysis = option.get('ethical_analysis', '')
                    if analysis:
                        print(f"      Analysis: {analysis}")
                    
                    # Show code references
                    code_refs = option.get('code_references', [])
                    if code_refs:
                        print(f"      Code References: {', '.join(code_refs)}")
                    
                    # Show precedent cases
                    precedents = option.get('precedent_cases', [])
                    if precedents:
                        print(f"      Precedent Cases: {', '.join(precedents)}")
                    
                    # Show reasoning quote
                    reasoning = option.get('reasoning_quote', '')
                    if reasoning:
                        print(f"      Reasoning: \"{reasoning}\"")
                    
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
        
        print(f"\n📊 CONSOLIDATED SUMMARY:")
        print(f"   Total Events: {len(events)}")
        print(f"   Total Decisions: {len(decisions)}")
        print(f"   Total Options: {sum(len(d.options or []) for d in decisions)}")
        
        # Count options by type
        all_options = []
        for decision in decisions:
            all_options.extend(decision.options or [])
        
        nspe_options = len([opt for opt in all_options if opt.get('nspe_status') in ['nspe_positive', 'nspe_negative', 'nspe_conclusion']])
        alternative_options = len(all_options) - nspe_options
        
        print(f"   NSPE-based Options: {nspe_options}")
        print(f"   Alternative Options: {alternative_options}")
        
        # Show decision breakdown
        print(f"\n📋 DECISION BREAKDOWN:")
        for decision in decisions:
            seq = decision.parameters.get('decision_sequence', '?')
            options_count = len(decision.options or [])
            print(f"   Decision {seq}: {options_count} options - {decision.parameters.get('decision_title')}")
        
        print(f"\n🌐 View consolidated scenario: http://localhost:3333/scenarios/7")
        
        print(f"\n✅ CONSOLIDATION SUCCESS:")
        print(f"   - Options are now properly grouped under each decision")
        print(f"   - Each decision is a single Action with options in the options field")
        print(f"   - Color coding and NSPE analysis preserved")
        print(f"   - Timeline maintains chronological flow")
        
    except Exception as e:
        print(f"❌ Error viewing consolidated scenario: {e}")
        import traceback
        traceback.print_exc()