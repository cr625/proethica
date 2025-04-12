#!/usr/bin/env python
"""
Script to check if there are any worlds in the database and create the Engineering world if needed.
"""

import sys
import os
import json
from datetime import datetime
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, select, func
from sqlalchemy.orm import Session

# Add the project directory to the path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    # Import database config from app.config
    from app.config import config
    # Get the default config
    DATABASE_URI = config['default']().SQLALCHEMY_DATABASE_URI
    print(f"Using database URI: {DATABASE_URI}")
except ImportError:
    print("Unable to import config from app.config")
    DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost/ai_ethical_dm')

def check_and_create_worlds():
    """Check if there are any worlds in the database and create the Engineering world if needed."""
    
    # Create engine and metadata
    engine = create_engine(DATABASE_URI)
    metadata = MetaData()

    # Define worlds table
    worlds = Table(
        'worlds', metadata,
        Column('id', Integer, primary_key=True),
        Column('name', String),
        Column('description', String),
        Column('ontology_source', String),
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('cases', String),
        Column('rulesets', String),
        Column('world_metadata', String)
    )

    try:
        # Get count of worlds in database
        with Session(engine) as session:
            count_query = select(func.count()).select_from(worlds)
            world_count = session.execute(count_query).scalar()
            
            print(f"Found {world_count} worlds in the database.")
            
            # If no worlds, add engineering world
            if world_count == 0:
                # Sample data for Engineering Ethics world
                engineering_world = {
                    'name': 'Engineering Ethics',
                    'description': 'A world based on engineering ethics guidelines and standards',
                    'ontology_source': 'engineering_ethics',
                    'created_at': datetime.now(),
                    'updated_at': datetime.now(),
                    'cases': json.dumps({}),  # Empty cases object
                    'rulesets': json.dumps({
                        'nspe_code': {
                            'name': 'NSPE Code of Ethics',
                            'description': 'National Society of Professional Engineers Code of Ethics',
                            'source_url': 'https://www.nspe.org/resources/ethics/code-ethics'
                        }
                    }),
                    'world_metadata': json.dumps({
                        'domain': 'engineering',
                        'profession': 'engineer',
                        'guidelines': 'Engineers shall hold paramount the safety, health, and welfare of the public. Engineers shall perform services only in areas of their competence. Engineers shall issue public statements only in an objective and truthful manner. Engineers shall act for each employer or client as faithful agents or trustees. Engineers shall avoid deceptive acts. Engineers shall conduct themselves honorably, responsibly, ethically, and lawfully so as to enhance the honor, reputation, and usefulness of the profession.'
                    })
                }
                
                # Insert engineering world
                insert_stmt = worlds.insert().values(**engineering_world)
                result = session.execute(insert_stmt)
                session.commit()
                
                print(f"Created Engineering Ethics world with ID: {result.inserted_primary_key[0]}")
                
                return True
            else:
                # Query world details to confirm they exist
                query = select(worlds)
                all_worlds = session.execute(query).fetchall()
                for world in all_worlds:
                    print(f"World ID {world.id}: {world.name}")
                
                return False
                
    except Exception as e:
        print(f"Error accessing the worlds table: {e}")
        return False

if __name__ == "__main__":
    created = check_and_create_worlds()
    if created:
        print("Engineering world created successfully!")
    else:
        print("No new worlds were created.")
