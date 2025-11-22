"""Scenario-related blueprint registrations."""

from typing import Dict, List, Tuple
from flask import Blueprint

from app.routes.scenario_pipeline import interactive_scenario_bp
from app.routes.scenario_pipeline.entity_review import bp as entity_review_bp
from app.routes.scenario_pipeline.step4 import bp as step4_bp
from app.routes.scenario_pipeline.step5 import bp as step5_bp
from app.routes.scenarios import scenarios_bp

BlueprintRegistration = Tuple[Blueprint, Dict]

SCENARIO_BLUEPRINTS: List[BlueprintRegistration] = [
    (scenarios_bp, {"url_prefix": "/scenarios"}),
    (interactive_scenario_bp, {}),
    (entity_review_bp, {"url_prefix": "/scenario_pipeline"}),
    (step4_bp, {}),
    (step5_bp, {}),
]
