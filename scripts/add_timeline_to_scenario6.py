#!/usr/bin/env python3
import sys
import os
import json
import argparse
from datetime import datetime, timedelta

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.scenario import Scenario
from app.models.world import World
from app.models.character import Character
from app.models.event import Event, Action
from app.services.mcp_client import MCPClient

def create_action(scenario_id, name, character_id, action_time, description, action_type=None, is_decision=False, options=None, parameters=None):
    """Create an action in a scenario"""
    action = Action(
        scenario_id=scenario_id,
        name=name,
        character_id=character_id,
        action_time=action_time,
        description=description,
        action_type=action_type,
        is_decision=is_decision,
        options=options or [],
        parameters=parameters or {}
    )
    db.session.add(action)
    db.session.flush()
    print(f"Created action: {name} with ID {action.id}")
    return action

def create_event(scenario_id, description, event_time, character_id=None, action_id=None, parameters=None):
    """Create an event in a scenario"""
    event = Event(
        scenario_id=scenario_id,
        description=description,
        event_time=event_time,
        character_id=character_id,
        action_id=action_id,
        parameters=parameters or {}
    )
    db.session.add(event)
    db.session.flush()
    print(f"Created event: {description} with ID {event.id}")
    return event

def add_timeline_to_scenario_6(force=False):
    """Add timeline events, actions, and decisions to Scenario 6"""
    app = create_app()
    with app.app_context():
        # Get scenario 6
        scenario = Scenario.query.get(6)
        if not scenario:
            print("Scenario 6 not found")
            return
        
        print(f"Adding timeline to Scenario: {scenario.name}")
        
        # Check if we already have events
        existing_events = Event.query.filter_by(scenario_id=scenario.id).all()
        existing_actions = Action.query.filter_by(scenario_id=scenario.id).all()
        
        if (existing_events or existing_actions) and not force:
            print(f"Warning: Scenario already has {len(existing_events)} events and {len(existing_actions)} actions")
            confirm = input("Do you want to continue and add more timeline items? (y/n): ")
            if confirm.lower() != 'y':
                print("Operation cancelled")
                return
        
        try:
            # Get characters
            engineer = Character.query.filter_by(scenario_id=scenario.id, name="Engineer A").first()
            building_owner = Character.query.filter_by(scenario_id=scenario.id, name="Building Owner").first()
            building_authority = Character.query.filter_by(scenario_id=scenario.id, name="Building Safety Authority").first()
            
            if not engineer or not building_owner or not building_authority:
                print("Required characters not found. Please add characters first with add_characters_to_scenario6.py")
                return
            
            # Create a base date for the timeline - everything will happen relative to this
            base_date = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
            
            # 1. Initial Meeting - Client hires Engineer
            action1 = create_action(
                scenario_id=scenario.id,
                name="Hiring Meeting",
                character_id=building_owner.id,
                action_time=base_date,
                description="Building Owner hires Engineer A to investigate the structural integrity of the 60-year old apartment building.",
                action_type="Meeting"
            )
            
            event1 = create_event(
                scenario_id=scenario.id,
                description="Initial meeting between Building Owner and Engineer A to discuss the structural inspection.",
                event_time=base_date,
                character_id=building_owner.id,
                action_id=action1.id
            )
            
            # 2. Confidentiality Agreement Signing
            action2 = create_action(
                scenario_id=scenario.id,
                name="Sign Confidentiality Agreement",
                character_id=engineer.id,
                action_time=base_date + timedelta(hours=1),
                description="Engineer A signs confidentiality agreement with Building Owner, agreeing to keep the structural report confidential.",
                action_type="ContractSigning"
            )
            
            event2 = create_event(
                scenario_id=scenario.id,
                description="Engineer A signs confidentiality agreement, agreeing that the structural report will remain confidential.",
                event_time=base_date + timedelta(hours=1),
                character_id=engineer.id,
                action_id=action2.id
            )
            
            # 3. Client Explains Intentions
            action3 = create_action(
                scenario_id=scenario.id,
                name="Explain Building Sale Intentions",
                character_id=building_owner.id,
                action_time=base_date + timedelta(hours=1, minutes=30),
                description="Building Owner explains that the building is being sold 'as is' with no plans for repairs or renovations.",
                action_type="Disclosure"
            )
            
            event3 = create_event(
                scenario_id=scenario.id,
                description="Building Owner informs Engineer A that the building is being sold 'as is' with no plans for remediation.",
                event_time=base_date + timedelta(hours=1, minutes=30),
                character_id=building_owner.id,
                action_id=action3.id
            )
            
            # 4. Structural Inspection
            action4 = create_action(
                scenario_id=scenario.id,
                name="Conduct Structural Testing",
                character_id=engineer.id,
                action_time=base_date + timedelta(days=2),
                description="Engineer A performs structural tests on the building to assess its integrity.",
                action_type="Inspection"
            )
            
            event4 = create_event(
                scenario_id=scenario.id,
                description="Engineer A conducts structural tests and inspections throughout the apartment building.",
                event_time=base_date + timedelta(days=2),
                character_id=engineer.id,
                action_id=action4.id
            )
            
            # 5. Structural Assessment Result
            action5 = create_action(
                scenario_id=scenario.id,
                name="Determine Structural Soundness",
                character_id=engineer.id,
                action_time=base_date + timedelta(days=2, hours=5),
                description="Engineer A determines that the building is structurally sound with no significant issues.",
                action_type="Assessment"
            )
            
            event5 = create_event(
                scenario_id=scenario.id,
                description="Engineer A concludes that the apartment building is structurally sound with no significant issues.",
                event_time=base_date + timedelta(days=2, hours=5),
                character_id=engineer.id,
                action_id=action5.id
            )
            
            # 6. Client Reveals Code Violations
            action6 = create_action(
                scenario_id=scenario.id,
                name="Reveal Code Violations",
                character_id=building_owner.id,
                action_time=base_date + timedelta(days=2, hours=6),
                description="Building Owner reveals to Engineer A that the building contains electrical and mechanical code violations.",
                action_type="Disclosure"
            )
            
            event6 = create_event(
                scenario_id=scenario.id,
                description="Building Owner confides in Engineer A that the building contains electrical and mechanical system deficiencies that violate applicable codes.",
                event_time=base_date + timedelta(days=2, hours=6),
                character_id=building_owner.id,
                action_id=action6.id
            )
            
            # 7. Engineer Recognizes Safety Hazards
            action7 = create_action(
                scenario_id=scenario.id,
                name="Recognize Safety Concerns",
                character_id=engineer.id,
                action_time=base_date + timedelta(days=2, hours=6, minutes=10),
                description="Engineer A realizes that the code violations could pose safety hazards to building occupants.",
                action_type="Assessment"
            )
            
            event7 = create_event(
                scenario_id=scenario.id,
                description="Engineer A recognizes that the electrical and mechanical deficiencies could cause injury to the building occupants.",
                event_time=base_date + timedelta(days=2, hours=6, minutes=10),
                character_id=engineer.id,
                action_id=action7.id
            )
            
            # 8. Engineer Informs Client of Concerns
            action8 = create_action(
                scenario_id=scenario.id,
                name="Inform Client of Safety Concerns",
                character_id=engineer.id,
                action_time=base_date + timedelta(days=2, hours=6, minutes=15),
                description="Engineer A informs Building Owner of the safety concerns related to the code violations.",
                action_type="Communication"
            )
            
            event8 = create_event(
                scenario_id=scenario.id,
                description="Engineer A informs the Building Owner about the safety implications of the electrical and mechanical deficiencies.",
                event_time=base_date + timedelta(days=2, hours=6, minutes=15),
                character_id=engineer.id,
                action_id=action8.id
            )
            
            # 9. Engineer Writes Report
            action9 = create_action(
                scenario_id=scenario.id,
                name="Write Structural Report",
                character_id=engineer.id,
                action_time=base_date + timedelta(days=3),
                description="Engineer A writes the structural report, making brief mention of the conversation about deficiencies.",
                action_type="Documentation"
            )
            
            event9 = create_event(
                scenario_id=scenario.id,
                description="Engineer A prepares the structural report, briefly mentioning the conversation about code violations but not reporting them to authorities.",
                event_time=base_date + timedelta(days=3),
                character_id=engineer.id,
                action_id=action9.id
            )
            
            # 10. Ethical Decision Point - This is the main decision in the scenario
            action10 = create_action(
                scenario_id=scenario.id,
                name="Ethical Dilemma: Report Violations?",
                character_id=engineer.id,
                action_time=base_date + timedelta(days=3, hours=3),
                description="Engineer A faces an ethical dilemma about whether to report the safety violations to authorities despite the confidentiality agreement.",
                action_type="EthicalDecision",
                is_decision=True,
                options=[
                    {
                        "text": "Maintain client confidentiality",
                        "description": "Respect the confidentiality agreement and do not report the violations to the authorities.",
                        "ethical_codes": ["NSPE Code III.4 - Do not Disclose Confidential Information Without Consent", "NSPE Code I.4 - Act as a Faithful Agent or Trustee"]
                    },
                    {
                        "text": "Report violations to authorities",
                        "description": "Report the electrical and mechanical code violations to the Building Safety Authority to protect public safety.",
                        "ethical_codes": ["NSPE Code I.1 - Safety, Health, and Welfare of Public is Paramount", "NSPE Code II.1.A - Primary Obligation is to Protect Public"]
                    },
                    {
                        "text": "Convince owner to address violations",
                        "description": "Try to persuade the Building Owner to address the violations before selling the building.",
                        "ethical_codes": ["NSPE Code III.1 - Be Guided by Highest Standards of Integrity", "NSPE Code II.1.A - Primary Obligation is to Protect Public"]
                    },
                    {
                        "text": "Seek professional ethics guidance",
                        "description": "Consult with the professional engineering association for guidance on this ethical conflict.",
                        "ethical_codes": ["NSPE Code III.2.B - Do not Complete or Sign Documents that are not Safe for Public"]
                    }
                ]
            )
            
            event10 = create_event(
                scenario_id=scenario.id,
                description="Engineer A faces ethical decision on whether to report safety violations or maintain client confidentiality.",
                event_time=base_date + timedelta(days=3, hours=3),
                character_id=engineer.id,
                action_id=action10.id,
                parameters={"decision_point": True, "critical_event": True}
            )
            
            # Commit all changes
            db.session.commit()
            print("Successfully added timeline to Scenario 6")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error adding timeline: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Add timeline to Scenario 6')
    parser.add_argument('--force', action='store_true', help='Force adding timeline even if scenario already has events')
    
    args = parser.parse_args()
    add_timeline_to_scenario_6(force=args.force)
