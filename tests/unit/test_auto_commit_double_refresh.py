"""
Unit tests for auto_commit_service._sync_to_ontserve double-refresh fix.

Verifies that:
- When commit_case_versioned succeeds, the subprocess refresh is skipped
- When commit_case_versioned fails, the subprocess refresh runs as fallback
- Non-versioned commits always run the subprocess refresh
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path


@pytest.fixture
def auto_commit_service():
    """Create AutoCommitService with mocked dependencies."""
    with patch('app.services.auto_commit_service.db'), \
         patch('app.services.auto_commit_service.TemporaryRDFStorage'):
        from app.services.auto_commit_service import AutoCommitService
        service = AutoCommitService.__new__(AutoCommitService)
        service._versioned_commit = True
        yield service


class TestDoubleRefreshFix:
    """Test that _sync_to_ontserve doesn't run refresh twice."""

    @patch('app.services.auto_commit_service.get_ontserve_base_path')
    def test_versioned_success_skips_subprocess(self, mock_base_path, auto_commit_service):
        """When commit_case_versioned succeeds, subprocess refresh is skipped."""
        mock_base_path.return_value = Path("/fake/OntServe")

        mock_commit_service = MagicMock()
        mock_commit_service.commit_case_versioned.return_value = {
            'success': True, 'new_version': 2, 'versions_superseded': 1
        }

        mock_entities = MagicMock()
        mock_entities.__iter__ = MagicMock(return_value=iter([MagicMock(id=1), MagicMock(id=2)]))
        mock_entities.__bool__ = MagicMock(return_value=True)

        with patch('app.services.auto_commit_service.TemporaryRDFStorage') as mock_rdf:
            mock_rdf.query.filter_by.return_value.all.return_value = mock_entities
            with patch('app.services.ontserve_commit_service.OntServeCommitService',
                       return_value=mock_commit_service):
                with patch('subprocess.run') as mock_subprocess:
                    auto_commit_service._versioned_commit = True
                    auto_commit_service._sync_to_ontserve(7)

                    mock_commit_service.commit_case_versioned.assert_called_once()
                    # subprocess should NOT have been called (versioned refresh already done)
                    mock_subprocess.assert_not_called()

    @patch('app.services.auto_commit_service.get_ontserve_base_path')
    def test_versioned_failure_runs_subprocess_fallback(self, mock_base_path, auto_commit_service):
        """When commit_case_versioned fails, subprocess refresh runs as fallback."""
        mock_base_path.return_value = Path("/fake/OntServe")

        mock_commit_service = MagicMock()
        mock_commit_service.commit_case_versioned.return_value = {
            'success': False, 'error': 'DB connection failed'
        }

        mock_entities = MagicMock()
        mock_entities.__iter__ = MagicMock(return_value=iter([MagicMock(id=1)]))
        mock_entities.__bool__ = MagicMock(return_value=True)

        with patch('app.services.auto_commit_service.TemporaryRDFStorage') as mock_rdf:
            mock_rdf.query.filter_by.return_value.all.return_value = mock_entities
            with patch('app.services.ontserve_commit_service.OntServeCommitService',
                       return_value=mock_commit_service):
                with patch('subprocess.run') as mock_subprocess:
                    mock_subprocess.return_value = MagicMock(returncode=0)
                    auto_commit_service._versioned_commit = True
                    auto_commit_service._sync_to_ontserve(7)

                    # subprocess SHOULD run as fallback
                    mock_subprocess.assert_called_once()

    @patch('app.services.auto_commit_service.get_ontserve_base_path')
    def test_versioned_exception_runs_subprocess_fallback(self, mock_base_path, auto_commit_service):
        """When commit_case_versioned raises, subprocess refresh runs as fallback."""
        mock_base_path.return_value = Path("/fake/OntServe")

        with patch('app.services.auto_commit_service.TemporaryRDFStorage') as mock_rdf:
            mock_rdf.query.filter_by.return_value.all.return_value = [MagicMock(id=1)]
            with patch('app.services.ontserve_commit_service.OntServeCommitService',
                       side_effect=Exception("Import error")):
                with patch('subprocess.run') as mock_subprocess:
                    mock_subprocess.return_value = MagicMock(returncode=0)
                    auto_commit_service._versioned_commit = True
                    auto_commit_service._sync_to_ontserve(7)

                    # subprocess SHOULD run as fallback
                    mock_subprocess.assert_called_once()

    @patch('app.services.auto_commit_service.get_ontserve_base_path')
    def test_non_versioned_always_runs_subprocess(self, mock_base_path, auto_commit_service):
        """Non-versioned commits always use subprocess refresh."""
        mock_base_path.return_value = Path("/fake/OntServe")

        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value = MagicMock(returncode=0)
            auto_commit_service._versioned_commit = False
            auto_commit_service._sync_to_ontserve(7)

            # subprocess SHOULD run (no versioned commit path)
            mock_subprocess.assert_called_once()
            # Verify it called the refresh script with the right case name
            call_args = mock_subprocess.call_args[0][0]
            assert "refresh_entity_extraction.py" in call_args[1]
            assert "proethica-case-7" in call_args[2]

    @patch('app.services.auto_commit_service.get_ontserve_base_path')
    def test_no_entities_still_runs_subprocess(self, mock_base_path, auto_commit_service):
        """When no published entities found, subprocess still runs for TTL sync."""
        mock_base_path.return_value = Path("/fake/OntServe")

        with patch('app.services.auto_commit_service.TemporaryRDFStorage') as mock_rdf:
            mock_rdf.query.filter_by.return_value.all.return_value = []
            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.return_value = MagicMock(returncode=0)
                auto_commit_service._versioned_commit = True
                auto_commit_service._sync_to_ontserve(7)

                # subprocess SHOULD run (no entities means versioned commit was skipped)
                mock_subprocess.assert_called_once()


