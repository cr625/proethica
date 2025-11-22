"""Administrative blueprint registrations."""

from typing import Dict, List, Tuple
from flask import Blueprint

from app.routes.admin import admin_bp
from app.routes.admin_prompts import admin_prompts_bp
from app.routes.prompt_builder import prompt_builder_bp

BlueprintRegistration = Tuple[Blueprint, Dict]

ADMIN_BLUEPRINTS: List[BlueprintRegistration] = [
    (admin_bp, {}),
    (admin_prompts_bp, {}),
    (prompt_builder_bp, {}),
]
