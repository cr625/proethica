"""
Code Provision Entity Linking Service

Links NSPE code provisions to extracted case entities (Roles, States, Resources)
using LLM-based semantic matching.
"""

import logging
import json
import re
from typing import List, Dict

logger = logging.getLogger(__name__)


class CodeProvisionLinker:
    """Links code provisions to case entities using LLM analysis."""

    def __init__(self, llm_client=None):
        """
        Initialize the linker.

        Args:
            llm_client: Claude API client for LLM analysis
        """
        self.llm_client = llm_client
        self.last_linking_prompt = None
        self.last_linking_response = None

    def link_provisions_to_entities(
        self,
        provisions: List[Dict],
        roles: List[Dict],
        states: List[Dict],
        resources: List[Dict],
        case_text_summary: str = ""
    ) -> List[Dict]:
        """
        Link code provisions to applicable case entities.

        Args:
            provisions: List of parsed code provisions
            roles: List of role entities from case
            states: List of state entities from case
            resources: List of resource entities from case
            case_text_summary: Brief summary of the case for context

        Returns:
            List of provisions with 'applies_to' relationships added
        """
        if not self.llm_client:
            logger.warning("No LLM client provided, skipping entity linking")
            return provisions

        if not provisions:
            logger.info("No provisions to link")
            return []

        logger.info(f"Linking {len(provisions)} provisions to {len(roles)} roles, {len(states)} states, {len(resources)} resources")

        # Create LLM prompt
        prompt = self._create_linking_prompt(
            provisions, roles, states, resources, case_text_summary
        )
        self.last_linking_prompt = prompt

        try:
            # Call LLM
            response = self.llm_client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=8000,
                temperature=0.1,  # Low temperature for consistent analysis
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = response.content[0].text
            self.last_linking_response = response_text

            # Parse LLM response
            linked_provisions = self._parse_linking_response(response_text, provisions)

            logger.info(f"Successfully linked provisions to entities")
            return linked_provisions

        except Exception as e:
            logger.error(f"Error in LLM entity linking: {e}")
            # Return provisions without links on error
            return provisions

    def _create_linking_prompt(
        self,
        provisions: List[Dict],
        roles: List[Dict],
        states: List[Dict],
        resources: List[Dict],
        case_summary: str
    ) -> str:
        """Create prompt for LLM to link provisions to entities."""

        # Format entities for prompt
        roles_text = self._format_entities_for_prompt(roles, "Roles")
        states_text = self._format_entities_for_prompt(states, "States")
        resources_text = self._format_entities_for_prompt(resources, "Resources")

        # Format provisions
        provisions_text = ""
        for i, prov in enumerate(provisions, 1):
            provisions_text += f"{i}. **{prov['code_provision']}**: {prov['provision_text']}\n"

        prompt = f"""You are analyzing NSPE Code of Ethics provisions selected by the Board of Ethical Review for this engineering ethics case.

**Case Context:**
{case_summary if case_summary else "Engineering professional ethics case involving roles, ethical states, and resources."}

**NSPE Code Provisions (Board-Selected):**
{provisions_text}

**Extracted Case Entities:**

{roles_text}

{states_text}

{resources_text}

**Task:**
For each code provision, identify which specific case entities it applies to. A provision "applies to" an entity if:
- For Roles: The provision governs the professional conduct of that role
- For States: The provision addresses or relates to that ethical situation
- For Resources: The provision references or requires that resource/document

For each provision, provide:
1. Which entities it applies to (by label)
2. Brief reasoning explaining why the provision applies to each entity

**Output Format:**
Respond with a JSON array where each object represents one provision:

```json
[
  {{
    "code_provision": "I.1",
    "applies_to": [
      {{
        "entity_type": "role",
        "entity_label": "Engineer L",
        "reasoning": "This provision governs Engineer L's paramount duty to protect public water source safety"
      }},
      {{
        "entity_type": "state",
        "entity_label": "PublicSafetyAtRisk_WaterSource",
        "reasoning": "This provision directly addresses the state where public welfare is endangered"
      }}
    ]
  }},
  ...
]
```

**Important:**
- Only link provisions to entities where there's a clear, direct connection
- It's okay if a provision doesn't apply to any entities
- Use the exact entity labels from the lists above
- Provide specific, case-relevant reasoning (not generic descriptions)
"""

        return prompt

    def _format_entities_for_prompt(self, entities: List[Dict], entity_type: str) -> str:
        """Format entity list for inclusion in prompt."""
        if not entities:
            return f"**{entity_type}:** (none extracted)"

        formatted = f"**{entity_type}:**\n"
        for entity in entities:
            label = entity.get('label', entity.get('entity_label', 'Unknown'))
            definition = entity.get('definition', entity.get('entity_definition', ''))

            formatted += f"- {label}"
            if definition:
                # Truncate long definitions
                if len(definition) > 150:
                    definition = definition[:150] + "..."
                formatted += f": {definition}"
            formatted += "\n"

        return formatted

    def _parse_linking_response(
        self,
        response_text: str,
        original_provisions: List[Dict]
    ) -> List[Dict]:
        """Parse LLM response and add 'applies_to' to provisions."""

        # Extract JSON from response
        json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
        if not json_match:
            # Try without code blocks
            json_match = re.search(r'\[\s*\{.*?\}\s*\]', response_text, re.DOTALL)
            if not json_match:
                logger.warning("Could not find JSON in LLM response")
                return original_provisions

        try:
            json_text = json_match.group(1) if '```json' in response_text else json_match.group(0)
            linkings = json.loads(json_text)

            # Create a mapping from code provision to applies_to list
            # Normalize code provisions (remove trailing periods) for matching
            provision_links = {}
            for link in linkings:
                code = link.get('code_provision', '').rstrip('.')
                applies_to = link.get('applies_to', [])
                provision_links[code] = applies_to

            # Add applies_to to original provisions
            for provision in original_provisions:
                code = provision['code_provision'].rstrip('.')
                if code in provision_links:
                    provision['applies_to'] = provision_links[code]
                    logger.info(f"Provision {code}: {len(provision_links[code])} entity links")
                else:
                    provision['applies_to'] = []
                    logger.warning(f"Provision {code} not found in LLM response")

            return original_provisions

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse linking JSON: {e}")
            return original_provisions

    def extract_relevant_excerpts(
        self,
        provisions: List[Dict],
        case_sections: Dict[str, str]
    ) -> List[Dict]:
        """
        Extract specific text excerpts from case sections that relate to each provision.

        Args:
            provisions: List of code provisions
            case_sections: Dict with keys like 'facts', 'discussion', 'questions', 'conclusions'
                          and values being the text content

        Returns:
            List of provisions with 'relevant_excerpts' added
        """
        if not self.llm_client:
            logger.warning("No LLM client, skipping excerpt extraction")
            return provisions

        logger.info(f"Extracting relevant excerpts for {len(provisions)} provisions")

        # Create prompt
        prompt = self._create_excerpt_prompt(provisions, case_sections)

        try:
            response = self.llm_client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=8000,
                temperature=0.1,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = response.content[0].text

            # Parse excerpts from response
            provisions_with_excerpts = self._parse_excerpts_response(response_text, provisions)

            logger.info("Successfully extracted relevant excerpts")
            return provisions_with_excerpts

        except Exception as e:
            logger.error(f"Error extracting excerpts: {e}")
            return provisions

    def _create_excerpt_prompt(
        self,
        provisions: List[Dict],
        case_sections: Dict[str, str]
    ) -> str:
        """Create prompt for extracting relevant case text excerpts."""

        provisions_text = "\n\n".join([
            f"**{p['code_provision']}**: {p['provision_text']}"
            for p in provisions
        ])

        sections_text = ""
        for section_name, section_text in case_sections.items():
            sections_text += f"\n**{section_name.upper()}:**\n{section_text}\n"

        prompt = f"""You are analyzing an engineering ethics case to find specific text passages that relate to NSPE Code provisions.

**NSPE Code Provisions:**
{provisions_text}

**Case Text:**
{sections_text}

**Task:**
For each code provision, identify 1-3 specific sentences or short paragraphs from the case text that directly relate to that provision. Focus on:
- Specific situations where the provision applies
- Actions or decisions that invoke the provision
- Ethical dilemmas addressed by the provision

Only include text that DIRECTLY relates to the specific provision. Don't include generic case background.

**Output Format:**
Respond with JSON where each provision has its relevant excerpts:

```json
[
  {{
    "code_provision": "I.1",
    "excerpts": [
      {{
        "section": "facts",
        "text": "The specific sentence or paragraph from the case that relates to this provision."
      }},
      {{
        "section": "discussion",
        "text": "Another relevant passage from a different section."
      }}
    ]
  }},
  ...
]
```

**Important:**
- Only include excerpts that SPECIFICALLY relate to the provision
- Each excerpt should be 1-3 sentences (not full paragraphs unless necessary)
- Use exact text from the case (don't paraphrase)
- It's okay if a provision has no relevant excerpts
- Section names should be: "facts", "discussion", "questions", or "conclusions"
"""

        return prompt

    def _parse_excerpts_response(
        self,
        response_text: str,
        original_provisions: List[Dict]
    ) -> List[Dict]:
        """Parse LLM response with excerpts and add to provisions."""

        import json
        import re

        # Extract JSON
        json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\[\s*\{.*?\}\s*\]', response_text, re.DOTALL)
            if not json_match:
                logger.warning("Could not find JSON in excerpts response")
                return original_provisions

        try:
            json_text = json_match.group(1) if '```json' in response_text else json_match.group(0)
            excerpts_data = json.loads(json_text)

            # Create mapping
            excerpts_by_code = {}
            for item in excerpts_data:
                code = item.get('code_provision')
                excerpts = item.get('excerpts', [])
                excerpts_by_code[code] = excerpts

            # Add to provisions
            for provision in original_provisions:
                code = provision['code_provision']
                if code in excerpts_by_code:
                    provision['relevant_excerpts'] = excerpts_by_code[code]
                    logger.info(f"Provision {code}: {len(excerpts_by_code[code])} excerpts")
                else:
                    provision['relevant_excerpts'] = []

            return original_provisions

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse excerpts JSON: {e}")
            return original_provisions

    def get_last_prompt_and_response(self) -> Dict:
        """Return the last linking prompt and response for UI display."""
        return {
            'prompt': self.last_linking_prompt,
            'response': self.last_linking_response
        }
