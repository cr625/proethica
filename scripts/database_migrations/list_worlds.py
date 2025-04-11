from app import create_app
from app.models.world import World

app = create_app()
with app.app_context():
    print('Available Worlds:')
    worlds = World.query.all()
    for w in worlds:
        print(f'ID: {w.id}, Name: {w.name}')
