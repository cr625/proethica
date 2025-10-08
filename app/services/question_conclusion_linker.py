"""
Question-Conclusion Linker

Links ethical questions to their corresponding conclusions using LLM analysis.
Creates answersQuestion RDF properties based on McLaren framework.
"""

import json
import re
import logging
from typing import List, Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class QuestionConclusionLink:
    """Represents a Q→C link."""
    question_number: int
    conclusion_number: int
    confidence: float
    reasoning: str


class QuestionConclusionLinker:
    """
    Links questions to conclusions using LLM semantic analysis.

    Handles:
    - Multiple questions → single conclusion
    - Single question → multiple conclusions
    - Implicit Q-C relationships
    """

    def __init__(self, llm_client=None):
        """
        Initialize linker.

        Args:
            llm_client: Claude API client
        """
        self.llm_client = llm_client
        self.last_prompt = None
        self.last_response = None

    def link_questions_to_conclusions(
        self,
        questions: List,  # List of EthicalQuestion objects
        conclusions: List  # List of EthicalConclusion objects
    ) -> List[QuestionConclusionLink]:
        """
        Determine which conclusion answers which question.

        Args:
            questions: List of EthicalQuestion objects
            conclusions: List of EthicalConclusion objects

        Returns:
            List of QuestionConclusionLink objects
        """
        if not self.llm_client:
            logger.warning("No LLM client, cannot link Q→C")
            return []

        if not questions or not conclusions:
            logger.warning("No questions or conclusions to link")
            return []

        logger.info(f"Linking {len(questions)} questions to {len(conclusions)} conclusions")

        # Create linking prompt
        prompt = self._create_linking_prompt(questions, conclusions)
        self.last_prompt = prompt

        try:
            response = self.llm_client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=4000,
                temperature=0.1,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = response.content[0].text
            self.last_response = response_text

            # Parse response
            links = self._parse_response(response_text)

            logger.info(f"Created {len(links)} Q→C links")

            return links

        except Exception as e:
            logger.error(f"Error linking Q→C: {e}")
            return []

    def _create_linking_prompt(
        self,
        questions: List,
        conclusions: List
    ) -> str:
        """Create LLM prompt for Q→C linking."""

        # Format questions
        questions_text = ""
        for q in questions:
            questions_text += f"\n**Question {q.question_number}:**\n"
            questions_text += f"\"{q.question_text}\"\n"

        # Format conclusions
        conclusions_text = ""
        for c in conclusions:
            conclusions_text += f"\n**Conclusion {c.conclusion_number}:**\n"
            conclusions_text += f"\"{c.conclusion_text}\"\n"
            conclusions_text += f"Type: {c.conclusion_type}\n"

        prompt = f"""You are analyzing NSPE Board of Ethical Review questions and conclusions to determine which conclusion answers which question.

**QUESTIONS:**
{questions_text}

**CONCLUSIONS:**
{conclusions_text}

**TASK:**
For each conclusion, determine which question(s) it answers.

Consider:
- Direct answers: Conclusion explicitly addresses the question
- Partial answers: Conclusion addresses part of a multi-part question
- Implicit answers: Conclusion answers question without restating it

**OUTPUT FORMAT (JSON):**
```json
[
  {{
    "conclusion_number": 1,
    "answers_questions": [1],
    "confidence": 0.95,
    "reasoning": "Conclusion 1 directly addresses Question 1 by stating whether Engineer A violated II.4.e, which is exactly what Question 1 asked."
  }},
  {{
    "conclusion_number": 2,
    "answers_questions": [1, 2],
    "confidence": 0.90,
    "reasoning": "Conclusion 2 addresses both Question 1 (violation determination) and Question 2 (disclosure requirement) as related issues."
  }}
]
```

**IMPORTANT:**
- A conclusion can answer multiple questions
- Multiple conclusions can answer the same question
- Provide confidence (0.0-1.0) and reasoning for each link
- If a conclusion doesn't answer any question, use answers_questions: []
"""

        return prompt

    def _parse_response(self, response_text: str) -> List[QuestionConclusionLink]:
        """Parse LLM response into QuestionConclusionLink objects."""

        # Extract JSON
        json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\[\s*\{.*?\}\s*\]', response_text, re.DOTALL)
            if not json_match:
                logger.warning("Could not find JSON in response")
                return []

        try:
            json_text = json_match.group(1) if '```json' in response_text else json_match.group(0)
            links_data = json.loads(json_text)

            links = []
            for link_data in links_data:
                conclusion_num = link_data.get('conclusion_number')
                question_nums = link_data.get('answers_questions', [])
                confidence = link_data.get('confidence', 0.5)
                reasoning = link_data.get('reasoning', '')

                # Create a link for each question this conclusion answers
                for question_num in question_nums:
                    link = QuestionConclusionLink(
                        question_number=question_num,
                        conclusion_number=conclusion_num,
                        confidence=confidence,
                        reasoning=reasoning
                    )
                    links.append(link)

                    logger.debug(
                        f"Link: Q{question_num} → C{conclusion_num} "
                        f"(confidence: {confidence})"
                    )

            return links

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse links JSON: {e}")
            return []

    def apply_links_to_conclusions(
        self,
        conclusions: List,
        links: List[QuestionConclusionLink]
    ) -> List:
        """
        Add answersQuestion information to conclusion objects.

        Args:
            conclusions: List of EthicalConclusion objects
            links: List of QuestionConclusionLink objects

        Returns:
            Updated conclusions list
        """
        # Group links by conclusion
        links_by_conclusion = {}
        for link in links:
            if link.conclusion_number not in links_by_conclusion:
                links_by_conclusion[link.conclusion_number] = []
            links_by_conclusion[link.conclusion_number].append(link)

        # Add to conclusions
        for conclusion in conclusions:
            conclusion_links = links_by_conclusion.get(conclusion.conclusion_number, [])
            conclusion.answers_questions = [
                link.question_number for link in conclusion_links
            ]
            conclusion.link_confidences = {
                link.question_number: link.confidence
                for link in conclusion_links
            }

        return conclusions

    def get_last_prompt_and_response(self) -> Dict:
        """Return last prompt and response for debugging."""
        return {
            'prompt': self.last_prompt,
            'response': self.last_response
        }