class TestMCPClientSharedTransport:
    """Test that ExternalMCPClient and OntServeMCPClient share transport singleton."""

    def test_external_client_uses_singleton(self):
        """ExternalMCPClient without custom URL uses shared transport."""
        from app.services.mcp_transport import MCPTransport
        with patch('app.services.external_mcp_client.get_mcp_transport') as mock_get:
            mock_transport = MagicMock(spec=MCPTransport)
            mock_transport.base_url = "http://localhost:8082"
            mock_get.return_value = mock_transport

            from app.services.external_mcp_client import ExternalMCPClient
            client = ExternalMCPClient()
            assert client.transport is mock_transport
            mock_get.assert_called_once()

    def test_external_client_custom_url_creates_new(self):
        """ExternalMCPClient with custom URL creates its own transport."""
        from app.services.mcp_transport import MCPTransport
        with patch('app.services.external_mcp_client.get_mcp_transport') as mock_get:
            with patch('app.services.external_mcp_client.MCPTransport') as mock_cls:
                mock_cls.return_value = MagicMock(base_url="http://custom:9000")
                from app.services.external_mcp_client import ExternalMCPClient
                client = ExternalMCPClient(server_url="http://custom:9000")
                mock_get.assert_not_called()
                mock_cls.assert_called_once_with(base_url="http://custom:9000")

    def test_ontserve_client_uses_singleton(self):
        """OntServeMCPClient without custom URL uses shared transport."""
        from app.services.mcp_transport import MCPTransport
        with patch('app.services.ontserve_mcp_client.get_mcp_transport') as mock_get:
            mock_transport = MagicMock(spec=MCPTransport)
            mock_transport.base_url = "http://localhost:8082"
            mock_get.return_value = mock_transport

            from app.services.ontserve_mcp_client import OntServeMCPClient
            client = OntServeMCPClient()
            assert client._transport is mock_transport
            assert client.mcp_url == "http://localhost:8082"

    def test_ontserve_client_custom_url_creates_new(self):
        """OntServeMCPClient with custom URL creates its own transport."""
        with patch('app.services.ontserve_mcp_client.get_mcp_transport') as mock_get:
            with patch('app.services.ontserve_mcp_client.MCPTransport') as mock_cls:
                mock_cls.return_value = MagicMock(base_url="http://custom:9000")
                from app.services.ontserve_mcp_client import OntServeMCPClient
                client = OntServeMCPClient(mcp_url="http://custom:9000")
                mock_get.assert_not_called()
                mock_cls.assert_called_once_with(base_url="http://custom:9000", timeout=30)
