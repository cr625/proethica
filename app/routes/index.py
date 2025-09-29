"""
Index route for the application.
"""

from flask import Blueprint, render_template, current_app, redirect, url_for, Response
from app.models.world import World
from app.models.scenario import Scenario
from app.models.guideline import Guideline

# Create a blueprint for the index routes
index_bp = Blueprint('index', __name__)

@index_bp.route('/')
def index():
    """
    Render the index page with statistics and system status.
    
    Returns:
        Rendered index template with data
    """
    try:
        # Get all worlds for the list
        worlds = World.query.all()
        
        # Get ontologies - handle if model doesn't exist
        ontologies = []
        try:
            from app.models.ontology import Ontology
            ontologies = Ontology.query.all()
        except:
            pass
        
        # Get pending reviews count and concept count
        pending_reviews = 0
        concept_count = 0
        try:
            from app.models.entity_triple import EntityTriple
            pending_reviews = EntityTriple.query.filter_by(
                needs_type_review=True,
                entity_type='guideline_concept'
            ).count()
            
            # Count total guideline concepts (ontology concepts)
            concept_count = EntityTriple.query.filter_by(
                entity_type='guideline_concept'
            ).count()
        except:
            pass
        
        # System status checks (mock for now)
        mcp_status = True  # Could check actual MCP server
        embedding_status = True  # Could check embedding service
        last_backup_time = "2024-06-07"  # Could check actual backup
        
        return render_template('index.html',
            worlds=worlds,
            ontologies=ontologies,
            pending_reviews=pending_reviews,
            concept_count=concept_count,
            mcp_status=mcp_status,
            embedding_status=embedding_status,
            last_backup_time=last_backup_time
        )
    except Exception as e:
        # Fallback to redirecting to worlds page if something fails
        current_app.logger.error(f"Error rendering index: {e}")
        return redirect(url_for('worlds.list_worlds'))

@index_bp.route('/about')
def about():
    """
    Render the about page.
    
    Returns:
        Rendered about template
    """
    return render_template('about.html')

@index_bp.route('/health')
def health():
    """
    Health check endpoint.

    Returns:
        Simple health check response
    """
    return {
        "status": "healthy",
        "environment": current_app.config.get('ENVIRONMENT', 'unknown'),
        "app_name": "ProEthica"
    }

@index_bp.route('/favicon.ico')
def favicon():
    """
    Return an empty favicon to prevent 404 errors.

    Returns:
        Empty response with icon content type
    """
    return Response(status=204)  # No Content response
