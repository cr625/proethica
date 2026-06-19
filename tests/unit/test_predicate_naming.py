"""R3 guard test: pin the snake_case -> camelCase predicate contract.

The edge materializers (resource_edges, participant_edges, obligation_edges,
rpo_edges, defeasibility_pipeline) hardcode the camelCase predicate names they read
off the committed graph / rdf_json_ld props. The storage and commit converters must
keep producing exactly those names. This test fails loudly if the single shared
converter (app/utils/predicate_naming) drifts, converting the old silent writer<->
reader desync (the `activePeriod` -> `activeperiod` mangling class of bug) into a
caught regression.
"""
from app.services.extraction.extraction_graph import _to_camel_case
from app.utils.predicate_naming import to_camel_case

# snake_case emit field -> camelCase predicate the readers/stored props expect.
CONTRACT = {
    'state_class': 'stateClass',
    'state_category': 'stateCategory',
    'activation_conditions': 'activationConditions',
    'termination_conditions': 'terminationConditions',
    'triggering_event': 'triggeringEvent',
    'active_period': 'activePeriod',
    'obligation_class': 'obligationClass',
    'obligation_statement': 'obligationStatement',
    'obligated_party': 'obligatedParty',
    'constrained_entity': 'constrainedEntity',
    'possessed_by': 'possessedBy',
    'invoked_by': 'invokedBy',
    'compliance_status': 'complianceStatus',
    'temporal_scope': 'temporalScope',
    'capability_class': 'capabilityClass',
    'principle_class': 'principleClass',
    'concrete_expression': 'concreteExpression',
    'resource_class': 'resourceClass',
    'role_class': 'roleClass',
    'role_category': 'roleCategory',
    'source_text': 'sourceText',
    'text_references': 'textReferences',
}

# already-camelCase props keys must pass through UNCHANGED (the lowercasing bug).
PASSTHROUGH = ['stateClass', 'activePeriod', 'obligationStatement', 'roleClass',
               'sourceText', 'confidence', 'interpretation']


def test_snake_to_camel_contract():
    for snake, camel in CONTRACT.items():
        assert to_camel_case(snake) == camel, f"{snake} -> {to_camel_case(snake)!r}, expected {camel!r}"


def test_idempotent_on_already_camel():
    for k in PASSTHROUGH:
        assert to_camel_case(k) == k, f"{k} was mangled to {to_camel_case(k)!r}"


def test_both_call_sites_delegate_to_shared():
    """extraction_graph._to_camel_case and ontserve_commit_service._camelCase must
    both agree with the shared converter, so storage and commit cannot drift."""
    from app.services.commit.ontserve_commit_service import OntServeCommitService
    svc = OntServeCommitService.__new__(OntServeCommitService)
    for snake in list(CONTRACT) + PASSTHROUGH:
        assert _to_camel_case(snake) == to_camel_case(snake)
        assert svc._camelCase(snake) == to_camel_case(snake)
