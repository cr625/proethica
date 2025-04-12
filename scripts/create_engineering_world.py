"""
Script to create an Engineering Ethics world in the database.
"""

from datetime import datetime
import sys
import os

# Add project root to path so app can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.world import World

def create_engineering_ethics_world():
    """Create the Engineering Ethics world if it doesn't exist."""
    # Create app context
    app = create_app('development')
    
    with app.app_context():
        # Check if Engineering Ethics world exists
        engineering_world = World.query.filter_by(name='Engineering Ethics').first()
        
        if engineering_world:
            print("Engineering Ethics world already exists with id:", engineering_world.id)
            return
        
        # Create Engineering Ethics world
        engineering_world = World(
            name='Engineering Ethics',
            description="""
# Engineering Ethics

This world represents the ethical framework and guidelines for professional engineering practice.

## Core Principles

1. **Hold paramount the safety, health, and welfare of the public**
2. **Perform services only in areas of their competence**
3. **Issue public statements only in an objective and truthful manner**
4. **Act for each employer or client as faithful agents or trustees**
5. **Avoid deceptive acts**
6. **Conduct themselves honorably, responsibly, ethically, and lawfully**

Engineers must adhere to these principles to maintain the integrity of the profession and ensure that engineering work benefits society.
            """,
            ontology_source='engineering_ethics',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            # Optional fields with default values
            cases=[],
            rulesets={},
            world_metadata={}
        )
        
        # Add to session and commit
        db.session.add(engineering_world)
        db.session.commit()
        
        print("Engineering Ethics world created with id:", engineering_world.id)

if __name__ == '__main__':
    create_engineering_ethics_world()
