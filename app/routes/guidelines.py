"""
Guidelines routes for displaying all guidelines across all worlds.
"""

from flask import Blueprint, render_template, request
from app.models import db
from app.models import Document
from app.models.world import World

guidelines_bp = Blueprint('guidelines', __name__, url_prefix='/guidelines')

@guidelines_bp.route('/', methods=['GET'])
def all_guidelines():
    """Display all guidelines, optionally filtered by world_id."""
    from app.models.guideline import Guideline

    # Get world_id filter from query parameters
    world_id = request.args.get('world_id', type=int)
    selected_world = None

    # Build query
    query = db.session.query(Guideline, World).join(
        World, Guideline.world_id == World.id
    )

    # Apply world filter if specified
    if world_id:
        query = query.filter(Guideline.world_id == world_id)
        selected_world = World.query.get(world_id)

    guidelines = query.order_by(World.name, Guideline.title).all()

    # Group guidelines by world for better display
    guidelines_by_world = {}
    for guideline, world in guidelines:
        if world.name not in guidelines_by_world:
            guidelines_by_world[world.name] = {
                'world': world,
                'guidelines': []
            }
        guidelines_by_world[world.name]['guidelines'].append(guideline)

    return render_template('guidelines_all.html',
                         guidelines_by_world=guidelines_by_world,
                         total_guidelines=len(guidelines),
                         selected_world=selected_world,
                         world_id=world_id)