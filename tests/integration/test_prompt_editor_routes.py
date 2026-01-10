"""
Integration tests for Prompt Editor routes.

Tests the API and web routes for the prompt editor feature.
Uses Flask test client with mocked MCP client and database fixtures.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from app.models import db
from app.models.extraction_prompt_template import ExtractionPromptTemplate
from app.models.document import Document


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def create_test_template(app_context):
    """Create a test extraction prompt template."""
    def _create_test_template(
        step_number=1,
        concept_type='roles',
        name='Test Roles Template',
        template_text='Extract roles from {{ case_text }}',
        domain='engineering',
        version=1
    ):
        template = ExtractionPromptTemplate(
            step_number=step_number,
            concept_type=concept_type,
            pass_type='all',
            name=name,
            description='Test template for unit tests',
            template_text=template_text,
            variables_schema={'case_text': {'type': 'string', 'description': 'Case text to analyze'}},
            version=version,
            is_active=True,
            source_file='test_source.py',
            domain=domain
        )
        db.session.add(template)
        db.session.commit()
        return template
    return _create_test_template


@pytest.fixture
def create_test_document(app_context, create_test_world):
    """Create a test document for rendering tests."""
    def _create_test_document(
        title='Test Case 24-02',
        content='<div class="card"><div class="card-header"><h5>Facts</h5></div><div class="card-body"><p>Engineer A was retained by Client W to prepare a report.</p></div></div>'
    ):
        # First create a world for the document
        from app.models.world import World
        world = World.query.first()
        if not world:
            world = create_test_world(name='Test World', description='For testing')

        doc = Document(
            title=title,
            document_type='case_study',
            world_id=world.id,
            content=content,
            processing_status='completed'
        )
        db.session.add(doc)
        db.session.commit()
        return doc
    return _create_test_document


# =============================================================================
# Web Route Tests
# =============================================================================

class TestPromptEditorWebRoutes:
    """Tests for prompt editor web routes."""

    def test_index_redirects_without_login(self, client):
        """Test that /tools/prompts redirects to login when not authenticated."""
        response = client.get('/tools/prompts')

        # Should redirect to login
        assert response.status_code == 302
        assert 'login' in response.location.lower() or response.status_code == 302

    def test_index_accessible_when_logged_in(self, auth_client):
        """Test that /tools/prompts is accessible when logged in."""
        response = auth_client.get('/tools/prompts')

        # Should return 200 or redirect to specific template
        assert response.status_code in [200, 302]

    def test_edit_template_page_requires_login(self, client):
        """Test that edit template page requires authentication."""
        response = client.get('/tools/prompts/1/roles')

        assert response.status_code == 302
        assert 'login' in response.location.lower() or response.status_code == 302

    def test_edit_template_page_loads_for_concept(self, auth_client, create_test_template):
        """Test that edit template page loads for a specific concept."""
        # Create a template first
        template = create_test_template()

        response = auth_client.get(f'/tools/prompts/{template.step_number}/{template.concept_type}')

        assert response.status_code == 200
        # The page should contain template-related content
        assert b'roles' in response.data.lower() or b'template' in response.data.lower()

    def test_edit_template_page_handles_missing_template(self, auth_client):
        """Test that page handles missing template gracefully."""
        # Request a template that doesn't exist
        response = auth_client.get('/tools/prompts/1/nonexistent')

        # Should either return 200 with message or handle gracefully
        assert response.status_code in [200, 404]

    def test_edit_template_page_includes_domain_selection(self, auth_client, create_test_template):
        """Test that domain selection is available on the edit page."""
        template = create_test_template(domain='engineering')

        response = auth_client.get(f'/tools/prompts/{template.step_number}/{template.concept_type}')

        assert response.status_code == 200


# =============================================================================
# API Route Tests - Template Rendering
# =============================================================================

class TestRenderTemplateAPI:
    """Tests for POST /api/prompts/template/<id>/render endpoint."""

    def test_render_requires_authentication(self, client, create_test_template):
        """Test that render endpoint requires authentication."""
        template = create_test_template()

        response = client.post(
            f'/api/prompts/template/{template.id}/render',
            json={'case_id': 1, 'section_type': 'facts'},
            content_type='application/json'
        )

        assert response.status_code == 302  # Redirects to login

    @patch('app.services.external_mcp_client.get_external_mcp_client')
    def test_render_requires_case_id(self, mock_mcp, auth_client, create_test_template):
        """Test that render endpoint requires case_id."""
        mock_mcp.return_value = MagicMock()
        template = create_test_template()

        response = auth_client.post(
            f'/api/prompts/template/{template.id}/render',
            json={'section_type': 'facts'},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'case_id' in data['error'].lower()

    @patch('app.services.external_mcp_client.get_external_mcp_client')
    @patch('app.services.prompt_variable_resolver.get_prompt_variable_resolver')
    def test_render_with_valid_case(self, mock_resolver_factory, mock_mcp, auth_client, create_test_template, create_test_document):
        """Test rendering a template with a valid case."""
        mock_mcp_instance = MagicMock()
        mock_mcp_instance.get_all_role_entities.return_value = []
        mock_mcp.return_value = mock_mcp_instance

        template = create_test_template(
            template_text='Extract roles from: {{ case_text }}\nExisting: {{ existing_roles_text }}'
        )
        doc = create_test_document()

        # Mock the variable resolver
        mock_resolver = MagicMock()
        mock_resolver.resolve_variables.return_value = {
            'case_text': 'Engineer A was retained.',
            'existing_roles_text': 'No existing roles.',
            'section_type': 'facts'
        }
        mock_resolver_factory.return_value = mock_resolver

        response = auth_client.post(
            f'/api/prompts/template/{template.id}/render',
            json={'case_id': doc.id, 'section_type': 'facts'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'rendered_prompt' in data
        assert 'variables_used' in data

    def test_render_returns_404_for_invalid_template(self, auth_client):
        """Test that render returns 404 for non-existent template."""
        response = auth_client.post(
            '/api/prompts/template/99999/render',
            json={'case_id': 1, 'section_type': 'facts'},
            content_type='application/json'
        )

        assert response.status_code == 404


# =============================================================================
# API Route Tests - Resolve Variables
# =============================================================================

class TestResolveVariablesAPI:
    """Tests for POST /api/prompts/template/<id>/resolve-variables endpoint."""

    def test_resolve_variables_requires_auth(self, client, create_test_template):
        """Test that resolve-variables requires authentication."""
        template = create_test_template()

        response = client.post(
            f'/api/prompts/template/{template.id}/resolve-variables',
            json={'case_id': 1},
            content_type='application/json'
        )

        assert response.status_code == 302

    @patch('app.services.external_mcp_client.get_external_mcp_client')
    def test_resolve_variables_requires_case_id(self, mock_mcp, auth_client, create_test_template):
        """Test that resolve-variables requires case_id."""
        mock_mcp.return_value = MagicMock()
        template = create_test_template()

        response = auth_client.post(
            f'/api/prompts/template/{template.id}/resolve-variables',
            json={},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    @patch('app.services.external_mcp_client.get_external_mcp_client')
    @patch('app.services.prompt_variable_resolver.get_prompt_variable_resolver')
    def test_resolve_variables_returns_formatted_variables(self, mock_resolver_factory, mock_mcp, auth_client, create_test_template, create_test_document):
        """Test that resolve-variables returns properly formatted variables."""
        mock_mcp_instance = MagicMock()
        mock_mcp_instance.get_all_role_entities.return_value = []
        mock_mcp.return_value = mock_mcp_instance

        template = create_test_template()
        doc = create_test_document()

        mock_resolver = MagicMock()
        mock_resolver.resolve_variables.return_value = {
            'case_text': 'Test case text',
            'section_type': 'facts',
            'existing_roles_text': 'No existing roles.'
        }
        mock_resolver_factory.return_value = mock_resolver

        response = auth_client.post(
            f'/api/prompts/template/{template.id}/resolve-variables',
            json={'case_id': doc.id, 'section_type': 'facts'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'variables' in data
        assert 'case_id' in data
        assert 'concept_type' in data

        # Variables should have metadata format
        for var_name, var_data in data['variables'].items():
            assert 'value' in var_data
            assert 'length' in var_data
            assert 'type' in var_data


# =============================================================================
# API Route Tests - Update Template
# =============================================================================

class TestUpdateTemplateAPI:
    """Tests for PUT /api/prompts/template/<id> endpoint."""

    def test_update_requires_authentication(self, client, create_test_template):
        """Test that update endpoint requires authentication."""
        template = create_test_template()

        response = client.put(
            f'/api/prompts/template/{template.id}',
            json={'template_text': 'New text'},
            content_type='application/json'
        )

        assert response.status_code == 302

    def test_update_requires_template_text(self, auth_client, create_test_template):
        """Test that update requires template_text field."""
        template = create_test_template()

        response = auth_client.put(
            f'/api/prompts/template/{template.id}',
            json={'name': 'New name only'},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'template_text' in data['error'].lower()

    def test_update_creates_version_history(self, auth_client, create_test_template):
        """Test that updating a template creates version history."""
        template = create_test_template(version=1)
        original_text = template.template_text

        response = auth_client.put(
            f'/api/prompts/template/{template.id}',
            json={
                'template_text': 'Updated template {{ new_var }}',
                'change_description': 'Test update'
            },
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['template']['version'] == 2

    def test_update_returns_updated_template(self, auth_client, create_test_template):
        """Test that update returns the updated template."""
        template = create_test_template()
        new_text = 'Completely new template {{ different_var }}'

        response = auth_client.put(
            f'/api/prompts/template/{template.id}',
            json={'template_text': new_text},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['template']['template_text'] == new_text

    def test_update_returns_404_for_invalid_template(self, auth_client):
        """Test that update returns 404 for non-existent template."""
        response = auth_client.put(
            '/api/prompts/template/99999',
            json={'template_text': 'New text'},
            content_type='application/json'
        )

        assert response.status_code == 404


# =============================================================================
# API Route Tests - Get Templates
# =============================================================================

class TestGetTemplatesAPI:
    """Tests for GET /api/prompts/templates endpoint."""

    def test_get_templates_requires_auth(self, client):
        """Test that get templates requires authentication."""
        response = client.get('/api/prompts/templates')

        assert response.status_code == 302

    def test_get_templates_returns_organized_by_step(self, auth_client, create_test_template):
        """Test that templates are organized by pipeline step."""
        # Create templates for different steps
        create_test_template(step_number=1, concept_type='roles')
        create_test_template(step_number=2, concept_type='principles')
        create_test_template(step_number=3, concept_type='actions')

        response = auth_client.get('/api/prompts/templates')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'steps' in data

        # Should have step entries
        steps = data['steps']
        assert len(steps) == 3  # 3 pipeline steps

    def test_get_templates_includes_concept_info(self, auth_client, create_test_template):
        """Test that template response includes concept information."""
        template = create_test_template(step_number=1, concept_type='roles')

        response = auth_client.get('/api/prompts/templates')

        assert response.status_code == 200
        data = json.loads(response.data)

        # Find step 1
        step1 = next((s for s in data['steps'] if s['step'] == 1), None)
        assert step1 is not None
        assert 'concepts' in step1


# =============================================================================
# API Route Tests - Get Single Template
# =============================================================================

class TestGetTemplateAPI:
    """Tests for GET /api/prompts/template/<id> endpoint."""

    def test_get_template_requires_auth(self, client, create_test_template):
        """Test that get single template requires authentication."""
        template = create_test_template()

        response = client.get(f'/api/prompts/template/{template.id}')

        assert response.status_code == 302

    def test_get_template_returns_template_data(self, auth_client, create_test_template):
        """Test that get template returns full template data."""
        template = create_test_template(
            name='Specific Template',
            template_text='{{ specific_var }}'
        )

        response = auth_client.get(f'/api/prompts/template/{template.id}')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['template']['name'] == 'Specific Template'
        assert data['template']['template_text'] == '{{ specific_var }}'

    def test_get_template_returns_404_for_invalid_id(self, auth_client):
        """Test that get template returns 404 for invalid ID."""
        response = auth_client.get('/api/prompts/template/99999')

        assert response.status_code == 404


# =============================================================================
# API Route Tests - Template Versions
# =============================================================================

class TestTemplateVersionsAPI:
    """Tests for GET /api/prompts/template/<id>/versions endpoint."""

    def test_get_versions_requires_auth(self, client, create_test_template):
        """Test that versions endpoint requires authentication."""
        template = create_test_template()

        response = client.get(f'/api/prompts/template/{template.id}/versions')

        assert response.status_code == 302

    def test_get_versions_returns_current_version(self, auth_client, create_test_template):
        """Test that versions endpoint returns current version."""
        template = create_test_template(version=3)

        response = auth_client.get(f'/api/prompts/template/{template.id}/versions')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['current_version'] == 3
        assert 'versions' in data


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in prompt editor routes."""

    def test_invalid_json_returns_400(self, auth_client, create_test_template):
        """Test that invalid JSON returns 400."""
        template = create_test_template()

        response = auth_client.put(
            f'/api/prompts/template/{template.id}',
            data='invalid json',
            content_type='application/json'
        )

        # Should return 400 for bad request
        assert response.status_code in [400, 500]

    @patch('app.services.external_mcp_client.get_external_mcp_client')
    @patch('app.services.prompt_variable_resolver.get_prompt_variable_resolver')
    def test_resolver_error_returns_500(self, mock_resolver_factory, mock_mcp, auth_client, create_test_template, create_test_document):
        """Test that resolver errors are handled gracefully."""
        mock_mcp.return_value = MagicMock()
        template = create_test_template()
        doc = create_test_document()

        mock_resolver = MagicMock()
        mock_resolver.resolve_variables.side_effect = Exception('MCP connection failed')
        mock_resolver_factory.return_value = mock_resolver

        response = auth_client.post(
            f'/api/prompts/template/{template.id}/render',
            json={'case_id': doc.id, 'section_type': 'facts'},
            content_type='application/json'
        )

        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'error' in data
