"""
Conclusion Analyzer

Extracts ethical conclusions from Conclusions section with full entity context.
Tags entities mentioned (all 9 types), links to code provisions, and prepares
for Q→C linking.
"""

import json
import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EthicalConclusion:
    """Represents an extracted ethical conclusion."""
    conclusion_number: int
    conclusion_text: str
    mentioned_entities: Dict[str, List[str]]  # entity_type → [entity_labels]
    cited_provisions: List[str]  # Code provisions cited
    conclusion_type: str  # 'violation', 'compliance', 'interpretation', etc.
    extraction_reasoning: str
    # Note: answersQuestion link will be added by QuestionConclusionLinker


class ConclusionAnalyzer:
    """
    Analyzes Conclusions section with complete entity context.

    Extracts conclusions and tags:
    - All entity types mentioned
    - Code provisions cited in reasoning
    - Conclusion type (violation, compliance, etc.)
    """

    def __init__(self, llm_client=None):
        """
        Initialize analyzer.

        Args:
            llm_client: Claude API client
        """
        self.llm_client = llm_client
        self.last_prompt = None
        self.last_response = None

    def extract_conclusions(
        self,
        conclusions_text: str,
        all_entities: Dict[str, List],
        code_provisions: List[Dict] = None
    ) -> List[EthicalConclusion]:
        """
        Extract ethical conclusions with entity tagging.

        Args:
            conclusions_text: Conclusions section text
            all_entities: Dict with all 9 entity types
            code_provisions: List of extracted code provisions (optional)

        Returns:
            List of EthicalConclusion objects
        """
        if not self.llm_client:
            logger.warning("No LLM client, cannot extract conclusions")
            return []

        if not conclusions_text or not conclusions_text.strip():
            logger.warning("No conclusions text provided")
            return []

        logger.info("Extracting conclusions with full entity context")

        # Create extraction prompt
        prompt = self._create_extraction_prompt(
            conclusions_text,
            all_entities,
            code_provisions
        )
        self.last_prompt = prompt

        try:
            response = self.llm_client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=6000,
                temperature=0.1,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = response.content[0].text
            self.last_response = response_text

            # Parse response
            conclusions = self._parse_response(response_text)

            logger.info(f"Extracted {len(conclusions)} conclusions")

            return conclusions

        except Exception as e:
            logger.error(f"Error extracting conclusions: {e}")
            return []

    def _create_extraction_prompt(
        self,
        conclusions_text: str,
        all_entities: Dict[str, List],
        code_provisions: List[Dict]
    ) -> str:
        """Create LLM prompt for conclusion extraction."""

        # Format entities by type
        entities_text = self._format_all_entities(all_entities)

        # Format code provisions
        provisions_text = ""
        if code_provisions:
            provisions_text = "\n**CODE PROVISIONS EXTRACTED:**\n"
            for prov in code_provisions:
                provisions_text += f"- {prov['code_provision']}: {prov['provision_text'][:100]}...\n"

        prompt = f"""You are analyzing the Conclusions section from an NSPE Board of Ethical Review case.

**CONCLUSIONS SECTION TEXT:**
{conclusions_text}

**EXTRACTED CASE ENTITIES:**
{entities_text}

{provisions_text}

**TASK:**
Extract each ethical conclusion and analyze:

1. **Conclusion Text**: The verbatim conclusion text
2. **Mentioned Entities**: Which entities are referenced?
   - For each entity type
   - Use EXACT labels from the entity list above
3. **Cited Provisions**: Which code provisions are cited in the reasoning?
4. **Conclusion Type**: What kind of conclusion?
   - 'violation': Found a violation of ethics code
   - 'compliance': Found compliance with ethics code
   - 'no_violation': Found no violation occurred
   - 'interpretation': Clarifies interpretation of provision
   - 'recommendation': Recommends action
5. **Reasoning**: Brief explanation of the conclusion

**OUTPUT FORMAT (JSON):**
```json
[
  {{
    "conclusion_number": 1,
    "conclusion_text": "Engineer A violated Section II.4.e by accepting the contract while serving on the town board.",
    "mentioned_entities": {{
      "roles": ["Engineer A"],
      "actions": ["accepting the contract"],
      "states": ["serving on the town board"]
    }},
    "cited_provisions": ["II.4.e"],
    "conclusion_type": "violation",
    "extraction_reasoning": "The Board concluded Engineer A committed a violation of II.4.e through the specific action of accepting a contract while in a prohibited state."
  }}
]
```

**IMPORTANT:**
- Use EXACT entity labels from the lists above
- Extract ALL conclusions (may be multiple)
- Empty arrays are fine if no entities of that type mentioned
- Identify provisions cited in the Board's reasoning
"""

        return prompt

    def _format_all_entities(self, all_entities: Dict[str, List]) -> str:
        """Format all entity types for prompt."""

        entity_types = [
            ('roles', 'Roles'),
            ('states', 'States'),
            ('resources', 'Resources'),
            ('principles', 'Principles'),
            ('obligations', 'Obligations'),
            ('constraints', 'Constraints'),
            ('capabilities', 'Capabilities'),
            ('actions', 'Actions'),
            ('events', 'Events')
        ]

        formatted = ""
        for key, display_name in entity_types:
            entities = all_entities.get(key, [])
            if entities:
                formatted += f"\n**{display_name}:**\n"
                for entity in entities:
                    # Handle both dict and model objects
                    if isinstance(entity, dict):
                        label = entity.get('label', 'Unknown')
                        definition = entity.get('definition', '')
                    else:
                        # SQLAlchemy model object
                        label = getattr(entity, 'entity_label', 'Unknown')
                        definition = getattr(entity, 'entity_definition', '')

                    formatted += f"  - {label}"
                    if definition and len(definition) < 100:
                        formatted += f": {definition}"
                    formatted += "\n"
            else:
                formatted += f"\n**{display_name}:** (none)\n"

        return formatted

    def _parse_response(self, response_text: str) -> List[EthicalConclusion]:
        """Parse LLM response into EthicalConclusion objects."""

        # Extract JSON
        json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\[\s*\{.*?\}\s*\]', response_text, re.DOTALL)
            if not json_match:
                logger.warning("Could not find JSON in response")
                return []

        try:
            json_text = json_match.group(1) if '```json' in response_text else json_match.group(0)
            conclusions_data = json.loads(json_text)

            conclusions = []
            for c_data in conclusions_data:
                conclusion = EthicalConclusion(
                    conclusion_number=c_data.get('conclusion_number', 0),
                    conclusion_text=c_data.get('conclusion_text', ''),
                    mentioned_entities=c_data.get('mentioned_entities', {}),
                    cited_provisions=c_data.get('cited_provisions', []),
                    conclusion_type=c_data.get('conclusion_type', 'unknown'),
                    extraction_reasoning=c_data.get('extraction_reasoning', '')
                )
                conclusions.append(conclusion)

                logger.debug(
                    f"Conclusion {conclusion.conclusion_number}: "
                    f"type={conclusion.conclusion_type}, "
                    f"{len(conclusion.mentioned_entities)} entity types, "
                    f"{len(conclusion.cited_provisions)} provisions"
                )

            return conclusions

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse conclusions JSON: {e}")
            return []

    def get_last_prompt_and_response(self) -> Dict:
        """Return last prompt and response for debugging."""
        return {
            'prompt': self.last_prompt,
            'response': self.last_response
        }
