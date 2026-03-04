from flask import Blueprint

bp = Blueprint('worlds', __name__, url_prefix='/worlds')
worlds_bp = bp  # Alias for app/__init__.py compatibility

from app.routes.worlds.core import register_core_routes
from app.routes.worlds.guidelines import register_guideline_routes
from app.routes.worlds.triples import register_triple_routes
from app.routes.worlds.concepts import register_concept_routes
from app.routes.worlds.helpers import register_helper_routes

register_core_routes(bp)
register_guideline_routes(bp)
register_triple_routes(bp)
register_concept_routes(bp)
register_helper_routes(bp)

from app.routes.worlds.extraction import worlds_extract_only_bp
