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

        # For non-facts sections, append classes extracted from prior sections
        if section_type != 'facts':
            prior_text = self._format_prior_section_classes(
                case_id, section_type, concept_type
            )
            if prior_text:
                existing_text += prior_text

        # Set concept-specific variable names
        var_name = f'existing_{concept_type}_text'
        variables[var_name] = existing_text
        variables['existing_entities_text'] = existing_text  # Generic fallback

        # Also provide the raw list
        variables[f'existing_{concept_type}'] = existing_entities
        variables['existing_entities'] = existing_entities

        # Cross-concept context (e.g., roles for principles extraction)
        from app.services.extraction.unified_dual_extractor import (
            format_cross_concept_context,
        )
        variables['cross_concept_context'] = format_cross_concept_context(
            concept_type, case_id
        )

        logger.info(f"Resolved {len(variables)} variables for case {case_id}, "
                   f"section {section_type}, concept {concept_type}")

        return variables

    def _format_prior_section_classes(
        self, case_id: int, current_section: str, concept_type: str,
    ) -> str:
        """
        Format classes extracted from earlier sections for this case.

        Mirrors UnifiedDualExtractor._format_prior_section_classes() so the
        prompt editor preview matches what the actual extraction sends.
        """
        try:
            from app.models.temporary_rdf_storage import TemporaryRDFStorage
            from app.models.extraction_prompt import ExtractionPrompt

            section_order = ['facts', 'discussion', 'questions', 'conclusions']
            current_idx = (
                section_order.index(current_section)
                if current_section in section_order else 0
            )
            prior_sections = section_order[:current_idx]
            if not prior_sections:
                return ''

            prior_sessions = [
                p.extraction_session_id
                for p in ExtractionPrompt.query.filter_by(
                    case_id=case_id,
                    concept_type=concept_type,
                    is_active=True,
                ).all()
                if p.extraction_session_id and p.section_type in prior_sections
            ]
            if not prior_sessions:
                return ''

            prior_classes = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_type == concept_type,
                TemporaryRDFStorage.storage_type == 'class',
                TemporaryRDFStorage.extraction_session_id.in_(prior_sessions),
            ).all()
            if not prior_classes:
                return ''

            lines = [
                f'\n\n--- {concept_type.upper()} CLASSES ALREADY EXTRACTED '
                f'FROM PRIOR SECTIONS ---',
                'These classes were found in earlier sections of this case.',
                'Reference them via match_decision if the same concept '
                'appears here.',
                'Do NOT re-create them as new classes.\n',
            ]
            for cls in prior_classes:
                defn = cls.entity_definition or ''
                lines.append(f'- {cls.entity_label}: {defn}')

            logger.info(
                f"Added {len(prior_classes)} prior-section {concept_type} "
                f"classes to prompt editor preview for case {case_id}"
            )
            return '\n'.join(lines)

        except Exception as e:
            logger.warning(f"Could not load prior-section classes: {e}")
            return ''

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
        """Delegate to module-level function."""
        return format_existing_entities(entities, concept_type)


def format_existing_entities(entities: List[Dict[str, Any]],
                             concept_type: str) -> str:
    """
    Format existing ontology entities for inclusion in a prompt.

    Shared by UnifiedDualExtractor and PromptVariableResolver to ensure
    the extraction pipeline and prompt editor produce identical prompts.

    Entities are separated into tiers by source ontology:
      Tier 1 - Canonical (proethica-core, proethica-intermediate): hand-curated
      Tier 2 - Previously extracted (proethica-intermediate-extended): from prior cases
      Tier 4 - External standards (engineering-ethics): NSPE, ISO, ANSI references

    Args:
        entities: List of entity dictionaries from MCP
        concept_type: Concept type (roles, states, etc.)

    Returns:
        Formatted string for prompt inclusion
    """
    if not entities:
        return f"No existing {concept_type} classes found in ontology."

    # Classify entities by source ontology tier.
    # MCP entities use 'source' for ontology name, and nested
    # metadata.ontology as fallback.
    canonical = []     # proethica-core, proethica-intermediate
    extracted = []     # proethica-intermediate-extended
    external = []      # engineering-ethics
    for entity in entities:
        ont_name = (
            entity.get('ontology_name')
            or entity.get('source')
            or (entity.get('metadata', {}) or {}).get('ontology', '')
        )
        if ont_name in ('proethica-core', 'proethica-intermediate'):
            canonical.append(entity)
        elif ont_name == 'proethica-intermediate-extended':
            extracted.append(entity)
        elif ont_name == 'engineering-ethics':
            external.append(entity)
        else:
            canonical.append(entity)  # default to canonical

    def _format_entity_line(entity):
        label = entity.get('label', entity.get('name', 'Unknown'))
        definition = (
            entity.get('definition')
            or entity.get('description')
            or entity.get('comment', '')
        )
        if definition:
            return f"- {label}: {definition}"
        return f"- {label}"

    lines = []

    if canonical:
        lines.append(f"=== CANONICAL ONTOLOGY CLASSES ({concept_type}) ===")
        lines.append("Hand-curated classes from the formal ontology. Match to these with high confidence.")
        for e in canonical:
            lines.append(_format_entity_line(e))

    if extracted:
        if lines:
            lines.append('')
        lines.append(f"=== PREVIOUSLY EXTRACTED CLASSES (from other cases) ===")
        lines.append("Auto-extracted from prior case analyses and approved. Match if the same concept appears.")
        for e in extracted:
            lines.append(_format_entity_line(e))

    if external:
        if lines:
            lines.append('')
        lines.append(f"=== EXTERNAL REFERENCE STANDARDS ===")
        lines.append("NSPE, ISO, ANSI, and other professional standards. Reference context only.")
        for e in external:
            lines.append(_format_entity_line(e))

    return '\n'.join(lines)


def get_prompt_variable_resolver() -> PromptVariableResolver:
    """Get a PromptVariableResolver instance."""
    return PromptVariableResolver()
