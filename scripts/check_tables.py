#!/usr/bin/env python3
import os
import sys

# Add the parent directory to the path so we can import the app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print("Database tables:", tables)
    
    # Check if the roles table exists
    if 'roles' in tables:
        print("Roles table exists!")
        # Check the columns in the roles table
        columns = inspector.get_columns('roles')
        print("Roles table columns:", [col['name'] for col in columns])
    else:
        print("Roles table does not exist!")
