#!/usr/bin/env python3
"""
Script to delete all scenarios from the database.
"""

import sys
import os

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import Scenario

def delete_all_scenarios():
    """Delete all scenarios from the database."""
    app = create_app()
    with app.app_context():
        from app.models import Action, Event, Character, Resource, Condition, Decision
        from app.models import SimulationSession, SimulationState
        from sqlalchemy import text
        
        # Get all scenarios to report what will be deleted
        scenarios = Scenario.query.all()
        if not scenarios:
            print("No scenarios found in the database.")
            return
        
        print("The following scenarios will be deleted:")
        for s in scenarios:
            print(f"ID: {s.id}, Name: {s.name}")
            
        print("\nDeleting associated records...")
        
        # Get all scenario IDs
        scenario_ids = [s.id for s in scenarios]
        
        # Delete in the correct order to handle foreign key constraints
        
        # 1. First delete evaluation records that reference actions
        db.session.execute(text("DELETE FROM evaluations WHERE action_id IN (SELECT id FROM actions WHERE scenario_id IN :ids)"), 
                          {"ids": tuple(scenario_ids) if len(scenario_ids) > 1 else (scenario_ids[0],)})
        
        # 2. Delete actions (including decisions converted to actions)
        action_count = Action.query.filter(Action.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
        print(f"- Deleted {action_count} actions")
        
        # 3. Delete old-style decisions (for backward compatibility)
        decision_count = Decision.query.filter(Decision.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
        print(f"- Deleted {decision_count} decisions")
        
        # 4. Delete events
        event_count = Event.query.filter(Event.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
        print(f"- Deleted {event_count} events")
        
        # 5. Delete conditions (linked to characters)
        condition_count = Condition.query.filter(Condition.character_id.in_(
            db.session.query(Character.id).filter(Character.scenario_id.in_(scenario_ids))
        )).delete(synchronize_session=False)
        print(f"- Deleted {condition_count} conditions")
        
        # 6. Delete characters
        character_count = Character.query.filter(Character.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
        print(f"- Deleted {character_count} characters")
        
        # 7. Delete resources
        resource_count = Resource.query.filter(Resource.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
        print(f"- Deleted {resource_count} resources")
        
        # 8. Delete simulation states and sessions
        state_count = SimulationState.query.filter(SimulationState.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
        print(f"- Deleted {state_count} simulation states")
        
        session_count = SimulationSession.query.filter(SimulationSession.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
        print(f"- Deleted {session_count} simulation sessions")
        
        # 9. Finally delete the scenarios
        scenario_count = Scenario.query.filter(Scenario.id.in_(scenario_ids)).delete(synchronize_session=False)
        print(f"- Deleted {scenario_count} scenarios")
        
        # Commit all changes
        db.session.commit()
        
        print("\nSuccessfully deleted all scenarios and their related records from the database.")

if __name__ == "__main__":
    from app import db
    delete_all_scenarios()
