"""
Step 4: Whole-Case Synthesis

Package initialization. Defines the 'step4' blueprint and registers all
sub-module routes.

Three-Part Synthesis:
  Part A: Code Provisions (References section)
  Part B: Questions & Conclusions
  Part C: Cross-Section Synthesis
"""

from flask import Blueprint

from app.routes.scenario_pipeline.step4.config import (  # noqa: F401
    STEP4_SECTION_TYPE, STEP4_DEFAULT_MODEL, STEP4_POWERFUL_MODEL,
    STEP4_EXTRACTION_TYPES, reset_step4_case_features,
)

bp = Blueprint('step4', __name__, url_prefix='/scenario_pipeline')

# --- Import helpers used as callbacks for sub-module registration ---
from app.routes.scenario_pipeline.step4.helpers import (  # noqa: E402
    get_all_case_entities,
    load_phase2_data,
    build_entity_foundation_for_phase4,
    load_canonical_points_for_phase4,
    load_conclusions_for_phase4,
    get_transformation_type_for_phase4,
    load_causal_links_for_phase4,
)

# --- Register route sub-modules defined in this package ---
from app.routes.scenario_pipeline.step4.views import register_view_routes  # noqa: E402
from app.routes.scenario_pipeline.step4.entity_mgmt import register_entity_mgmt_routes  # noqa: E402
from app.routes.scenario_pipeline.step4.provisions import register_provision_routes  # noqa: E402
from app.routes.scenario_pipeline.step4.precedents import register_precedent_routes  # noqa: E402
from app.routes.scenario_pipeline.step4.qc_extraction import register_qc_routes  # noqa: E402
from app.routes.scenario_pipeline.step4.decision_legacy import register_decision_legacy_routes  # noqa: E402
from app.routes.scenario_pipeline.step4.entity_analysis import register_entity_analysis_routes  # noqa: E402
from app.routes.scenario_pipeline.step4.synthesis import register_synthesis_routes  # noqa: E402

register_view_routes(bp)
register_entity_mgmt_routes(bp)
register_provision_routes(bp)
register_precedent_routes(bp)
register_qc_routes(bp)
register_decision_legacy_routes(bp)
register_entity_analysis_routes(bp)
register_synthesis_routes(bp)

# --- Register callback-based sub-modules (existing step4_*.py files, now in step4/) ---
from app.routes.scenario_pipeline.step4.questions import register_question_routes  # noqa: E402
from app.routes.scenario_pipeline.step4.conclusions import register_conclusion_routes  # noqa: E402
from app.routes.scenario_pipeline.step4.transformation import register_transformation_routes  # noqa: E402
from app.routes.scenario_pipeline.step4.rich_analysis import register_rich_analysis_routes  # noqa: E402
from app.routes.scenario_pipeline.step4.phase3 import register_phase3_routes  # noqa: E402
from app.routes.scenario_pipeline.step4.phase4 import register_phase4_routes  # noqa: E402
from app.routes.scenario_pipeline.step4.complete_synthesis import register_complete_synthesis_routes  # noqa: E402
from app.routes.scenario_pipeline.step4.run_all import register_run_all_routes  # noqa: E402

register_question_routes(bp, get_all_case_entities)
register_conclusion_routes(bp, get_all_case_entities)
register_transformation_routes(bp, get_all_case_entities)
register_rich_analysis_routes(bp, get_all_case_entities)
register_phase3_routes(bp, get_all_case_entities, load_phase2_data)
register_phase4_routes(
    bp,
    build_entity_foundation_for_phase4,
    load_canonical_points_for_phase4,
    load_conclusions_for_phase4,
    get_transformation_type_for_phase4,
    load_causal_links_for_phase4
)
register_complete_synthesis_routes(
    bp,
    build_entity_foundation_for_phase4,
    load_canonical_points_for_phase4,
    load_conclusions_for_phase4,
    get_transformation_type_for_phase4,
    load_causal_links_for_phase4
)
_run_all_funcs = register_run_all_routes(bp)
run_complete_synthesis_func = _run_all_funcs['run_complete_synthesis']
run_complete_synthesis_stream_func = _run_all_funcs['run_complete_synthesis_stream']


def init_step4_csrf_exemption(app):
    """Exempt Step 4 synthesis routes from CSRF protection."""
    if hasattr(app, 'csrf') and app.csrf:
        # Exempt by view name (string-based) -- avoids import issues
        csrf_exempt_views = [
            # Entity management
            'step4.save_streaming_results',
            'step4.clear_step4_data',
            'step4.commit_step4_entities',
            # Provision extraction
            'step4.extract_provisions_streaming',
            'step4.extract_provisions_individual',
            # Precedent extraction
            'step4.extract_precedents_streaming',
            'step4.extract_precedents_individual',
            # Q&C extraction
            'step4.extract_qc_unified',
            'step4.extract_qc_unified_streaming',
            # Decision points (legacy)
            'step4.extract_decision_points',
            'step4.generate_arguments',
            # Synthesis
            'step4.synthesize_case',
            'step4.synthesize_complete',
            'step4.extract_decision_synthesis_individual',
            'step4.extract_narrative_individual',
            # Modular endpoints
            'step4.extract_questions_individual',
            'step4.extract_questions_streaming',
            'step4.extract_conclusions_individual',
            'step4.extract_conclusions_streaming',
            'step4.extract_transformation_individual',
            'step4.extract_transformation_streaming',
            'step4.extract_rich_analysis_individual',
            'step4.extract_rich_analysis_streaming',
            # Phase 3 synthesis endpoints
            'step4.synthesize_phase3_individual',
            'step4.synthesize_phase3_streaming',
            # Phase 4 narrative construction endpoints
            'step4.construct_phase4_individual',
            'step4.construct_phase4_streaming',
            'step4.get_phase4_data',
            # Complete synthesis streaming
            'step4.synthesize_complete_streaming',
            # Run all
            'step4.run_complete_synthesis',
            'step4.run_complete_synthesis_stream',
        ]

        from app.routes.scenario_pipeline.generate_scenario import generate_scenario_from_case
        app.csrf.exempt(generate_scenario_from_case)

        for view_name in csrf_exempt_views:
            app.csrf.exempt(view_name)
