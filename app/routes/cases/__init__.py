"""Cases blueprint package -- case management routes."""

from flask import Blueprint

bp = Blueprint('cases', __name__, url_prefix='/cases')
cases_bp = bp  # Alias for app/__init__.py compatibility

from app.routes.cases.listing import register_listing_routes
from app.routes.cases.view import register_view_routes
from app.routes.cases.creation_forms import register_creation_form_routes
from app.routes.cases.creation_processing import register_creation_processing_routes
from app.routes.cases.edit import register_edit_routes
from app.routes.cases.save_view import register_save_view_routes
from app.routes.cases.scenario_legacy import register_scenario_legacy_routes
from app.routes.cases.direct_scenario import register_direct_scenario_routes
from app.routes.cases.agent_creation import register_agent_creation_routes
from app.routes.cases.structure_embeddings import register_structure_embedding_routes
from app.routes.cases.pipeline import register_pipeline_routes

register_listing_routes(bp)
register_view_routes(bp)
register_creation_form_routes(bp)
register_creation_processing_routes(bp)
register_edit_routes(bp)
register_save_view_routes(bp)
register_scenario_legacy_routes(bp)
register_direct_scenario_routes(bp)
register_agent_creation_routes(bp)
register_structure_embedding_routes(bp)
register_pipeline_routes(bp)


def init_cases_csrf_exemption(app):
    """Exempt specific case routes from CSRF protection."""
    if hasattr(app, 'csrf') and app.csrf:
        for view_name in [
            'cases.generate_direct_scenario',
            'cases.clear_scenario',
            'cases.generate_case_embeddings',
        ]:
            app.csrf.exempt(view_name)
