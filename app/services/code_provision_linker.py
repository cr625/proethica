"""
Code Provision Entity Linking Service

Links NSPE code provisions to extracted case entities (Roles, States, Resources)
using LLM-based semantic matching.
"""

import logging
import json
import re
from typing import List, Dict

from models import ModelConfig

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
        roles: List[Dict] = None,
        states: List[Dict] = None,
        resources: List[Dict] = None,
        principles: List[Dict] = None,
        obligations: List[Dict] = None,
        constraints: List[Dict] = None,
        capabilities: List[Dict] = None,
        actions: List[Dict] = None,
        events: List[Dict] = None,
        case_text_summary: str = ""
    ) -> List[Dict]:
        """
        Link code provisions to applicable case entities (all 9 types).

        Args:
            provisions: List of parsed code provisions
            roles: List of role entities
            states: List of state entities
            resources: List of resource entities
            principles: List of principle entities
            obligations: List of obligation entities
            constraints: List of constraint entities
            capabilities: List of capability entities
            actions: List of action entities
            events: List of event entities
            case_text_summary: Brief summary of the case

        Returns:
            List of provisions with 'applies_to' relationships added
        """
        if not self.llm_client:
            logger.warning("No LLM client provided, skipping entity linking")
            return provisions

        if not provisions:
            logger.info("No provisions to link")
            return []

        # Build entity groups for batched processing
        entity_groups = [
            ('role', 'Roles', roles or []),
            ('state', 'States', states or []),
            ('resource', 'Resources', resources or []),
            ('principle', 'Principles', principles or []),
            ('obligation', 'Obligations', obligations or []),
            ('constraint', 'Constraints', constraints or []),
            ('capability', 'Capabilities', capabilities or []),
            ('action', 'Actions', actions or []),
            ('event', 'Events', events or []),
        ]

        total_entities = sum(len(g[2]) for g in entity_groups)
        entity_counts = {g[1].lower(): len(g[2]) for g in entity_groups}
        logger.info(f"Linking {len(provisions)} provisions to {total_entities} total entities across 9 types")
        logger.info(f"Entity breakdown: {entity_counts}")

        # Initialize applies_to for each provision
        for provision in provisions:
            provision['applies_to'] = []

        # Process one entity type at a time to avoid timeout on large payloads
        all_prompts = []
        all_responses = []
        for entity_type, type_label, entities in entity_groups:
            if not entities:
                continue

            prompt = self._create_batch_linking_prompt(
                provisions, entity_type, type_label, entities, case_text_summary
            )
            all_prompts.append(prompt)

            try:
                response = self.llm_client.messages.create(
                    model=ModelConfig.get_claude_model("default"),
                    max_tokens=2000,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = response.content[0].text
                all_responses.append(response_text)

                # Parse and merge links
                batch_links = self._parse_batch_response(response_text, entity_type)
                for provision in provisions:
                    code = provision['code_provision'].rstrip('.')
                    if code in batch_links:
                        provision['applies_to'].extend(batch_links[code])

                logger.info(f"Linked {type_label}: {sum(len(batch_links.get(p['code_provision'].rstrip('.'), [])) for p in provisions)} links")

            except Exception as e:
                logger.error(f"Error linking {type_label}: {e}")

        self.last_linking_prompt = "\n\n---BATCH---\n\n".join(all_prompts)
        self.last_linking_response = "\n\n---BATCH---\n\n".join(all_responses)

        total_links = sum(len(p.get('applies_to', [])) for p in provisions)
        logger.info(f"Provision linking complete: {total_links} total links across {len(provisions)} provisions")
        return provisions

    def _create_batch_linking_prompt(
        self,
        provisions: List[Dict],
        entity_type: str,
        type_label: str,
        entities: List[Dict],
        case_summary: str
    ) -> str:
        """Create prompt for linking provisions to a single entity type."""

        provisions_text = ""
        for i, prov in enumerate(provisions, 1):
            provisions_text += f"{i}. **{prov['code_provision']}**: {prov['provision_text']}\n"

        entities_text = self._format_entities_for_prompt(entities, type_label)

        type_descriptions = {
            'role': 'The provision governs the professional conduct of that role',
            'state': 'The provision addresses or relates to that ethical situation',
            'resource': 'The provision references or requires that resource/document',
            'principle': 'The provision embodies or relates to that principle',
            'obligation': 'The provision specifies or relates to that obligation',
            'constraint': 'The provision creates or relates to that constraint',
            'capability': 'The provision requires or relates to that capability',
            'action': 'The provision governs or prohibits that action',
            'event': 'The provision addresses that event or occurrence',
        }
        applicability = type_descriptions.get(entity_type, '')

        prompt = f"""Link NSPE Code provisions to extracted {type_label} entities from this engineering ethics case.

**Case Context:**
{case_summary if case_summary else "Engineering professional ethics case."}

**NSPE Code Provisions (Board-Selected):**
{provisions_text}

**{type_label} Entities:**
{entities_text}

A provision applies to a {entity_type} entity if: {applicability}

For each provision, list which {type_label.lower()} entities it applies to (if any). Only include clear, direct connections.

Respond with JSON:
```json
[
  {{
    "code_provision": "I.1",
    "applies_to": [
      {{"entity_label": "Example Entity", "reasoning": "Brief case-specific reason"}}
    ]
  }}
]
```

Use exact entity labels. Omit provisions with no links to these entities."""

        return prompt

    def _parse_batch_response(self, response_text: str, entity_type: str) -> Dict[str, List[Dict]]:
        """Parse batch linking response, returning {provision_code: [links]}."""
        from_code_block = False
        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response_text, re.DOTALL)
        if json_match:
            from_code_block = True
        else:
            json_match = re.search(r'\[\s*\{.*?\}\s*\]', response_text, re.DOTALL)
            if not json_match:
                logger.warning(f"No JSON in {entity_type} linking response")
                return {}

        try:
            json_text = json_match.group(1) if from_code_block else json_match.group(0)
            linkings = json.loads(json_text)

            result = {}
            for link in linkings:
                code = link.get('code_provision', '').rstrip('.')
                applies_to = []
                for item in link.get('applies_to', []):
                    applies_to.append({
                        'entity_type': entity_type,
                        'entity_label': item.get('entity_label', ''),
                        'reasoning': item.get('reasoning', ''),
                    })
                if applies_to:
                    result[code] = applies_to
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {entity_type} linking JSON: {e}")
            return {}

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
                model=ModelConfig.get_claude_model("default"),
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
