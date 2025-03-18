#!/usr/bin/env python3
import os
import sys

# Add the parent directory to the path so we can import the app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create a log file
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "roles_check.log")
with open(log_file, "w") as f:
    f.write("Starting role check...\n")

    try:
        from app import create_app, db
        from app.models import Role, World
        
        f.write("Imported modules successfully\n")
        
        app = create_app()
        with app.app_context():
            f.write("Checking database connection...\n")
            try:
                # Check if we can connect to the database
                db.session.execute("SELECT 1")
                f.write("Database connection successful!\n")
            except Exception as e:
                f.write(f"Database connection error: {e}\n")
                sys.exit(1)
            
            # Check worlds
            f.write("\nChecking worlds...\n")
            worlds = World.query.all()
            f.write(f"Found {len(worlds)} worlds:\n")
            for world in worlds:
                f.write(f"ID: {world.id}, Name: {world.name}\n")
            
            # Get all roles
            f.write("\nChecking roles...\n")
            try:
                roles = Role.query.all()
                f.write(f"Found {len(roles)} roles:\n")
                for role in roles:
                    f.write(f"ID: {role.id}, Name: {role.name}, Tier: {role.tier}\n")
                    f.write(f"Description: {role.description}\n")
                    f.write(f"Ontology URI: {role.ontology_uri}\n")
                    f.write("-" * 50 + "\n")
            except Exception as e:
                f.write(f"Error querying roles: {e}\n")
    except Exception as e:
        f.write(f"Error: {e}\n")

print(f"Check complete. Log file written to {log_file}")
