"""
Locks the Phase2Extractor entity-source mapping after the retirement of the
combined 'actions_events' extraction type (2026-07-10).

Step 3 stores actions and events in temporary_rdf_storage under one
extraction_type, 'temporal_dynamics_enhanced', discriminated by entity_type
('actions' / 'events'; the other values there are causal_chains,
allen_relations, timeline). The prior mapping read 'actions' from the never
populated 'actions_events' extraction_type (always empty, so Step-4 provision
linking received actions=[]) and lumped every temporal row under 'events'.

_get_all_case_entities is DB-bound, so the test drives it with a recording
TemporaryRDFStorage stub and asserts the query shape and the split.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.synthesis.phase2_extractor import Phase2Extractor

EXPECTED_KEYS = {
    'roles', 'states', 'resources', 'principles', 'obligations',
    'constraints', 'capabilities', 'actions', 'events',
}


class _RecordingQuery:
    """Stands in for TemporaryRDFStorage.query; records filter_by kwargs."""

    def __init__(self, results_for):
        self._results_for = results_for
        self.calls = []

    def filter_by(self, **kwargs):
        self.calls.append(kwargs)
        results = self._results_for(kwargs)
        return SimpleNamespace(all=lambda: results)


def test_actions_and_events_split_from_temporal_dynamics(monkeypatch):
    action_row = SimpleNamespace(entity_type='actions', entity_label='Design Approach Selection')
    event_row = SimpleNamespace(entity_type='events', entity_label='Construction Worker Injury')

    def results_for(kwargs):
        if kwargs.get('extraction_type') == 'temporal_dynamics_enhanced':
            return {'actions': [action_row], 'events': [event_row]}.get(kwargs.get('entity_type'), [])
        return []

    query = _RecordingQuery(results_for)
    monkeypatch.setattr(
        'app.services.synthesis.phase2_extractor.TemporaryRDFStorage',
        SimpleNamespace(query=query),
    )

    # unbound call: the method uses only self.case_id
    entities = Phase2Extractor._get_all_case_entities(SimpleNamespace(case_id=9))

    assert set(entities) == EXPECTED_KEYS
    assert entities['actions'] == [action_row]
    assert entities['events'] == [event_row]

    # The retired combined type must not be queried.
    assert all(c.get('extraction_type') != 'actions_events' for c in query.calls)

    # Exactly two temporal queries, one per entity_type discriminator.
    temporal_calls = [
        c for c in query.calls
        if c.get('extraction_type') == 'temporal_dynamics_enhanced'
    ]
    assert sorted(c['entity_type'] for c in temporal_calls) == ['actions', 'events']

    assert all(c['case_id'] == 9 for c in query.calls)


def test_step12_types_still_queried_by_extraction_type(monkeypatch):
    query = _RecordingQuery(lambda kwargs: [])
    monkeypatch.setattr(
        'app.services.synthesis.phase2_extractor.TemporaryRDFStorage',
        SimpleNamespace(query=query),
    )

    Phase2Extractor._get_all_case_entities(SimpleNamespace(case_id=7))

    step12_types = {
        c['extraction_type'] for c in query.calls
        if 'entity_type' not in c
    }
    assert step12_types == {
        'roles', 'states', 'resources', 'principles',
        'obligations', 'constraints', 'capabilities',
    }
