"""
Unit tests for the Prompt Editor feature.

Tests the ExtractionPromptTemplate model methods and PromptVariableResolver service.
Uses mocks to avoid database and MCP client dependencies.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime


# =============================================================================
# ExtractionPromptTemplate Model Tests
# =============================================================================

class TestExtractionPromptTemplateGetTemplateVariables:
    """Tests for ExtractionPromptTemplate.get_template_variables() method."""

    def test_extracts_single_variable(self):
        """Test extraction of a single variable from template."""
        from app.models.extraction_prompt_template import ExtractionPromptTemplate

        template = ExtractionPromptTemplate(
            step_number=1,
            concept_type='roles',
            name='Test Template',
            template_text='Extract roles from {{ case_text }}'
        )

        variables = template.get_template_variables()

        assert 'case_text' in variables
        assert len(variables) == 1

    def test_extracts_multiple_variables(self):
        """Test extraction of multiple variables from template."""
        from app.models.extraction_prompt_template import ExtractionPromptTemplate

        template = ExtractionPromptTemplate(
            step_number=1,
            concept_type='roles',
            name='Test Template',
            template_text='''
            Case Text: {{ case_text }}
            Section: {{ section_type }}
            Existing: {{ existing_roles_text }}
            '''
        )

        variables = template.get_template_variables()

        assert 'case_text' in variables
        assert 'section_type' in variables
        assert 'existing_roles_text' in variables
        assert len(variables) == 3

    def test_handles_whitespace_in_variables(self):
        """Test that whitespace inside braces is handled correctly."""
        from app.models.extraction_prompt_template import ExtractionPromptTemplate

        template = ExtractionPromptTemplate(
            step_number=1,
            concept_type='roles',
            name='Test Template',
            template_text='{{ case_text }} and {{section_type}} and {{  entity  }}'
        )

        variables = template.get_template_variables()

        assert 'case_text' in variables
        assert 'section_type' in variables
        assert 'entity' in variables
        assert len(variables) == 3

    def test_deduplicates_repeated_variables(self):
        """Test that repeated variable names are deduplicated."""
        from app.models.extraction_prompt_template import ExtractionPromptTemplate

        template = ExtractionPromptTemplate(
            step_number=1,
            concept_type='roles',
            name='Test Template',
            template_text='{{ case_text }} ... again {{ case_text }} ... {{ case_text }}'
        )

        variables = template.get_template_variables()

        assert len(variables) == 1
        assert 'case_text' in variables

    def test_returns_empty_list_for_no_variables(self):
        """Test that empty list is returned when no variables present."""
        from app.models.extraction_prompt_template import ExtractionPromptTemplate

        template = ExtractionPromptTemplate(
            step_number=1,
            concept_type='roles',
            name='Test Template',
            template_text='This template has no variables'
        )

        variables = template.get_template_variables()

        assert variables == []


class TestExtractionPromptTemplateToLangchainPrompt:
    """Tests for ExtractionPromptTemplate.to_langchain_prompt() method."""

    def test_converts_jinja2_to_langchain_syntax(self):
        """Test that Jinja2 {{ var }} syntax converts to LangChain { var } syntax."""
        from app.models.extraction_prompt_template import ExtractionPromptTemplate

        template = ExtractionPromptTemplate(
            id=1,
            step_number=1,
            concept_type='roles',
            version=2,
            name='Test Template',
            template_text='Extract from {{ case_text }} with {{ section_type }}'
        )

        langchain_prompt = template.to_langchain_prompt()

        # Check the template text was converted
        assert '{case_text}' in langchain_prompt.template
        assert '{section_type}' in langchain_prompt.template
        assert '{{' not in langchain_prompt.template
        assert '}}' not in langchain_prompt.template

    def test_sets_input_variables(self):
        """Test that input_variables are set correctly."""
        from app.models.extraction_prompt_template import ExtractionPromptTemplate

        template = ExtractionPromptTemplate(
            id=1,
            step_number=1,
            concept_type='roles',
            version=1,
            name='Test Template',
            template_text='{{ var_a }} and {{ var_b }}'
        )

        langchain_prompt = template.to_langchain_prompt()

        assert 'var_a' in langchain_prompt.input_variables
        assert 'var_b' in langchain_prompt.input_variables

    def test_includes_metadata(self):
        """Test that ProEthica metadata is included in the prompt."""
        from app.models.extraction_prompt_template import ExtractionPromptTemplate

        template = ExtractionPromptTemplate(
            id=42,
            step_number=2,
            concept_type='principles',
            version=5,
            name='Test Template',
            template_text='{{ text }}'
        )

        langchain_prompt = template.to_langchain_prompt()

        assert langchain_prompt.metadata['proethica_template_id'] == 42
        assert langchain_prompt.metadata['version'] == 5
        assert langchain_prompt.metadata['concept_type'] == 'principles'
        assert langchain_prompt.metadata['step_number'] == 2


class TestExtractionPromptTemplateToLangchainChatPrompt:
    """Tests for ExtractionPromptTemplate.to_langchain_chat_prompt() method."""

    def test_creates_chat_prompt_template(self):
        """Test that a ChatPromptTemplate is created correctly."""
        from app.models.extraction_prompt_template import ExtractionPromptTemplate
        from langchain_core.prompts import ChatPromptTemplate

        template = ExtractionPromptTemplate(
            id=1,
            step_number=1,
            concept_type='roles',
            version=1,
            name='Test Template',
            template_text='Extract roles from {{ case_text }}'
        )

        chat_prompt = template.to_langchain_chat_prompt()

        assert isinstance(chat_prompt, ChatPromptTemplate)

    def test_chat_prompt_uses_system_message(self):
        """Test that the prompt is wrapped in a system message."""
        from app.models.extraction_prompt_template import ExtractionPromptTemplate

        template = ExtractionPromptTemplate(
            id=1,
            step_number=1,
            concept_type='roles',
            version=1,
            name='Test Template',
            template_text='Extract roles from {{ case_text }}'
        )

        chat_prompt = template.to_langchain_chat_prompt()

        # Check that the first message is a system message
        messages = chat_prompt.messages
        assert len(messages) == 1
        # The message_type should be 'system' in the template
        assert messages[0].prompt.template == 'Extract roles from {case_text}'

    def test_chat_prompt_converts_jinja2_syntax(self):
        """Test that Jinja2 syntax is converted in chat prompt."""
        from app.models.extraction_prompt_template import ExtractionPromptTemplate

        template = ExtractionPromptTemplate(
            id=1,
            step_number=1,
            concept_type='roles',
            version=1,
            name='Test Template',
            template_text='{{ var1 }} and {{ var2 }}'
        )

        chat_prompt = template.to_langchain_chat_prompt()

        # Verify the system message contains LangChain syntax
        system_template = chat_prompt.messages[0].prompt.template
        assert '{var1}' in system_template
        assert '{var2}' in system_template
        assert '{{' not in system_template


# =============================================================================
# PromptVariableResolver Service Tests
# =============================================================================

class TestPromptVariableResolverResolveVariables:
    """Tests for PromptVariableResolver.resolve_variables() method."""

    @patch('app.services.external_mcp_client.get_external_mcp_client')
    def test_resolve_variables_returns_case_text(self, mock_get_mcp):
        """Test that resolve_variables returns case_text variable."""
        from app.services.prompt_variable_resolver import PromptVariableResolver

        # Mock MCP client
        mock_mcp = MagicMock()
        mock_mcp.get_all_role_entities.return_value = []
        mock_get_mcp.return_value = mock_mcp

        resolver = PromptVariableResolver()

        # Mock the get_case_section_text method
        with patch.object(resolver, 'get_case_section_text', return_value='Test case text'):
            with patch.object(resolver, 'get_existing_entities', return_value=[]):
                variables = resolver.resolve_variables(
                    case_id=7,
                    section_type='facts',
                    concept_type='roles'
                )

        assert 'case_text' in variables
        assert variables['case_text'] == 'Test case text'
        assert 'section_type' in variables
        assert variables['section_type'] == 'facts'

    @patch('app.services.external_mcp_client.get_external_mcp_client')
    def test_resolve_variables_includes_existing_entities(self, mock_get_mcp):
        """Test that existing entities are included in resolved variables."""
        from app.services.prompt_variable_resolver import PromptVariableResolver

        # Mock MCP client
        mock_mcp = MagicMock()
        mock_mcp.get_all_role_entities.return_value = [
            {'label': 'Engineer A', 'definition': 'Licensed engineer'},
            {'label': 'Client W', 'definition': 'Client'}
        ]
        mock_get_mcp.return_value = mock_mcp

        resolver = PromptVariableResolver()

        with patch.object(resolver, 'get_case_section_text', return_value='Case text'):
            variables = resolver.resolve_variables(
                case_id=7,
                section_type='facts',
                concept_type='roles'
            )

        # Check concept-specific variable
        assert 'existing_roles_text' in variables
        assert 'existing_roles' in variables
        # Check generic fallback variables
        assert 'existing_entities_text' in variables
        assert 'existing_entities' in variables

    @patch('app.services.external_mcp_client.get_external_mcp_client')
    def test_resolve_variables_handles_different_concept_types(self, mock_get_mcp):
        """Test that different concept types create correct variable names."""
        from app.services.prompt_variable_resolver import PromptVariableResolver

        mock_mcp = MagicMock()
        mock_mcp.get_entities_by_category.return_value = {
            'success': True,
            'result': {'entities': [{'label': 'Test Principle'}]}
        }
        mock_get_mcp.return_value = mock_mcp

        resolver = PromptVariableResolver()

        with patch.object(resolver, 'get_case_section_text', return_value='Case text'):
            variables = resolver.resolve_variables(
                case_id=7,
                section_type='discussion',
                concept_type='principles'
            )

        assert 'existing_principles_text' in variables
        assert 'existing_principles' in variables


class TestPromptVariableResolverGetCaseText:
    """Tests for PromptVariableResolver._extract_section_from_html() method."""

    @patch('app.services.external_mcp_client.get_external_mcp_client')
    def test_extract_facts_section(self, mock_get_mcp):
        """Test extraction of facts section from HTML."""
        from app.services.prompt_variable_resolver import PromptVariableResolver

        mock_get_mcp.return_value = MagicMock()
        resolver = PromptVariableResolver()

        html_content = '''
        <div class="card">
            <div class="card-header"><h5>Facts</h5></div>
            <div class="card-body">
                <p>Engineer A was retained by Client W.</p>
                <p>Work required analysis of groundwater data.</p>
            </div>
        </div>
        '''

        result = resolver._extract_section_from_html(html_content, 'facts')

        assert 'Engineer A was retained by Client W' in result
        assert 'groundwater data' in result

    @patch('app.services.external_mcp_client.get_external_mcp_client')
    def test_extract_discussion_section(self, mock_get_mcp):
        """Test extraction of discussion section from HTML."""
        from app.services.prompt_variable_resolver import PromptVariableResolver

        mock_get_mcp.return_value = MagicMock()
        resolver = PromptVariableResolver()

        html_content = '''
        <div class="card">
            <div class="card-header"><h5>Discussion</h5></div>
            <div class="card-body">
                <p>The Board analyzed the ethical implications.</p>
            </div>
        </div>
        '''

        result = resolver._extract_section_from_html(html_content, 'discussion')

        assert 'Board analyzed' in result

    @patch('app.services.external_mcp_client.get_external_mcp_client')
    def test_handles_missing_section(self, mock_get_mcp):
        """Test handling of missing section in HTML."""
        from app.services.prompt_variable_resolver import PromptVariableResolver

        mock_get_mcp.return_value = MagicMock()
        resolver = PromptVariableResolver()

        html_content = '''
        <div class="card">
            <div class="card-header"><h5>Other Section</h5></div>
            <div class="card-body"><p>Some content</p></div>
        </div>
        '''

        result = resolver._extract_section_from_html(html_content, 'facts')

        assert 'not found' in result.lower() or 'error' in result.lower() or result.startswith('[')


class TestPromptVariableResolverFormatExistingEntities:
    """Tests for PromptVariableResolver.format_existing_entities() method."""

    @patch('app.services.external_mcp_client.get_external_mcp_client')
    def test_formats_entities_with_definitions(self, mock_get_mcp):
        """Test formatting of entities that have definitions."""
        from app.services.prompt_variable_resolver import PromptVariableResolver

        mock_get_mcp.return_value = MagicMock()
        resolver = PromptVariableResolver()

        entities = [
            {'label': 'Engineer A', 'definition': 'Licensed professional engineer'},
            {'label': 'Client W', 'definition': 'Corporate client'}
        ]

        result = resolver.format_existing_entities(entities, 'roles')

        assert 'Engineer A: Licensed professional engineer' in result
        assert 'Client W: Corporate client' in result
        assert result.startswith('- ')

    @patch('app.services.external_mcp_client.get_external_mcp_client')
    def test_formats_entities_without_definitions(self, mock_get_mcp):
        """Test formatting of entities without definitions."""
        from app.services.prompt_variable_resolver import PromptVariableResolver

        mock_get_mcp.return_value = MagicMock()
        resolver = PromptVariableResolver()

        entities = [
            {'label': 'Public'},
            {'name': 'Regulator'}  # Uses 'name' fallback
        ]

        result = resolver.format_existing_entities(entities, 'roles')

        assert '- Public' in result
        assert '- Regulator' in result

    @patch('app.services.external_mcp_client.get_external_mcp_client')
    def test_returns_no_entities_message_for_empty_list(self, mock_get_mcp):
        """Test that empty entity list returns appropriate message."""
        from app.services.prompt_variable_resolver import PromptVariableResolver

        mock_get_mcp.return_value = MagicMock()
        resolver = PromptVariableResolver()

        result = resolver.format_existing_entities([], 'principles')

        assert 'no existing' in result.lower()
        assert 'principles' in result.lower()

    @patch('app.services.external_mcp_client.get_external_mcp_client')
    def test_truncates_long_definitions(self, mock_get_mcp):
        """Test that long definitions are truncated."""
        from app.services.prompt_variable_resolver import PromptVariableResolver

        mock_get_mcp.return_value = MagicMock()
        resolver = PromptVariableResolver()

        long_definition = 'x' * 200  # Longer than 150 char limit
        entities = [{'label': 'Test Entity', 'definition': long_definition}]

        result = resolver.format_existing_entities(entities, 'roles')

        assert '...' in result
        assert len(result) < len(long_definition) + 50  # Some overhead for label

    @patch('app.services.external_mcp_client.get_external_mcp_client')
    def test_limits_to_20_entities(self, mock_get_mcp):
        """Test that entity list is limited to 20 entries."""
        from app.services.prompt_variable_resolver import PromptVariableResolver

        mock_get_mcp.return_value = MagicMock()
        resolver = PromptVariableResolver()

        entities = [{'label': f'Entity {i}'} for i in range(30)]

        result = resolver.format_existing_entities(entities, 'roles')

        # Should have 20 entries plus "... and X more"
        assert '... and 10 more' in result
        lines = result.strip().split('\n')
        assert len(lines) == 21  # 20 entities + 1 "more" line


# =============================================================================
# ExtractionPromptTemplate Render Tests
# =============================================================================

class TestExtractionPromptTemplateRender:
    """Tests for ExtractionPromptTemplate.render() method."""

    def test_renders_template_with_variables(self):
        """Test that template renders correctly with provided variables."""
        from app.models.extraction_prompt_template import ExtractionPromptTemplate

        template = ExtractionPromptTemplate(
            step_number=1,
            concept_type='roles',
            name='Test Template',
            template_text='Extract roles from: {{ case_text }}\nSection: {{ section_type }}'
        )

        result = template.render(
            case_text='Engineer A worked with Client W',
            section_type='facts'
        )

        assert 'Engineer A worked with Client W' in result
        assert 'Section: facts' in result

    def test_handles_missing_variables_gracefully(self):
        """Test that missing variables don't crash the render."""
        from app.models.extraction_prompt_template import ExtractionPromptTemplate

        template = ExtractionPromptTemplate(
            step_number=1,
            concept_type='roles',
            name='Test Template',
            template_text='{{ undefined_var }}'
        )

        # Jinja2 renders undefined variables as empty string by default
        result = template.render()

        # Should not raise an exception and should return something
        assert isinstance(result, str)


