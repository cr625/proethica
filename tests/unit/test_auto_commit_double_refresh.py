"""
Unit tests for auto_commit_service._sync_to_ontserve (the "sync exactly once" fix).

_sync_to_ontserve syncs a case ontology to OntServe exactly once: versioned commits
sync via commit_case_versioned (which materializes edges + syncs disk->DB itself);
every other path (versioned-commit failure/exception, no published entities, or
non-versioned) falls back to the in-process commit_service._sync_ontology_to_db.
Earlier versions shelled out to a subprocess refresh; that was replaced by the
in-process call, so these assert on _sync_ontology_to_db, not subprocess.run.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path


@pytest.fixture
def auto_commit_service():
    """Create AutoCommitService with mocked dependencies."""
    with patch('app.services.commit.auto_commit_service.db'), \
         patch('app.services.commit.auto_commit_service.TemporaryRDFStorage'):
        from app.services.commit.auto_commit_service import AutoCommitService
        service = AutoCommitService.__new__(AutoCommitService)
        service._versioned_commit = True
        # __new__ bypasses __init__, so attributes the real __init__ sets must be provided
        # here. The sync/refresh path builds a case TTL path from ontologies_dir; set it to a
        # fake path consistent with the patched get_ontserve_base_path (no real I/O -- subprocess
        # and OntServeCommitService are mocked in the tests).
        service.ontserve_path = Path("/fake/OntServe")
        service.ontologies_dir = Path("/fake/OntServe/ontologies")
        yield service


class TestDoubleRefreshFix:
    """_sync_to_ontserve must sync the case ontology to OntServe exactly once:
    versioned-commit success syncs inside commit_case_versioned; every other path
    falls back to the in-process commit_service._sync_ontology_to_db (never both)."""

    @patch('app.services.extraction.edge_materialization.materialize_edges_on_ttl')
    @patch('app.services.commit.auto_commit_service.get_ontserve_base_path')
    def test_versioned_success_skips_fallback_sync(self, mock_base_path, mock_materialize, auto_commit_service):
        """commit_case_versioned succeeds -> the fallback _sync_ontology_to_db is skipped."""
        mock_base_path.return_value = Path("/fake/OntServe")

        mock_commit_service = MagicMock()
        mock_commit_service.commit_case_versioned.return_value = {
            'success': True, 'new_version': 2, 'versions_superseded': 1
        }

        with patch('app.services.commit.auto_commit_service.TemporaryRDFStorage') as mock_rdf:
            mock_rdf.query.filter_by.return_value.all.return_value = [MagicMock(id=1), MagicMock(id=2)]
            with patch('app.services.commit.ontserve_commit_service.OntServeCommitService',
                       return_value=mock_commit_service):
                auto_commit_service._versioned_commit = True
                auto_commit_service._sync_to_ontserve(7)

        mock_commit_service.commit_case_versioned.assert_called_once()
        # versioned commit already synced -> no second (fallback) sync
        mock_commit_service._sync_ontology_to_db.assert_not_called()

    @patch('app.services.extraction.edge_materialization.materialize_edges_on_ttl')
    @patch('app.services.commit.auto_commit_service.get_ontserve_base_path')
    def test_versioned_failure_runs_fallback_sync(self, mock_base_path, mock_materialize, auto_commit_service):
        """commit_case_versioned returns success=False -> fallback _sync_ontology_to_db runs."""
        mock_base_path.return_value = Path("/fake/OntServe")

        mock_commit_service = MagicMock()
        mock_commit_service.commit_case_versioned.return_value = {'success': False, 'error': 'DB connection failed'}
        mock_commit_service._sync_ontology_to_db.return_value = {'success': True}

        with patch('app.services.commit.auto_commit_service.TemporaryRDFStorage') as mock_rdf:
            mock_rdf.query.filter_by.return_value.all.return_value = [MagicMock(id=1)]
            with patch('app.services.commit.ontserve_commit_service.OntServeCommitService',
                       return_value=mock_commit_service):
                auto_commit_service._versioned_commit = True
                auto_commit_service._sync_to_ontserve(7)

        mock_commit_service._sync_ontology_to_db.assert_called_once()

    @patch('app.services.extraction.edge_materialization.materialize_edges_on_ttl')
    @patch('app.services.commit.auto_commit_service.get_ontserve_base_path')
    def test_versioned_commit_exception_runs_fallback_sync(self, mock_base_path, mock_materialize, auto_commit_service):
        """commit_case_versioned raises -> the inner handler falls back to _sync_ontology_to_db."""
        mock_base_path.return_value = Path("/fake/OntServe")

        mock_commit_service = MagicMock()
        mock_commit_service.commit_case_versioned.side_effect = Exception("versioned commit boom")
        mock_commit_service._sync_ontology_to_db.return_value = {'success': True}

        with patch('app.services.commit.auto_commit_service.TemporaryRDFStorage') as mock_rdf:
            mock_rdf.query.filter_by.return_value.all.return_value = [MagicMock(id=1)]
            with patch('app.services.commit.ontserve_commit_service.OntServeCommitService',
                       return_value=mock_commit_service):
                auto_commit_service._versioned_commit = True
                auto_commit_service._sync_to_ontserve(7)

        mock_commit_service._sync_ontology_to_db.assert_called_once()

    @patch('app.services.extraction.edge_materialization.materialize_edges_on_ttl')
    @patch('app.services.commit.auto_commit_service.get_ontserve_base_path')
    def test_non_versioned_runs_fallback_sync(self, mock_base_path, mock_materialize, auto_commit_service):
        """Non-versioned commits go straight to the in-process _sync_ontology_to_db."""
        mock_base_path.return_value = Path("/fake/OntServe")

        mock_commit_service = MagicMock()
        mock_commit_service._sync_ontology_to_db.return_value = {'success': True}

        with patch('app.services.commit.ontserve_commit_service.OntServeCommitService',
                   return_value=mock_commit_service):
            auto_commit_service._versioned_commit = False
            auto_commit_service._sync_to_ontserve(7)

        mock_commit_service._sync_ontology_to_db.assert_called_once()
        mock_commit_service.commit_case_versioned.assert_not_called()

    @patch('app.services.extraction.edge_materialization.materialize_edges_on_ttl')
    @patch('app.services.commit.auto_commit_service.get_ontserve_base_path')
    def test_no_entities_runs_fallback_sync(self, mock_base_path, mock_materialize, auto_commit_service):
        """No published entities -> versioned commit is skipped, fallback _sync_ontology_to_db runs."""
        mock_base_path.return_value = Path("/fake/OntServe")

        mock_commit_service = MagicMock()
        mock_commit_service._sync_ontology_to_db.return_value = {'success': True}

        with patch('app.services.commit.auto_commit_service.TemporaryRDFStorage') as mock_rdf:
            mock_rdf.query.filter_by.return_value.all.return_value = []
            with patch('app.services.commit.ontserve_commit_service.OntServeCommitService',
                       return_value=mock_commit_service):
                auto_commit_service._versioned_commit = True
                auto_commit_service._sync_to_ontserve(7)

        mock_commit_service._sync_ontology_to_db.assert_called_once()
        mock_commit_service.commit_case_versioned.assert_not_called()


class TestLazyTransientTtl:
    """The lean transient case TTL (_generate_case_ttl) is generated LAZILY: only in
    the fallback path (non-versioned, or a versioned-commit failure) where it is
    consumed, never eagerly on the happy versioned path where the OntServe writer
    overwrites it. _sync_to_ontserve takes entities/results to build it on demand."""

    @patch('app.services.extraction.edge_materialization.materialize_edges_on_ttl')
    @patch('app.services.commit.auto_commit_service.get_ontserve_base_path')
    def test_versioned_success_skips_transient_ttl(self, mock_base_path, mock_materialize, auto_commit_service):
        """Versioned commit succeeds -> the lean transient TTL is NOT generated."""
        mock_base_path.return_value = Path("/fake/OntServe")
        auto_commit_service._generate_case_ttl = MagicMock(name="_generate_case_ttl")

        mock_commit_service = MagicMock()
        mock_commit_service.commit_case_versioned.return_value = {
            'success': True, 'new_version': 2, 'versions_superseded': 1
        }
        with patch('app.services.commit.auto_commit_service.TemporaryRDFStorage') as mock_rdf:
            mock_rdf.query.filter_by.return_value.all.return_value = [MagicMock(id=1)]
            with patch('app.services.commit.ontserve_commit_service.OntServeCommitService',
                       return_value=mock_commit_service):
                auto_commit_service._versioned_commit = True
                auto_commit_service._sync_to_ontserve(7, entities=[MagicMock()], results=[MagicMock()])

        auto_commit_service._generate_case_ttl.assert_not_called()

    @patch('app.services.extraction.edge_materialization.materialize_edges_on_ttl')
    @patch('app.services.commit.auto_commit_service.get_ontserve_base_path')
    def test_versioned_failure_builds_transient_ttl(self, mock_base_path, mock_materialize, auto_commit_service):
        """Versioned commit fails -> the fallback builds the lean transient TTL before sync."""
        mock_base_path.return_value = Path("/fake/OntServe")
        auto_commit_service._generate_case_ttl = MagicMock(name="_generate_case_ttl")

        mock_commit_service = MagicMock()
        mock_commit_service.commit_case_versioned.return_value = {'success': False, 'error': 'boom'}
        mock_commit_service._sync_ontology_to_db.return_value = {'success': True}
        entities, results = [MagicMock()], [MagicMock()]
        with patch('app.services.commit.auto_commit_service.TemporaryRDFStorage') as mock_rdf:
            mock_rdf.query.filter_by.return_value.all.return_value = [MagicMock(id=1)]
            with patch('app.services.commit.ontserve_commit_service.OntServeCommitService',
                       return_value=mock_commit_service):
                auto_commit_service._versioned_commit = True
                auto_commit_service._sync_to_ontserve(7, entities=entities, results=results)

        auto_commit_service._generate_case_ttl.assert_called_once_with(7, entities, results)
        mock_commit_service._sync_ontology_to_db.assert_called_once()

    @patch('app.services.extraction.edge_materialization.materialize_edges_on_ttl')
    @patch('app.services.commit.auto_commit_service.get_ontserve_base_path')
    def test_temporal_path_no_results_skips_regeneration(self, mock_base_path, mock_materialize, auto_commit_service):
        """The temporal path calls _sync_to_ontserve() without results (it wrote its
        own TTL); the fallback must not try to regenerate from missing results."""
        mock_base_path.return_value = Path("/fake/OntServe")
        auto_commit_service._generate_case_ttl = MagicMock(name="_generate_case_ttl")

        mock_commit_service = MagicMock()
        mock_commit_service._sync_ontology_to_db.return_value = {'success': True}
        with patch('app.services.commit.ontserve_commit_service.OntServeCommitService',
                   return_value=mock_commit_service):
            auto_commit_service._versioned_commit = False
            auto_commit_service._sync_to_ontserve(7)  # no entities/results

        auto_commit_service._generate_case_ttl.assert_not_called()
        mock_commit_service._sync_ontology_to_db.assert_called_once()


class TestMCPClientSharedTransport:
    """Test that ExternalMCPClient shares the transport singleton."""

    def test_external_client_uses_singleton(self):
        """ExternalMCPClient without custom URL uses shared transport."""
        from app.services.ontserve.mcp_transport import MCPTransport
        with patch('app.services.ontserve.external_mcp_client.get_mcp_transport') as mock_get:
            mock_transport = MagicMock(spec=MCPTransport)
            mock_transport.base_url = "http://localhost:8082"
            mock_get.return_value = mock_transport

            from app.services.ontserve.external_mcp_client import ExternalMCPClient
            client = ExternalMCPClient()
            assert client.transport is mock_transport
            mock_get.assert_called_once()

    def test_external_client_custom_url_creates_new(self):
        """ExternalMCPClient with custom URL creates its own transport."""
        from app.services.ontserve.mcp_transport import MCPTransport
        with patch('app.services.ontserve.external_mcp_client.get_mcp_transport') as mock_get:
            with patch('app.services.ontserve.external_mcp_client.MCPTransport') as mock_cls:
                mock_cls.return_value = MagicMock(base_url="http://custom:9000")
                from app.services.ontserve.external_mcp_client import ExternalMCPClient
                client = ExternalMCPClient(server_url="http://custom:9000")
                mock_get.assert_not_called()
                mock_cls.assert_called_once_with(base_url="http://custom:9000")
