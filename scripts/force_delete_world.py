#!/usr/bin/env python
"""
Script to force delete a world and all its related data.
This handles the integrity error related to simulation_states.
"""

import os
import sys
import argparse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.world import World
from app.models.scenario import Scenario
from app.models.simulation_state import SimulationState
from app.models.simulation_session import SimulationSession
from app.models.character import Character
from app.models.event import Event, Action
from app.models.triple import Triple
from app.models.entity_triple import EntityTriple
from app.models.resource import Resource

def delete_world(world_id, force=False):
    """Delete a world and all related data."""
    # Get the world
    world = World.query.get(world_id)
    if not world:
        print(f"World with ID {world_id} not found.")
        return False

    print(f"Found world: {world.name} (ID: {world_id})")
    
    # Get related scenarios
    scenarios = Scenario.query.filter_by(world_id=world_id).all()
    print(f"Found {len(scenarios)} related scenarios")
    
    # Get related simulation sessions and states
    simulation_states = []
    for scenario in scenarios:
        states = SimulationState.query.filter_by(scenario_id=scenario.id).all()
        simulation_states.extend(states)
    
    print(f"Found {len(simulation_states)} related simulation states")
    
    # Try using state_data field for cases where metadata doesn't exist
    try:
        session = db.session
        sql_query = text(f"""
        SELECT id FROM simulation_states 
        WHERE simulation_states.state_data->>'world_id' = '{world_id}'
        """)
        world_states_ids = [row[0] for row in session.execute(sql_query)]
        world_states = SimulationState.query.filter(SimulationState.id.in_(world_states_ids)).all() if world_states_ids else []
        simulation_states.extend([s for s in world_states if s not in simulation_states])
        print(f"Found {len(world_states)} additional simulation states with world_id in state_data")
    except Exception as e:
        print(f"Note: Could not search state_data for world_id reference: {e}")
        world_states = []
    
    # Get related simulation sessions
    session_ids = {state.session_id for state in simulation_states if state.session_id is not None}
    simulation_sessions = SimulationSession.query.filter(SimulationSession.id.in_(session_ids)).all() if session_ids else []
    
    print(f"Found {len(simulation_sessions)} related simulation sessions")
    
    # Get related characters
    characters = []
    for scenario in scenarios:
        chars = Character.query.filter_by(scenario_id=scenario.id).all()
        characters.extend(chars)
    
    print(f"Found {len(characters)} related characters")
    
    # Get related events
    events = []
    for scenario in scenarios:
        evts = Event.query.filter_by(scenario_id=scenario.id).all()
        events.extend(evts)
    
    print(f"Found {len(events)} related events")
    
    # Get related actions
    action_ids = {event.action_id for event in events if event.action_id is not None}
    actions = Action.query.filter(Action.id.in_(action_ids)).all() if action_ids else []
    
    print(f"Found {len(actions)} related actions")
    
    # Get related resources
    resources = []
    for scenario in scenarios:
        res = Resource.query.filter_by(scenario_id=scenario.id).all()
        resources.extend(res)
    
    print(f"Found {len(resources)} related resources")
    
    # Get related triples
    char_ids = [char.id for char in characters]
    triples = Triple.query.filter(Triple.character_id.in_(char_ids)).all() if char_ids else []
    
    print(f"Found {len(triples)} related character triples")
    
    # Get related entity triples
    entity_triples = []
    if char_ids:
        entity_triples.extend(EntityTriple.query.filter_by(entity_type='character').filter(EntityTriple.entity_id.in_(char_ids)).all())
    
    # Also get entity triples related to events and actions
    event_ids = [event.id for event in events]
    if event_ids:
        entity_triples.extend(EntityTriple.query.filter_by(entity_type='event').filter(EntityTriple.entity_id.in_(event_ids)).all())
    
    action_ids = [action.id for action in actions]
    if action_ids:
        entity_triples.extend(EntityTriple.query.filter_by(entity_type='action').filter(EntityTriple.entity_id.in_(action_ids)).all())
    
    print(f"Found {len(entity_triples)} related entity triples")
    
    # If not force, ask for confirmation
    if not force:
        confirmation = input(
            f"\nAre you sure you want to delete world '{world.name}' with ID {world_id} and all related data? "
            f"This will delete:\n"
            f"- {len(scenarios)} scenarios\n"
            f"- {len(characters)} characters\n"
            f"- {len(events)} events\n"
            f"- {len(actions)} actions\n"
            f"- {len(resources)} resources\n"
            f"- {len(triples)} character triples\n"
            f"- {len(entity_triples)} entity triples\n"
            f"- {len(simulation_states)} simulation states\n"
            f"- {len(simulation_sessions)} simulation sessions\n"
            f"This action cannot be undone. (y/N): "
        )
        if confirmation.lower() != 'y':
            print("Deletion cancelled.")
            return False
    
    # Start deletion
    print("\nDeleting data...")
    
    try:
        # 1. Delete entity triples first (they reference other entities)
        for triple in entity_triples:
            db.session.delete(triple)
        print("- Entity triples deleted")
        
        # 2. Delete character triples
        for triple in triples:
            db.session.delete(triple)
        print("- Character triples deleted")
        
        # 3. Delete simulation states (we need to handle the constraint issue)
        if simulation_states:
            # First, let's directly delete any problematic states that have null scenario_id
            try:
                session.execute(text("DELETE FROM simulation_states WHERE scenario_id IS NULL"))
                print("- Deleted problematic simulation states with NULL scenario_id")
            except Exception as e:
                print(f"  Note: Error deleting states with NULL scenario_id: {e}")
            
            # Now delete the remaining states through the ORM
            for state in simulation_states:
                try:
                    db.session.delete(state)
                except Exception as e:
                    print(f"  Warning: Could not delete state {state.id}: {e}")
                    # Try direct SQL deletion as fallback
                    try:
                        session.execute(text(f"DELETE FROM simulation_states WHERE id = {state.id}"))
                    except Exception as sub_e:
                        print(f"  Error: SQL deletion also failed for state {state.id}: {sub_e}")
            print("- Simulation states deleted")
        
        # 4. Delete simulation sessions
        for session_obj in simulation_sessions:
            db.session.delete(session_obj)
        print("- Simulation sessions deleted")
        
        # 5. Delete characters, events, actions, and resources
        for action in actions:
            db.session.delete(action)
        print("- Actions deleted")
        
        for event in events:
            db.session.delete(event)
        print("- Events deleted")
        
        for character in characters:
            db.session.delete(character)
        print("- Characters deleted")
        
        for resource in resources:
            db.session.delete(resource)
        print("- Resources deleted")
        
        # 6. Delete scenarios
        for scenario in scenarios:
            db.session.delete(scenario)
        print("- Scenarios deleted")
        
        # 7. Finally delete the world
        db.session.delete(world)
        print("- World deleted")
        
        # Commit all changes
        db.session.commit()
        print(f"\nWorld '{world.name}' with ID {world_id} has been successfully deleted.")
        
        return True
    
    except Exception as e:
        db.session.rollback()
        print(f"Error during deletion: {e}")
        print("Deletion failed. No changes were made to the database.")
        return False

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Force delete a world and all related data')
    parser.add_argument('world_id', type=int, help='ID of the world to delete')
    parser.add_argument('--force', '-f', action='store_true', help='Force deletion without confirmation')
    args = parser.parse_args()
    
    app = create_app()
    
    with app.app_context():
        result = delete_world(args.world_id, args.force)
        
        if result:
            print("World deletion completed successfully.")
        else:
            print("World deletion failed or was cancelled.")

if __name__ == '__main__':
    main()
