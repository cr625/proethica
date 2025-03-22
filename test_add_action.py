from app import create_app
from app.models.event import Action
from app.models.scenario import Scenario
from datetime import datetime

app = create_app()

with app.app_context():
    from app import db
    
    # Get the first scenario
    scenario = Scenario.query.first()
    if not scenario:
        print("No scenarios found in the database")
        exit(1)
    
    # Create a new action
    action = Action(
        name="Test Action",
        description="This is a test action to verify the migration worked correctly",
        scenario=scenario,
        character_id=None,  # No character associated
        action_time=datetime.now(),
        action_type="test",
        parameters={},
        is_decision=False
    )
    
    # Add and commit
    db.session.add(action)
    db.session.commit()
    
    print(f"Action created successfully with ID: {action.id}")
    print(f"Action details: {action.name}, {action.description}, character_id: {action.character_id}")
