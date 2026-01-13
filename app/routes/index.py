"""
Index route for the application.
"""

from flask import Blueprint, render_template, current_app, redirect, url_for, Response, session, request
from app.models.world import World
from app.models.scenario import Scenario
from app.models.guideline import Guideline
from app.models.document import Document
from app.routes.health import check_mcp

# Create a blueprint for the index routes
index_bp = Blueprint('index', __name__)


@index_bp.route('/set-domain/<int:domain_id>')
def set_domain(domain_id):
    """
    Set the currently selected domain in the session.
    Redirects back to the referring page or home.
    """
    # Verify domain exists
    domain = World.query.get(domain_id)
    if domain:
        session['selected_domain_id'] = domain_id

    # Redirect back to referring page or home
    next_url = request.referrer or url_for('index.index')
    return redirect(next_url)

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
        
        # Get case count for the quick start card - filtered by selected domain if set
        total_cases = 0
        try:
            # Get selected domain from session (also set by context processor)
            selected_domain_id = session.get('selected_domain_id')

            query = Document.query.filter(
                Document.document_type.in_(['case_study', 'case'])
            )

            # Filter by domain if one is selected
            if selected_domain_id:
                query = query.filter(Document.world_id == selected_domain_id)

            total_cases = query.count()
        except:
            pass

        # System status checks
        mcp_result = check_mcp()
        mcp_status = mcp_result.get('status') == 'up'
        embedding_status = True  # Could check embedding service
        last_backup_time = "2024-06-07"  # Could check actual backup

        return render_template('index.html',
            worlds=worlds,
            ontologies=ontologies,
            pending_reviews=pending_reviews,
            concept_count=concept_count,
            total_cases=total_cases,
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
