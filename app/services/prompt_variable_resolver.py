"""
Prompt Variable Resolver Service

Resolves template variables for the prompt editor's preview and test functionality.
Fetches case text, queries MCP for existing entities, and formats variables.
"""

import re
import logging
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class PromptVariableResolver:
    """Resolves template variables from case context and MCP entities."""

    # Maps concept types to their MCP entity category
    CONCEPT_TO_MCP_CATEGORY = {
        'roles': 'Role',
        'states': 'State',
        'resources': 'Resource',
        'principles': 'Principle',
        'obligations': 'Obligation',
        'constraints': 'Constraint',
        'capabilities': 'Capability',
        'actions': 'Action',
        'events': 'Event'
    }

    def __init__(self):
        """Initialize the resolver with MCP client."""
        from app.services.external_mcp_client import get_external_mcp_client
        self.mcp_client = get_external_mcp_client()

    def resolve_variables(self, case_id: int, section_type: str,
                          concept_type: str) -> Dict[str, Any]:
        """
        Resolve all template variables for a given case and concept.

        Args:
            case_id: ID of the case document
            section_type: 'facts' or 'discussion'
            concept_type: Concept type (roles, principles, etc.)

        Returns:
            Dictionary of variable names to values
        """
        variables = {}

        # Get case text
        case_text = self.get_case_section_text(case_id, section_type)
        variables['case_text'] = case_text
        variables['section_type'] = section_type

        # Get existing entities from MCP
        existing_entities = self.get_existing_entities(concept_type)
        existing_text = self.format_existing_entities(existing_entities, concept_type)

        # Set concept-specific variable names
        var_name = f'existing_{concept_type}_text'
        variables[var_name] = existing_text
        variables['existing_entities_text'] = existing_text  # Generic fallback

        # Also provide the raw list
        variables[f'existing_{concept_type}'] = existing_entities
        variables['existing_entities'] = existing_entities

        logger.info(f"Resolved {len(variables)} variables for case {case_id}, "
                   f"section {section_type}, concept {concept_type}")

        return variables

    def get_case_section_text(self, case_id: int, section_type: str) -> str:
        """
        Extract section text from case document.

        Args:
            case_id: Document ID
            section_type: 'facts' or 'discussion'

        Returns:
            Plain text content of the section
        """
        from app.models.document import Document

        document = Document.query.get(case_id)
        if not document:
            logger.warning(f"Document {case_id} not found")
            return f"[Document {case_id} not found]"

        content = document.get_content()
        if not content:
            logger.warning(f"Document {case_id} has no content")
            return "[No content available]"

        # Parse HTML to extract section
        return self._extract_section_from_html(content, section_type)

    def _extract_section_from_html(self, html_content: str, section_type: str) -> str:
        """
        Extract a specific section from HTML case content.

        The HTML structure is:
        <div class="card">
            <div class="card-header"><h5>Facts</h5></div>
            <div class="card-body"><p>...</p></div>
        </div>

        Args:
            html_content: Full HTML content
            section_type: 'facts' or 'discussion'

        Returns:
            Plain text of the section
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Find the section header
            section_title = section_type.title()  # 'facts' -> 'Facts'

            # Look for h5 tag with the section name
            for h5 in soup.find_all('h5'):
                if h5.get_text(strip=True).lower() == section_type.lower():
                    # Find the parent card
                    card = h5.find_parent('div', class_='card')
                    if card:
                        # Find the card-body
                        body = card.find('div', class_='card-body')
                        if body:
                            # Get text content, preserving paragraph breaks
                            text = body.get_text(separator='\n', strip=True)
                            return text

            # Fallback: try regex for simple patterns
            pattern = rf'{section_title}[:\s]*(.+?)(?=(?:Discussion|Conclusion|References|$))'
            match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
            if match:
                # Clean HTML tags from the match
                text = re.sub(r'<[^>]+>', ' ', match.group(1))
                text = re.sub(r'\s+', ' ', text).strip()
                return text

            logger.warning(f"Section '{section_type}' not found in document")
            return f"[Section '{section_type}' not found]"

        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return f"[Error extracting section: {e}]"

    def get_existing_entities(self, concept_type: str) -> List[Dict[str, Any]]:
        """
        Get existing entities from MCP for the given concept type.

        Args:
            concept_type: Concept type (roles, principles, etc.)

        Returns:
            List of entity dictionaries
        """
        try:
            category = self.CONCEPT_TO_MCP_CATEGORY.get(concept_type)
            if not category:
                logger.warning(f"No MCP category for concept type: {concept_type}")
                return []

            # Use the appropriate MCP method based on concept type
            # These methods already handle extracting entities from MCP response
            if concept_type == 'roles':
                entities = self.mcp_client.get_all_role_entities()
            elif concept_type == 'principles':
                entities = self._get_entities_from_mcp('Principle')
            elif concept_type == 'obligations':
                entities = self._get_entities_from_mcp('Obligation')
            elif concept_type == 'states':
                entities = self._get_entities_from_mcp('State')
            elif concept_type == 'resources':
                entities = self._get_entities_from_mcp('Resource')
            elif concept_type == 'constraints':
                entities = self._get_entities_from_mcp('Constraint')
            elif concept_type == 'capabilities':
                entities = self._get_entities_from_mcp('Capability')
            elif concept_type == 'actions':
                entities = self._get_entities_from_mcp('Action')
            elif concept_type == 'events':
                entities = self._get_entities_from_mcp('Event')
            else:
                entities = self._get_entities_from_mcp(category)

            logger.info(f"Retrieved {len(entities)} existing {concept_type} from MCP")
            return entities

        except Exception as e:
            logger.error(f"Error getting existing entities for {concept_type}: {e}")
            return []

    def _get_entities_from_mcp(self, category: str) -> List[Dict[str, Any]]:
        """Extract entities list from MCP response."""
        result = self.mcp_client.get_entities_by_category(category)
        if result.get('success') and result.get('result'):
            return result['result'].get('entities', [])
        return []

    def format_existing_entities(self, entities: List[Dict[str, Any]],
                                  concept_type: str) -> str:
        """
        Format existing entities for inclusion in a prompt.

        Args:
            entities: List of entity dictionaries
            concept_type: Concept type for formatting

        Returns:
            Formatted string for prompt inclusion
        """
        if not entities:
            return f"No existing {concept_type} classes found in ontology."

        lines = []
        for entity in entities[:20]:  # Limit to 20 to avoid prompt bloat
            label = entity.get('label', entity.get('name', 'Unknown'))
            definition = entity.get('definition', entity.get('description', ''))

            if definition:
                # Truncate long definitions
                if len(definition) > 150:
                    definition = definition[:147] + '...'
                lines.append(f"- {label}: {definition}")
            else:
                lines.append(f"- {label}")

        if len(entities) > 20:
            lines.append(f"... and {len(entities) - 20} more")

        return '\n'.join(lines)


def get_prompt_variable_resolver() -> PromptVariableResolver:
    """Get a PromptVariableResolver instance."""
    return PromptVariableResolver()
