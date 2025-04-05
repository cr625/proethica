#!/usr/bin/env python3
"""
Script to clean the database using direct SQL commands.
This approach uses SQL to directly delete records while handling
dependencies and constraints properly.
"""

import sys
import os
import argparse

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from sqlalchemy import text

def run_cleanup_sql():
    """Run SQL commands to clean the database properly."""
    app = create_app()
    with app.app_context():
        print("Starting database cleanup with direct SQL...")
        
        # Use direct SQL commands to delete records in the correct order
        # This ensures all constraints are respected
        
        try:
            # 1. First, handle character triples
            triple_count = db.session.execute(text(
                "DELETE FROM character_triples"
            )).rowcount
            print(f"- Deleted {triple_count} character triples")
            
            # 2. Delete evaluations
            eval_count = db.session.execute(text(
                "DELETE FROM evaluations"
            )).rowcount
            print(f"- Deleted {eval_count} evaluations")
            
            # 3. Delete simulation states and sessions
            state_count = db.session.execute(text(
                "DELETE FROM simulation_states"
            )).rowcount
            print(f"- Deleted {state_count} simulation states")
            
            session_count = db.session.execute(text(
                "DELETE FROM simulation_sessions"
            )).rowcount
            print(f"- Deleted {session_count} simulation sessions")
            
            # 4. Delete conditions
            condition_count = db.session.execute(text(
                "DELETE FROM conditions"
            )).rowcount
            print(f"- Deleted {condition_count} conditions")
            
            # 5. Delete characters
            character_count = db.session.execute(text(
                "DELETE FROM characters"
            )).rowcount
            print(f"- Deleted {character_count} characters")
            
            # 6. Delete resources
            resource_count = db.session.execute(text(
                "DELETE FROM resources"
            )).rowcount
            print(f"- Deleted {resource_count} resources")
            
            # 7. Delete actions and decisions
            action_count = db.session.execute(text(
                "DELETE FROM actions"
            )).rowcount
            print(f"- Deleted {action_count} actions")
            
            decision_count = db.session.execute(text(
                "DELETE FROM decisions"
            )).rowcount
            print(f"- Deleted {decision_count} decisions")
            
            # 8. Delete events
            event_count = db.session.execute(text(
                "DELETE FROM events"
            )).rowcount
            print(f"- Deleted {event_count} events")
            
            # 9. Delete scenarios
            scenario_count = db.session.execute(text(
                "DELETE FROM scenarios"
            )).rowcount
            print(f"- Deleted {scenario_count} scenarios")
            
            # 10. Handle labels before label_types
            label_count = db.session.execute(text(
                "DELETE FROM labels"
            )).rowcount
            print(f"- Deleted {label_count} labels")
            
            # 11. Delete label types
            label_type_count = db.session.execute(text(
                "DELETE FROM label_types"
            )).rowcount
            print(f"- Deleted {label_type_count} label types")
            
            # 12. Delete condition types
            condition_type_count = db.session.execute(text(
                "DELETE FROM condition_types"
            )).rowcount
            print(f"- Deleted {condition_type_count} condition types")
            
            # 13. Delete resource types
            resource_type_count = db.session.execute(text(
                "DELETE FROM resource_types"
            )).rowcount
            print(f"- Deleted {resource_type_count} resource types")
            
            # 14. Delete roles
            role_count = db.session.execute(text(
                "DELETE FROM roles"
            )).rowcount
            print(f"- Deleted {role_count} roles")
            
            # 15. Delete documents
            doc_count = db.session.execute(text(
                "DELETE FROM documents"
            )).rowcount
            print(f"- Deleted {doc_count} documents")
            
            # 16. Check and delete entity_world if it exists
            entity_world_exists = db.session.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'entity_world')"
            )).scalar()
            
            if entity_world_exists:
                entity_world_count = db.session.execute(text(
                    "DELETE FROM entity_world"
                )).rowcount
                print(f"- Deleted {entity_world_count} entity-world associations")
            
            # 17. Delete other related tables if they exist
            for related_table in [
                "world_entities", "world_concepts", "world_rules", "world_guidelines", 
                "world_cases", "world_attributes", "world_tags"
            ]:
                try:
                    table_exists = db.session.execute(text(
                        f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{related_table}')"
                    )).scalar()
                    
                    if table_exists:
                        count = db.session.execute(text(
                            f"DELETE FROM {related_table}"
                        )).rowcount
                        if count > 0:
                            print(f"- Deleted {count} records from {related_table}")
                except Exception as e:
                    print(f"Warning: Error when trying to clean up {related_table}: {e}")
            
            # 18. Finally delete the worlds
            world_count = db.session.execute(text(
                "DELETE FROM worlds"
            )).rowcount
            print(f"- Deleted {world_count} worlds")
            
            # Commit all changes
            db.session.commit()
            print("\nDatabase cleanup completed successfully.")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error during database cleanup: {e}")
            print("Rolling back changes.")

def list_tables():
    """List all tables in the database and their row counts."""
    app = create_app()
    with app.app_context():
        # Get a list of all tables in the current schema
        tables_query = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = current_schema()
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        tables = db.session.execute(tables_query).scalars().all()
        
        print("Database Tables and Row Counts:")
        print("-------------------------------")
        
        for table in tables:
            # Count rows in each table
            count_query = text(f"SELECT COUNT(*) FROM {table}")
            count = db.session.execute(count_query).scalar()
            print(f"{table}: {count} rows")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Clean the database using direct SQL commands.')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Clean command
    clean_parser = subparsers.add_parser('clean', help='Clean the entire database')
    
    # List tables command
    list_parser = subparsers.add_parser('list-tables', help='List all tables and their row counts')
    
    args = parser.parse_args()
    
    if args.command == 'clean':
        run_cleanup_sql()
    elif args.command == 'list-tables':
        list_tables()
    else:
        # Default if no command is provided
        parser.print_help()
