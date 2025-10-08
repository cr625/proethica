"""
Question Analyzer

Extracts ethical questions from Questions section with full entity context.
Tags entities mentioned (all 9 types) and links to code provisions.
"""

import json
import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EthicalQuestion:
    """Represents an extracted ethical question."""
    question_number: int
    question_text: str
    mentioned_entities: Dict[str, List[str]]  # entity_type → [entity_labels]
    related_provisions: List[str]  # Code provision numbers
    extraction_reasoning: str


class QuestionAnalyzer:
    """
    Analyzes Questions section with complete entity context.

    Extracts questions and tags:
    - All entity types mentioned (Roles, Principles, Actions, etc.)
    - Code provisions referenced
    - Question structure and focus
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

    def extract_questions(
        self,
        questions_text: str,
        all_entities: Dict[str, List],
        code_provisions: List[Dict] = None
    ) -> List[EthicalQuestion]:
        """
        Extract ethical questions with entity tagging.

        Args:
            questions_text: Questions section text
            all_entities: Dict with all 9 entity types
                         {
                             'roles': [...],
                             'states': [...],
                             'resources': [...],
                             'principles': [...],
                             'obligations': [...],
                             'constraints': [...],
                             'capabilities': [...],
                             'actions': [...],
                             'events': [...]
                         }
            code_provisions: List of extracted code provisions (optional)

        Returns:
            List of EthicalQuestion objects
        """
        if not self.llm_client:
            logger.warning("No LLM client, cannot extract questions")
            return []

        if not questions_text or not questions_text.strip():
            logger.warning("No questions text provided")
            return []

        logger.info("Extracting questions with full entity context")

        # Create extraction prompt
        prompt = self._create_extraction_prompt(
            questions_text,
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
            questions = self._parse_response(response_text)

            logger.info(f"Extracted {len(questions)} questions")

            return questions

        except Exception as e:
            logger.error(f"Error extracting questions: {e}")
            return []

    def _create_extraction_prompt(
        self,
        questions_text: str,
        all_entities: Dict[str, List],
        code_provisions: List[Dict]
    ) -> str:
        """Create LLM prompt for question extraction."""

        # Format entities by type
        entities_text = self._format_all_entities(all_entities)

        # Format code provisions
        provisions_text = ""
        if code_provisions:
            provisions_text = "\n**CODE PROVISIONS EXTRACTED:**\n"
            for prov in code_provisions:
                provisions_text += f"- {prov['code_provision']}: {prov['provision_text'][:100]}...\n"

        prompt = f"""You are analyzing the Questions section from an NSPE Board of Ethical Review case.

**QUESTIONS SECTION TEXT:**
{questions_text}

**EXTRACTED CASE ENTITIES:**
{entities_text}

{provisions_text}

**TASK:**
Extract each ethical question and analyze:

1. **Question Text**: The verbatim question text
2. **Mentioned Entities**: Which entities from the case are referenced?
   - For each entity type (Roles, States, Resources, Principles, Obligations, etc.)
   - Use EXACT labels from the entity list above
3. **Related Provisions**: Which code provisions (if any) are mentioned?
4. **Reasoning**: Brief explanation of what the question asks

**OUTPUT FORMAT (JSON):**
```json
[
  {{
    "question_number": 1,
    "question_text": "Did Engineer A's acceptance of the contract violate Section II.4.e?",
    "mentioned_entities": {{
      "roles": ["Engineer A"],
      "actions": ["acceptance of contract"],
      "obligations": ["Section II.4.e requirement"]
    }},
    "related_provisions": ["II.4.e"],
    "extraction_reasoning": "This question asks whether a specific action (accepting contract) by a role (Engineer A) violated an obligation (II.4.e)."
  }}
]
```

**IMPORTANT:**
- Use EXACT entity labels from the lists above
- Extract ALL questions (even if multiple)
- Empty arrays are fine if no entities of that type are mentioned
- Include reasoning for each question
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
                    label = getattr(entity, 'entity_label', None) or entity.get('label', 'Unknown')
                    definition = getattr(entity, 'entity_definition', None) or entity.get('definition', '')

                    formatted += f"  - {label}"
                    if definition and len(definition) < 100:
                        formatted += f": {definition}"
                    formatted += "\n"
            else:
                formatted += f"\n**{display_name}:** (none)\n"

        return formatted

    def _parse_response(self, response_text: str) -> List[EthicalQuestion]:
        """Parse LLM response into EthicalQuestion objects."""

        # Extract JSON
        json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\[\s*\{.*?\}\s*\]', response_text, re.DOTALL)
            if not json_match:
                logger.warning("Could not find JSON in response")
                return []

        try:
            json_text = json_match.group(1) if '```json' in response_text else json_match.group(0)
            questions_data = json.loads(json_text)

            questions = []
            for q_data in questions_data:
                question = EthicalQuestion(
                    question_number=q_data.get('question_number', 0),
                    question_text=q_data.get('question_text', ''),
                    mentioned_entities=q_data.get('mentioned_entities', {}),
                    related_provisions=q_data.get('related_provisions', []),
                    extraction_reasoning=q_data.get('extraction_reasoning', '')
                )
                questions.append(question)

                logger.debug(
                    f"Question {question.question_number}: "
                    f"{len(question.mentioned_entities)} entity types mentioned, "
                    f"{len(question.related_provisions)} provisions"
                )

            return questions

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse questions JSON: {e}")
            return []

    def get_last_prompt_and_response(self) -> Dict:
        """Return last prompt and response for debugging."""
        return {
            'prompt': self.last_prompt,
            'response': self.last_response
        }
