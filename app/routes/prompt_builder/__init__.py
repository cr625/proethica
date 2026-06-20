"""Prompt Builder blueprint package -- advanced prompt-template management routes."""

from flask import Blueprint

prompt_builder_bp = Blueprint('prompt_builder', __name__, url_prefix='/prompt-builder')

from app.routes.prompt_builder.template_routes import register_template_routes
from app.routes.prompt_builder.example_routes import register_example_routes
from app.routes.prompt_builder.registry_routes import register_registry_routes

register_template_routes(prompt_builder_bp)
register_example_routes(prompt_builder_bp)
register_registry_routes(prompt_builder_bp)

__all__ = ['prompt_builder_bp']
