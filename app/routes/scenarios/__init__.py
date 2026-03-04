"""
DEPRECATED: Standalone Scenarios Route (December 2025)

This route handles standalone scenarios created within a world/domain.
It has been removed from main navigation but routes are preserved for:
- Existing deep links
- Future per-domain scenario authoring capability

Current focus: Case-derived scenarios via /scenario_pipeline/case/<id>/step5

Templates archived to: app/templates/archive/scenarios/

To restore:
1. Move templates back from archive/scenarios/ to templates/
2. Uncomment nav link in base.html (search for "Scenarios route archived")
3. Remove this deprecation notice

Database: 2 existing scenarios remain in `scenarios` table (harmless)
"""

from flask import Blueprint

bp = Blueprint('scenarios', __name__, url_prefix='/scenarios')
scenarios_bp = bp  # Alias for app/__init__.py compatibility

from app.routes.scenarios.core import register_core_routes
from app.routes.scenarios.characters import register_character_routes
from app.routes.scenarios.resources import register_resource_routes
from app.routes.scenarios.actions import register_action_routes
from app.routes.scenarios.events import register_event_routes
from app.routes.scenarios.decisions import register_decision_routes

register_core_routes(bp)
register_character_routes(bp)
register_resource_routes(bp)
register_action_routes(bp)
register_event_routes(bp)
register_decision_routes(bp)
