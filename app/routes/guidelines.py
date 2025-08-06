"""
Guidelines routes for displaying all guidelines across all worlds.
"""

from flask import Blueprint, render_template
from app.models import db
from app.models.document import Document
from app.models.world import World

guidelines_bp = Blueprint('guidelines', __name__, url_prefix='/guidelines')

@guidelines_bp.route('/', methods=['GET'])
def all_guidelines():
    """Display all guidelines from all worlds."""
    # Get all guideline documents
    guidelines = db.session.query(Document, World).join(
        World, Document.world_id == World.id
    ).filter(
        Document.document_type == "guideline"
    ).order_by(
        World.name, Document.title
    ).all()
    
    # Group guidelines by world for better display
    guidelines_by_world = {}
    for doc, world in guidelines:
        if world.name not in guidelines_by_world:
            guidelines_by_world[world.name] = {
                'world': world,
                'guidelines': []
            }
        guidelines_by_world[world.name]['guidelines'].append(doc)
    
    return render_template('guidelines_all.html', 
                         guidelines_by_world=guidelines_by_world,
                         total_guidelines=len(guidelines))