# =============================================================================
# ExtractionPromptTemplate to_dict Tests
# =============================================================================

class TestExtractionPromptTemplateToDct:
    """Tests for ExtractionPromptTemplate.to_dict() method."""

    def test_includes_all_fields(self):
        """Test that to_dict includes all expected fields."""
        from app.models.extraction_prompt_template import ExtractionPromptTemplate

        template = ExtractionPromptTemplate(
            id=1,
            step_number=2,
            concept_type='principles',
            pass_type='facts',
            name='Test Template',
            description='Test description',
            template_text='{{ case_text }}',
            variables_schema={'case_text': {'type': 'string'}},
            version=3,
            is_active=True,
            source_file='test.py',
            extractor_file='extractor.py',
            prompt_method='build_prompt',
            variable_builders={'case_text': 'get_case_text'},
            output_schema={'role': 'string'},
            domain='engineering'
        )
        template.created_at = datetime(2026, 1, 10)
        template.updated_at = datetime(2026, 1, 10)

        result = template.to_dict()

        assert result['id'] == 1
        assert result['step_number'] == 2
        assert result['concept_type'] == 'principles'
        assert result['pass_type'] == 'facts'
        assert result['name'] == 'Test Template'
        assert result['description'] == 'Test description'
        assert result['template_text'] == '{{ case_text }}'
        assert result['variables_schema'] == {'case_text': {'type': 'string'}}
        assert result['version'] == 3
        assert result['is_active'] is True
        assert result['source_file'] == 'test.py'
        assert result['extractor_file'] == 'extractor.py'
        assert result['prompt_method'] == 'build_prompt'
        assert result['variable_builders'] == {'case_text': 'get_case_text'}
        assert result['output_schema'] == {'role': 'string'}
        assert result['domain'] == 'engineering'
