"""Collections of Flask blueprints grouped by domain."""

from app.blueprints.admin import ADMIN_BLUEPRINTS
from app.blueprints.annotations import ANNOTATION_BLUEPRINTS
from app.blueprints.core import CORE_BLUEPRINTS
from app.blueprints.scenarios import SCENARIO_BLUEPRINTS

__all__ = [
    "ADMIN_BLUEPRINTS",
    "ANNOTATION_BLUEPRINTS",
    "CORE_BLUEPRINTS",
    "SCENARIO_BLUEPRINTS",
]
