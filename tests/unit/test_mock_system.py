"""
Tests for the mock LLM system to verify it works correctly before using in extraction tests.
"""

import pytest
import json
from pathlib import Path


class TestMockLLMClient:
    """Tests for MockLLMClient fixture loading and response generation."""

    def test_mock_client_loads_fixtures(self, mock_llm_client):
        """Verify mock client loads all expected fixture files."""
        expected_fixtures = [
            'roles_facts', 'roles_discussion',
            'states_facts', 'states_discussion',
            'resources_facts', 'resources_discussion',
            'principles_facts', 'principles_discussion',
            'obligations_facts', 'obligations_discussion',
            'constraints_facts', 'constraints_discussion',
            'capabilities_facts', 'capabilities_discussion',
            'actions_events',
            'provisions', 'questions', 'conclusions', 'transformation',
            'participants', 'decision_points'
        ]

        for fixture_name in expected_fixtures:
            fixture = mock_llm_client._fixtures.get(fixture_name)
            assert fixture is not None, f"Missing fixture: {fixture_name}"

    def test_mock_client_returns_roles_response(self, mock_llm_client):
        """Verify mock client returns correct response for roles extraction."""
        response = mock_llm_client.call(
            prompt="Extract roles...",
            extraction_type='roles',
            section_type='facts'
        )

        assert response is not None
        assert hasattr(response, 'content')

        data = json.loads(response.content)
        assert 'new_role_classes' in data
        assert 'role_individuals' in data
        assert len(data['role_individuals']) > 0

    def test_mock_client_returns_states_response(self, mock_llm_client):
        """Verify mock client returns correct response for states extraction."""
        response = mock_llm_client.call(
            prompt="Extract states...",
            extraction_type='states',
            section_type='facts'
        )

        data = json.loads(response.content)
        assert 'states' in data
        assert len(data['states']) > 0

    def test_mock_client_logs_calls(self, mock_llm_client):
        """Verify mock client logs calls for debugging."""
        mock_llm_client.reset_call_log()

        mock_llm_client.call(
            prompt="Test prompt 1",
            extraction_type='roles',
            section_type='facts'
        )
        mock_llm_client.call(
            prompt="Test prompt 2",
            extraction_type='states',
            section_type='discussion'
        )

        assert mock_llm_client.call_count == 2
        calls = mock_llm_client.get_calls()
        assert calls[0]['extraction_type'] == 'roles'
        assert calls[1]['extraction_type'] == 'states'

    def test_mock_client_filters_calls_by_type(self, mock_llm_client):
        """Verify call log can be filtered by extraction type."""
        mock_llm_client.reset_call_log()

        mock_llm_client.call(prompt="p1", extraction_type='roles', section_type='facts')
        mock_llm_client.call(prompt="p2", extraction_type='states', section_type='facts')
        mock_llm_client.call(prompt="p3", extraction_type='roles', section_type='discussion')

        roles_calls = mock_llm_client.get_calls(extraction_type='roles')
        assert len(roles_calls) == 2


class TestMockClientFactory:
    """Tests for MockLLMClientFactory with custom overrides."""

    def test_create_with_overrides(self, mock_llm_client_factory):
        """Verify factory can create client with custom fixture overrides."""
        custom_roles = {
            'new_role_classes': [{'label': 'Custom Role', 'definition': 'Test'}],
            'role_individuals': []
        }

        client = mock_llm_client_factory.create_with_overrides({
            'roles_facts': custom_roles
        })

        response = client.call(prompt="test", extraction_type='roles', section_type='facts')
        data = json.loads(response.content)

        assert len(data['new_role_classes']) == 1
        assert data['new_role_classes'][0]['label'] == 'Custom Role'

    def test_create_empty_client(self, mock_llm_client_factory):
        """Verify factory can create client with no fixtures for error testing."""
        client = mock_llm_client_factory.create_empty()

        response = client.call(prompt="test", extraction_type='roles', section_type='facts')
        data = json.loads(response.content)

        # Should return error structure
        assert 'error' in data


class TestMockFixtureContent:
    """Tests to verify mock fixture content quality."""

    def test_roles_fixture_has_required_fields(self, mock_llm_client):
        """Verify roles fixture has all required fields for extraction."""
        response = mock_llm_client.call(
            prompt="test",
            extraction_type='roles',
            section_type='facts'
        )
        data = json.loads(response.content)

        # Check role individuals
        assert len(data['role_individuals']) > 0
        individual = data['role_individuals'][0]

        required_fields = ['name', 'role_classification', 'attributes', 'relationships']
        for field in required_fields:
            assert field in individual, f"Missing field: {field}"

    def test_actions_events_fixture_structure(self, mock_llm_client):
        """Verify actions_events fixture has correct structure."""
        response = mock_llm_client.call(
            prompt="test",
            extraction_type='actions_events',
            section_type='facts'
        )
        data = json.loads(response.content)

        assert 'actions' in data
        assert 'events' in data
        assert len(data['actions']) > 0
        assert len(data['events']) > 0

    def test_provisions_fixture_structure(self, mock_llm_client):
        """Verify provisions fixture has correct structure."""
        response = mock_llm_client.call(
            prompt="test",
            extraction_type='provisions',
            section_type='facts'
        )
        data = json.loads(response.content)

        assert 'provisions' in data
        assert len(data['provisions']) > 0

        provision = data['provisions'][0]
        assert 'code_section' in provision
        assert 'text' in provision
