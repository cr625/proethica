from app import create_app
from app.models.event import Action, Event
from app.models.scenario import Scenario
from datetime import datetime, timedelta

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
        description="This is a test action to verify the timeline styling",
        scenario=scenario,
        character_id=None,  # No character associated
        action_time=datetime.now(),
        action_type="test",
        parameters={},
        is_decision=False
    )
    
    # Create a new event (5 minutes after the action)
    event = Event(
        scenario=scenario,
        event_time=datetime.now() + timedelta(minutes=5),
        description="This is a test event to verify the timeline styling",
        character_id=None,
        parameters={}
    )
    
    # Add and commit
    db.session.add(action)
    db.session.add(event)
    db.session.commit()
    
    print(f"Action created successfully with ID: {action.id}")
    print(f"Action details: {action.name}, {action.description}, time: {action.action_time}")
    
    print(f"Event created successfully with ID: {event.id}")
    print(f"Event details: {event.description}, time: {event.event_time}")
