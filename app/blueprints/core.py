"""Core blueprint registrations for the ProEthica application."""

from typing import Dict, List, Tuple
from flask import Blueprint

from app.routes.agent import agent_bp
from app.routes.cases import cases_bp
from app.routes.characters import characters_bp
from app.routes.conditions import conditions_bp
from app.routes.dashboard import dashboard_bp
from app.routes.debug import debug_bp
from app.routes.debug_env import debug_env_bp
from app.routes.documents import documents_bp
from app.routes.domains import domains_bp
from app.routes.events import events_bp
from app.routes.experiment import experiment_bp
from app.routes.guidelines import guidelines_bp
from app.routes.index import index_bp
from app.routes.ontology import ontology_bp
from app.routes.provenance import provenance_bp
from app.routes.reasoning import reasoning_bp
from app.routes.resources import resources_bp
from app.routes.roles import roles_bp
from app.routes.simulation import simulation_bp
from app.routes.test_routes import test_bp
from app.routes.type_management import type_management_bp
from app.routes.wizard import wizard_bp
from app.routes.worlds import worlds_bp
from app.routes.worlds_extract_only import worlds_extract_only_bp
from app.routes.document_structure import doc_structure_bp
from app.routes.auth import auth_bp

BlueprintRegistration = Tuple[Blueprint, Dict]

CORE_BLUEPRINTS: List[BlueprintRegistration] = [
    (index_bp, {}),
    (auth_bp, {}),
    (dashboard_bp, {"url_prefix": "/dashboard"}),
    (worlds_bp, {"url_prefix": "/worlds"}),
    (domains_bp, {"url_prefix": "/domains"}),
    (roles_bp, {"url_prefix": "/roles"}),
    (resources_bp, {"url_prefix": "/resources"}),
    (conditions_bp, {"url_prefix": "/conditions"}),
    (characters_bp, {"url_prefix": "/characters"}),
    (events_bp, {"url_prefix": "/events"}),
    (simulation_bp, {"url_prefix": "/simulation"}),
    (ontology_bp, {"url_prefix": "/ontology"}),
    (debug_bp, {"url_prefix": "/debug"}),
    (documents_bp, {"url_prefix": "/documents"}),
    (cases_bp, {"url_prefix": "/cases"}),
    (doc_structure_bp, {}),
    (experiment_bp, {"url_prefix": "/experiment"}),
    (type_management_bp, {}),
    (debug_env_bp, {}),
    (wizard_bp, {}),
    (test_bp, {}),
    (guidelines_bp, {}),
    (worlds_extract_only_bp, {}),
    (agent_bp, {}),
    (reasoning_bp, {}),
    (provenance_bp, {}),
]
