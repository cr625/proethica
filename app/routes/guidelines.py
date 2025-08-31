"""
Guidelines routes for displaying all guidelines across all worlds.
"""

from flask import Blueprint, render_template
from app.models import db
from app.models import Document
from app.models.world import World

guidelines_bp = Blueprint('guidelines', __name__, url_prefix='/guidelines')

@guidelines_bp.route('/', methods=['GET'])
def all_guidelines():
    """Display all guidelines from all worlds."""
    # Get all guidelines from Guidelines table
    from app.models.guideline import Guideline
    guidelines = db.session.query(Guideline, World).join(
        World, Guideline.world_id == World.id
    ).order_by(
        World.name, Guideline.title
    ).all()
    
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
                         total_guidelines=len(guidelines))