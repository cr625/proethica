from app import create_app
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    from app import db
    inspector = inspect(db.engine)
    print('Tables in database:', inspector.get_table_names())
    
    # Check if actions table exists
    if 'actions' in inspector.get_table_names():
        print('Actions table columns:', inspector.get_columns('actions'))
    else:
        print('Actions table does not exist')
    
    # Check if events table exists
    if 'events' in inspector.get_table_names():
        print('Events table columns:', inspector.get_columns('events'))
    else:
        print('Events table does not exist')
