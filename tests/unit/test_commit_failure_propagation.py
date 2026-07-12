"""
Regression tests: a failed TTL write must not mark temp rows published.

commit_selected_entities previously appended the class/individuals-commit error
to results['errors'] and CONTINUED: every row was marked is_published=True and
the session committed, so a case could read as committed while its individuals
were absent from the case TTL (silent data loss that every later
recommit-from-temp_rdf sweep inherits). The fix aborts before the publish step
and returns success=False with the error; the outer except also rolls the
session back so a DB-origin failure cannot poison later queries.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.commit.ontserve_commit_service import OntServeCommitService

_MODULE = 'app.services.commit.ontserve_commit_service'


class _Row:
    """Minimal stand-in for a TemporaryRDFStorage row."""

    def __init__(self, row_id, storage_type):
        self.id = row_id
        self.storage_type = storage_type
        self.rdf_json_ld = {}
        self.is_published = False
        self.committed_at = None
        self.content_hash = None
        self.entity_uri = f"http://proethica.org/ontology/case/test#e{row_id}"
        self.entity_label = f"Entity {row_id}"
        self.entity_definition = "test definition"
        self.ontology_target = 'proethica-case-9'


def _service():
    svc = OntServeCommitService.__new__(OntServeCommitService)
    svc.ontologies_dir = Path('/fake/OntServe/ontologies')
    svc._record_conformance_provenance = MagicMock()
    svc._record_ontology_commit = MagicMock()
    return svc


def _patched_storage(rows):
    storage = MagicMock()
    storage.query.filter.return_value.all.return_value = rows
    storage.compute_content_hash.return_value = 'hash'
    return storage


def test_failed_individuals_commit_does_not_publish():
    rows = [_Row(1, 'individual'), _Row(2, 'individual')]
    svc = _service()
    svc._commit_individuals_to_case_ontology = MagicMock(
        return_value={'count': 0, 'error': 'disk full writing case TTL'})

    with patch(f'{_MODULE}.TemporaryRDFStorage', _patched_storage(rows)), \
         patch('app.services.extraction.conformance_gate.gate_case_ttl',
               return_value={'status': 'skipped'}), \
         patch('app.db') as mock_db:
        result = svc.commit_selected_entities(9, [1, 2])

    assert result['success'] is False
    assert 'disk full' in result['error']
    assert all(row.is_published is False for row in rows)
    mock_db.session.rollback.assert_called_once()
    mock_db.session.commit.assert_not_called()


def test_failed_class_commit_does_not_publish():
    rows = [_Row(3, 'class')]
    svc = _service()
    svc._commit_classes_to_intermediate = MagicMock(
        return_value={'count': 0, 'error': 'extended TTL write failed'})

    with patch(f'{_MODULE}.TemporaryRDFStorage', _patched_storage(rows)), \
         patch('app.db') as mock_db:
        result = svc.commit_selected_entities(9, [3])

    assert result['success'] is False
    assert 'extended TTL write failed' in result['error']
    assert rows[0].is_published is False
    mock_db.session.rollback.assert_called_once()
    mock_db.session.commit.assert_not_called()


def test_successful_commit_still_publishes():
    """Positive control: the guard must not fire on a clean commit."""
    rows = [_Row(4, 'individual')]
    svc = _service()
    svc._commit_individuals_to_case_ontology = MagicMock(
        return_value={'count': 1, 'merged': 0, 'file': 'x.ttl',
                      'role_axis_vetoes': 0, 'qc_edges_dropped': 0,
                      'role_axis_vetoes_post_canonicalization': 0})
    svc._sync_ontology_to_db = MagicMock(return_value={'success': True})

    with patch(f'{_MODULE}.TemporaryRDFStorage', _patched_storage(rows)), \
         patch('app.services.extraction.conformance_gate.gate_case_ttl',
               return_value={'status': 'skipped'}), \
         patch('app.services.commit.precedent_features.update_entity_classes_from_storage',
               return_value={}), \
         patch('app.db') as mock_db:
        result = svc.commit_selected_entities(9, [4])

    assert result['success'] is True
    assert result['errors'] == []
    assert rows[0].is_published is True
    mock_db.session.commit.assert_called()
    mock_db.session.rollback.assert_not_called()


def test_outer_exception_rolls_back_session():
    """A query-time exception must roll the session back (poisoned-session archetype)."""
    svc = _service()
    storage = MagicMock()
    storage.query.filter.side_effect = RuntimeError('db down')

    with patch(f'{_MODULE}.TemporaryRDFStorage', storage), \
         patch('app.db') as mock_db:
        result = svc.commit_selected_entities(9, [1])

    assert result['success'] is False
    assert 'db down' in result['error']
    mock_db.session.rollback.assert_called_once()
