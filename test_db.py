import os
from app import create_app
from app.models.scenario import Scenario

# Create app instance
app = create_app(os.getenv('FLASK_ENV', 'default'))

with app.app_context():
    # Print the database URL
    from flask import current_app
    print(f"Database URL: {current_app.config['SQLALCHEMY_DATABASE_URI']}")
    
    # Print the environment variables
    print(f"DATABASE_URL: {os.environ.get('DATABASE_URL')}")
    
    # Print the app config
    print(f"App config: {current_app.config}")
    
    # Get the database engine
    from app import db
    engine = db.engine
    print(f"Engine: {engine}")
    print(f"Engine URL: {engine.url}")
    
    # Try to create a table
    db.create_all()
    
    # Create a test scenario
    scenario = Scenario(name="Test Scenario", description="This is a test scenario")
    db.session.add(scenario)
    db.session.commit()
    
    # Query the database
    scenarios = Scenario.query.all()
    print(f"Scenarios: {scenarios}")
