#!/usr/bin/env python3
"""
Script to clean the database by deleting all scenarios and worlds.
This script handles foreign key relationships correctly and avoids
constraint violations when deleting worlds with associated entities.
"""

import sys
import os
import argparse
from pprint import pprint

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import World, Scenario, Role, ConditionType, ResourceType
from app.models import Character, Resource, Condition
from app.models import Action, Event, Decision
from app.models import SimulationSession, SimulationState
from app.models.triple import Triple
from sqlalchemy import text

def delete_all_scenarios():
    """Delete all scenarios from the database safely."""
    app = create_app()
    with app.app_context():
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
        
        # 1. Delete RDF triples associated with characters
        triple_count = Triple.query.filter(Triple.character_id.in_(
            db.session.query(Character.id).filter(Character.scenario_id.in_(scenario_ids))
        )).delete(synchronize_session=False)
        print(f"- Deleted {triple_count} RDF triples")
        
        # 2. Delete evaluation records that reference actions
        try:
            eval_count = db.session.execute(text(
                "DELETE FROM evaluations WHERE action_id IN (SELECT id FROM actions WHERE scenario_id IN :ids)"
            ), {"ids": tuple(scenario_ids) if len(scenario_ids) > 1 else (scenario_ids[0],)}).rowcount
            print(f"- Deleted {eval_count} evaluations")
        except Exception as e:
            print(f"Warning: Could not delete evaluations: {e}")
        
        # 3. Delete actions (including decisions converted to actions)
        action_count = Action.query.filter(Action.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
        print(f"- Deleted {action_count} actions")
        
        # 4. Delete old-style decisions (for backward compatibility)
        decision_count = Decision.query.filter(Decision.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
        print(f"- Deleted {decision_count} decisions")
        
        # 5. Delete events
        event_count = Event.query.filter(Event.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
        print(f"- Deleted {event_count} events")
        
        # 6. Delete conditions (linked to characters)
        condition_count = Condition.query.filter(Condition.character_id.in_(
            db.session.query(Character.id).filter(Character.scenario_id.in_(scenario_ids))
        )).delete(synchronize_session=False)
        print(f"- Deleted {condition_count} conditions")
        
        # 7. Delete characters
        character_count = Character.query.filter(Character.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
        print(f"- Deleted {character_count} characters")
        
        # 8. Delete resources
        resource_count = Resource.query.filter(Resource.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
        print(f"- Deleted {resource_count} resources")
        
        # 9. Delete simulation states and sessions
        state_count = SimulationState.query.filter(SimulationState.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
        print(f"- Deleted {state_count} simulation states")
        
        session_count = SimulationSession.query.filter(SimulationSession.scenario_id.in_(scenario_ids)).delete(synchronize_session=False)
        print(f"- Deleted {session_count} simulation sessions")
        
        # 10. Finally delete the scenarios
        scenario_count = Scenario.query.filter(Scenario.id.in_(scenario_ids)).delete(synchronize_session=False)
        print(f"- Deleted {scenario_count} scenarios")
        
        # Commit all changes
        db.session.commit()
        
        print("\nSuccessfully deleted all scenarios and their related records from the database.")

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
            print(f"Found {len(scenarios)} scenarios associated with this world.")
            print("Deleting scenarios first...")
            
            # Get the scenario IDs
            scenario_ids = [s.id for s in scenarios]
            
            # Delete these scenarios
            for scenario_id in scenario_ids:
                print(f"Deleting scenario ID {scenario_id}")
                # Use direct SQL for consistency
                db.session.execute(text(
                    "DELETE FROM scenarios WHERE id = :id"
                ), {"id": scenario_id})
            
            db.session.commit()
            print("All scenarios deleted.")
        
        # Now delete the world-specific entities
        
        # 1. Delete condition types
        condition_type_count = ConditionType.query.filter_by(world_id=world_id).delete(synchronize_session=False)
        print(f"- Deleted {condition_type_count} condition types")
        
        # 2. Delete resource types
        resource_type_count = ResourceType.query.filter_by(world_id=world_id).delete(synchronize_session=False)
        print(f"- Deleted {resource_type_count} resource types")
        
        # 3. Delete roles
        role_count = Role.query.filter_by(world_id=world_id).delete(synchronize_session=False)
        print(f"- Deleted {role_count} roles")
        
        # 4. Handle label_types and labels relationships
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
        
        # 5. Handle entity references
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
        
        # 6. Handle document references
        try:
            # Delete documents associated with this world
            doc_count = db.session.execute(text(
                "DELETE FROM documents WHERE world_id = :world_id"
            ), {"world_id": world_id}).rowcount
            print(f"- Deleted {doc_count} documents")
        except Exception as e:
            print(f"Warning: Could not delete documents: {e}")
        
        # 7. Handle any other potential relationships by direct SQL as a fallback
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
        
        # 8. Finally delete the world
        db.session.delete(world)
        db.session.commit()
        
        print(f"\nSuccessfully deleted World ID {world_id}: {world.name}")

def list_worlds():
    """List all worlds in the database."""
    app = create_app()
    with app.app_context():
        worlds = World.query.all()
        
        if not worlds:
            print("No worlds found in the database.")
            return
        
        print("Available Worlds:")
        for world in worlds:
            print(f"ID: {world.id}, Name: {world.name}")
            # Count the roles and scenarios for this world
            role_count = Role.query.filter_by(world_id=world.id).count()
            scenario_count = Scenario.query.filter_by(world_id=world.id).count()
            print(f"   Roles: {role_count}, Scenarios: {scenario_count}")

def list_scenarios():
    """List all scenarios in the database."""
    app = create_app()
    with app.app_context():
        scenarios = Scenario.query.all()
        
        if not scenarios:
            print("No scenarios found in the database.")
            return
        
        print("Available Scenarios:")
        for scenario in scenarios:
            print(f"ID: {scenario.id}, Name: {scenario.name}")
            # Get the world for this scenario
            world = World.query.get(scenario.world_id)
            world_name = world.name if world else "Unknown World"
            print(f"   World: {world_name}")
            # Count the characters and resources for this scenario
            character_count = Character.query.filter_by(scenario_id=scenario.id).count()
            resource_count = Resource.query.filter_by(scenario_id=scenario.id).count()
            print(f"   Characters: {character_count}, Resources: {resource_count}")

def clean_database():
    """Clean the entire database by deleting all scenarios and worlds."""
    app = create_app()
    with app.app_context():
        print("Starting database cleanup...")
        
        # First, delete all scenarios
        delete_all_scenarios()
        
        # Then, get all worlds and delete them one by one
        worlds = World.query.all()
        
        if not worlds:
            print("No worlds found in the database.")
            return
        
        print("\nPreparing to delete all worlds:")
        for world in worlds:
            print(f"Deleting World ID {world.id}: {world.name}")
            # Instead of using the world ID, we'll delete the world object directly
            
            # 1. Delete condition types
            condition_type_count = ConditionType.query.filter_by(world_id=world.id).delete(synchronize_session=False)
            print(f"- Deleted {condition_type_count} condition types")
            
            # 2. Delete resource types
            resource_type_count = ResourceType.query.filter_by(world_id=world.id).delete(synchronize_session=False)
            print(f"- Deleted {resource_type_count} resource types")
            
            # 3. Delete roles
            role_count = Role.query.filter_by(world_id=world.id).delete(synchronize_session=False)
            print(f"- Deleted {role_count} roles")
            
            # Handle other relationships as in delete_world function
            try:
                label_types_count = db.session.execute(text(
                    "DELETE FROM label_types WHERE world_id = :world_id"
                ), {"world_id": world.id}).rowcount
                if label_types_count > 0:
                    print(f"- Deleted {label_types_count} label types")
            except Exception as e:
                print(f"Warning: Could not delete label types: {e}")
            
            # Delete the world
            db.session.delete(world)
            
            # Commit after each world to avoid transaction issues
            db.session.commit()
            print(f"World ID {world.id} deleted successfully.")
        
        print("\nDatabase cleanup completed successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Clean the database by deleting scenarios and worlds.')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # List worlds command
    list_worlds_parser = subparsers.add_parser('list-worlds', help='List all worlds')
    
    # List scenarios command
    list_scenarios_parser = subparsers.add_parser('list-scenarios', help='List all scenarios')
    
    # Delete scenarios command
    delete_scenarios_parser = subparsers.add_parser('delete-scenarios', help='Delete all scenarios')
    
    # Delete world command
    delete_world_parser = subparsers.add_parser('delete-world', help='Delete a specific world')
    delete_world_parser.add_argument('world_id', type=int, help='The ID of the world to delete')
    
    # Clean all command
    clean_all_parser = subparsers.add_parser('clean-all', help='Clean the entire database')
    
    args = parser.parse_args()
    
    if args.command == 'list-worlds':
        list_worlds()
    elif args.command == 'list-scenarios':
        list_scenarios()
    elif args.command == 'delete-scenarios':
        delete_all_scenarios()
    elif args.command == 'delete-world':
        delete_world(args.world_id)
    elif args.command == 'clean-all':
        clean_database()
    else:
        # Default if no command is provided
        parser.print_help()
