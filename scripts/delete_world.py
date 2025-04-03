#!/usr/bin/env python3
"""
Script to delete a specific world from the database.
"""

import sys
import os
import argparse

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import World, Scenario
from sqlalchemy import text

def delete_world(world_id):
    """Delete a specific world and its associated records from the database."""
    app = create_app()
    with app.app_context():
        # Check if the world exists
        world = World.query.get(world_id)
        if not world:
            print(f"World with ID {world_id} not found.")
            return
        
        print(f"Preparing to delete World: ID {world.id}, Name: {world.name}")
        
        # Check for scenarios associated with this world
        scenarios = Scenario.query.filter_by(world_id=world_id).all()
        if scenarios:
            scenario_ids = [s.id for s in scenarios]
            print(f"Found {len(scenarios)} scenarios associated with this world.")
            
            # If there are scenarios, we need to delete them first
            # Using the same approach as in delete_all_scenarios.py
            
            print("Deleting associated scenario records...")
            
            # 1. First delete evaluation records that reference actions
            db.session.execute(text("DELETE FROM evaluations WHERE action_id IN (SELECT id FROM actions WHERE scenario_id IN :ids)"), 
                            {"ids": tuple(scenario_ids) if len(scenario_ids) > 1 else (scenario_ids[0],)})
            
            # 2. Delete actions (including decisions converted to actions)
            from app.models import Action
            action_count = Action.query.filter(Action.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
            print(f"- Deleted {action_count} actions")
            
            # 3. Delete old-style decisions (for backward compatibility)
            from app.models import Decision
            decision_count = Decision.query.filter(Decision.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
            print(f"- Deleted {decision_count} decisions")
            
            # 4. Delete events
            from app.models import Event
            event_count = Event.query.filter(Event.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
            print(f"- Deleted {event_count} events")
            
            # 5. Delete conditions (linked to characters)
            from app.models import Condition, Character
            condition_count = Condition.query.filter(Condition.character_id.in_(
                db.session.query(Character.id).filter(Character.scenario_id.in_(scenario_ids))
            )).delete(synchronize_session=False)
            print(f"- Deleted {condition_count} conditions")
            
            # 6. Delete characters
            character_count = Character.query.filter(Character.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
            print(f"- Deleted {character_count} characters")
            
            # 7. Delete resources
            from app.models import Resource
            resource_count = Resource.query.filter(Resource.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
            print(f"- Deleted {resource_count} resources")
            
            # 8. Delete simulation states and sessions
            from app.models import SimulationState, SimulationSession
            state_count = SimulationState.query.filter(SimulationState.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
            print(f"- Deleted {state_count} simulation states")
            
            session_count = SimulationSession.query.filter(SimulationSession.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
            print(f"- Deleted {session_count} simulation sessions")
            
            # 9. Finally delete the scenarios
            scenario_count = Scenario.query.filter(Scenario.id.in_(scenario_ids)).delete(synchronize_session=False)
            print(f"- Deleted {scenario_count} scenarios")
        else:
            print("No scenarios associated with this world.")
        
        # Handle label_types and labels relationships
        try:
            # Check if any label_types are associated with this world
            label_types_exist = db.session.execute(text(
                "SELECT EXISTS (SELECT 1 FROM label_types WHERE world_id = :world_id)"
            ), {"world_id": world_id}).scalar()
            
            if label_types_exist:
                # First delete the labels that reference these label_types
                db.session.execute(text(
                    "DELETE FROM labels WHERE label_type_id IN (SELECT id FROM label_types WHERE world_id = :world_id)"
                ), {"world_id": world_id})
                print("- Deleted labels associated with this world's label types")
                
                # Then delete the label_types
                label_types_count = db.session.execute(text(
                    "DELETE FROM label_types WHERE world_id = :world_id"
                ), {"world_id": world_id}).rowcount
                print(f"- Deleted {label_types_count} label types")
        except Exception as e:
            print(f"Warning: Could not delete labels or label types: {e}")
        
        # Handle entity references
        try:
            # Check if we have entity_world table
            entity_world_exists = db.session.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'entity_world')"
            )).scalar()
            
            if entity_world_exists:
                # Delete entity_world associations
                entity_world_count = db.session.execute(text(
                    "DELETE FROM entity_world WHERE world_id = :world_id"
                ), {"world_id": world_id}).rowcount
                print(f"- Deleted {entity_world_count} entity-world associations")
        except Exception as e:
            print(f"Warning: Could not delete entity-world associations: {e}")
        
        # Handle any other potential relationships by direct SQL as a fallback
        for related_table in [
            "world_entities", "world_concepts", "world_rules", "world_guidelines", 
            "world_cases", "world_attributes", "world_tags"
        ]:
            try:
                # Check if table exists
                table_exists = db.session.execute(text(
                    f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{related_table}')"
                )).scalar()
                
                if table_exists:
                    # Delete from the related table
                    count = db.session.execute(text(
                        f"DELETE FROM {related_table} WHERE world_id = :world_id"
                    ), {"world_id": world_id}).rowcount
                    if count > 0:
                        print(f"- Deleted {count} records from {related_table}")
            except Exception as e:
                print(f"Warning: Error when trying to clean up {related_table}: {e}")
        
        # Finally delete the world
        db.session.delete(world)
        db.session.commit()
        
        print(f"\nSuccessfully deleted World ID {world_id}: {world.name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Delete a world from the database.')
    parser.add_argument('world_id', type=int, help='The ID of the world to delete')
    
    args = parser.parse_args()
    delete_world(args.world_id)
