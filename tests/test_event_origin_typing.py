"""ONT-4 (2026-07-01): Event origin-subclass commit typing.

Step 3 emits an event individual as ``proeth:Event`` plus ``proeth:eventType``
(outcome/exogenous/automatic) with no per-case subclass. The commit path must type
the individual to exactly one of the three disjoint core ORIGIN subclasses
(AgentCausedEvent / ExogenousEvent / AutomaticEvent) rather than leaving it bare
core:Event. These tests cover the pure resolver and the repointed category maps.
"""

from app.services.commit.ontserve_commit_service import resolve_event_origin_category
from app.services.extraction.schemas import CATEGORY_TO_ONTOLOGY_IRI, CORE_NS


class TestResolveEventOriginCategory:
    """The pure eventType -> origin-subclass-local-name resolver."""

    def test_outcome_maps_to_agent_caused(self):
        # Flat Step-3 JSON-LD shape (top-level proeth:eventType), the real emitted form.
        rdf = {'@type': 'proeth:Event', 'proeth:eventType': 'outcome'}
        assert resolve_event_origin_category(rdf) == 'AgentCausedEvent'

    def test_exogenous_maps_to_exogenous_event(self):
        assert resolve_event_origin_category({'proeth:eventType': 'exogenous'}) == 'ExogenousEvent'

    def test_automatic_maps_to_automatic_event(self):
        assert resolve_event_origin_category({'proeth:eventType': 'automatic'}) == 'AutomaticEvent'

    def test_case_and_whitespace_insensitive(self):
        assert resolve_event_origin_category({'proeth:eventType': '  Exogenous '}) == 'ExogenousEvent'

    def test_nested_properties_dict(self):
        rdf = {'properties': {'proeth:eventType': 'automatic'}}
        assert resolve_event_origin_category(rdf) == 'AutomaticEvent'

    def test_list_value_takes_first(self):
        assert resolve_event_origin_category({'proeth:eventType': ['outcome']}) == 'AgentCausedEvent'

    def test_absent_field_returns_none(self):
        # No eventType -> None, so the commit keeps the bare core:Event type.
        assert resolve_event_origin_category({'@type': 'proeth:Event'}) is None

    def test_unknown_value_returns_none(self):
        assert resolve_event_origin_category({'proeth:eventType': 'crisis'}) is None

    def test_empty_and_none_inputs(self):
        assert resolve_event_origin_category({}) is None
        assert resolve_event_origin_category(None) is None

    def test_commit_decision_mirrors_resolver(self):
        # Faithfully mirrors the commit's inline decision: keep bare Event AND add the
        # origin subclass when eventType resolves (additive; both types asserted).
        for ev_type, expected_types in [
            ('outcome', {'Event', 'AgentCausedEvent'}),
            ('exogenous', {'Event', 'ExogenousEvent'}),
            ('automatic', {'Event', 'AutomaticEvent'}),
            ('unknown', {'Event'}),  # unresolved -> only the bare Event type
        ]:
            resolved_cat = 'Event'
            types = set()
            if resolved_cat:
                types.add(resolved_cat)
            if resolved_cat == 'Event':
                origin = resolve_event_origin_category({'proeth:eventType': ev_type})
                if origin:
                    types.add(origin)
            assert types == expected_types


class TestCategoryMapRepoint:
    """ONT-4 repointed the dead topical maps (schemas.py)."""

    def test_actions_map_is_empty_action_is_bare(self):
        # Action is bare (no subtype); the former topical action map is retired.
        assert CATEGORY_TO_ONTOLOGY_IRI['actions'] == {}

    def test_events_map_is_the_three_core_origin_subclasses(self):
        assert CATEGORY_TO_ONTOLOGY_IRI['events'] == {
            'outcome': f'{CORE_NS}AgentCausedEvent',
            'exogenous': f'{CORE_NS}ExogenousEvent',
            'automatic': f'{CORE_NS}AutomaticEvent',
        }

    def test_events_map_targets_core_namespace_not_deprecated_topical(self):
        # No topical (deprecated intermediate) class survives in the events map.
        for iri in CATEGORY_TO_ONTOLOGY_IRI['events'].values():
            assert iri.startswith(CORE_NS)
            assert 'Event' in iri
