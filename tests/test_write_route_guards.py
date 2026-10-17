"""
Write-route authentication inventory.

Every route that accepts POST, PUT, PATCH, or DELETE must carry an explicit
authentication decision: one of the `app.utils.environment_auth` decorators
(which record `_proethica_auth_guard` on the view), Flask-Login's
`login_required`, or an entry in KNOWN_UNGUARDED_WRITE_ENDPOINTS below.

The known-unguarded set is a debt registry, not an endorsement. It records
the endpoints that had no guard when the inventory was created (2026-10-17:
47 endpoints registered below, of 150 write rules). Removing an endpoint
from the set by adding
a decorator is the intended direction; adding a new endpoint to the set
requires a stated reason in the same change. A new write route with no guard
and no registry entry fails this test.
"""
import inspect

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

AUTH_DECORATOR_NAMES = {
    "login_required",
    "auth_required_for_write",
    "auth_required_for_llm",
    "auth_required_for_create",
    "auth_optional",
    "admin_required_production",
    "development_only",
}

# Endpoints with no authentication decorator, grouped by the reason recorded
# at inventory time. Participant study routes authenticate by session code,
# not by login; authentication routes must themselves be reachable logged out.
KNOWN_UNGUARDED_WRITE_ENDPOINTS = {
    # Authentication entry points.
    "auth.login",
    "auth.register",
    # Validation-study participant flow (session-code authentication).
    "study.enroll",
    "study.orientation",
    "study.retrospective",
    "study.submit_evaluation",
    # Pipeline dashboard API (no guard at inventory; local-operator surface).
    "pipeline.api_add_to_queue",
    "pipeline.api_cancel_run",
    "pipeline.api_clear_queue",
    "pipeline.api_remove_from_queue",
    "pipeline.api_reprocess_case",
    "pipeline.api_retry_run",
    "pipeline.api_run_single_case",
    "pipeline.api_run_step4",
    "pipeline.api_set_injection_mode",
    "pipeline.api_start_queue_processing",
    "pipeline.api_update_queue_item",
    # Annotation and document APIs.
    "annotations.annotate_text",
    "api_document_annotations.approve_annotation",
    "api_document_annotations.clear_document_annotations",
    "api_document_annotations.reject_annotation",
    "api_documents.process_url",
    "api_documents.search_documents",
    # Legacy and read-via-POST case endpoints.
    "cases.dummy_edit_triples",
    "cases.dummy_edit_triples_alt",
    "cases.get_related_cases",
    "cases.process_url_pipeline",
    "cases.save_and_view_case",
    # Document-structure and experiment surfaces.
    "debug_env.reload_environment",
    "doc_structure.generate_embeddings",
    "doc_structure.generate_structure",
    "doc_structure.generate_term_links",
    "doc_structure.search_similar_sections",
    "experiment.cases",
    "experiment.conclusion_prediction_setup",
    "experiment.evaluate_prediction",
    "experiment.quick_predict",
    "experiment.run_conclusion_predictions",
    # Prompt-editor helpers and type management.
    "prompt_editor.render_template_with_case",
    "prompt_editor.resolve_template_variables",
    "type_management.batch_approve_concepts",
    "type_management.update_concept_type",
    # Worlds endpoints guarded on sibling routes but not these.
    "worlds.add_case",
    "worlds.add_ruleset",
    "worlds.delete_case",
    "worlds.delete_ruleset",
    "worlds.update_world",
}


def _source_decorators(func):
    """Decorator names on the original view function, through wrappers."""
    original = func
    seen = set()
    while hasattr(original, "__wrapped__") and id(original.__wrapped__) not in seen:
        seen.add(id(original))
        original = original.__wrapped__
    try:
        source = inspect.getsource(original)
    except (OSError, TypeError):
        return set()
    return {name for name in AUTH_DECORATOR_NAMES if f"@{name}" in source}


def test_every_write_route_has_an_auth_decision(app):
    unguarded = set()
    for rule in app.url_map.iter_rules():
        if not (rule.methods & WRITE_METHODS):
            continue
        view = app.view_functions[rule.endpoint]
        if getattr(view, "_proethica_auth_guard", None):
            continue
        if _source_decorators(view):
            continue
        unguarded.add(rule.endpoint)

    new_unguarded = unguarded - KNOWN_UNGUARDED_WRITE_ENDPOINTS
    assert not new_unguarded, (
        "Write routes without an authentication decorator or a registry "
        f"entry in KNOWN_UNGUARDED_WRITE_ENDPOINTS: {sorted(new_unguarded)}. "
        "Add an environment_auth/login_required decorator, or record the "
        "endpoint in the registry with a reason."
    )
    stale = KNOWN_UNGUARDED_WRITE_ENDPOINTS - unguarded
    assert not stale, (
        f"Registry entries that are now guarded and must be removed: "
        f"{sorted(stale)}"
    )
