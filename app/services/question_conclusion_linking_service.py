"""
Question→Conclusion Linking Service

Maps individual questions to their corresponding conclusions in NSPE case analysis.
This implements McLaren's framework where ethical questions lead to normative conclusions.

Based on the NSPE case structure where:
- Questions section contains numbered ethical questions (e.g., "1. Was it ethical to...")
- Conclusions section contains numbered responses (e.g., "1. It was not unethical to...")
"""

import logging
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from models import ModelConfig

logger = logging.getLogger(__name__)


@dataclass
class QuestionConclusionPair:
    """Represents a linked Question→Conclusion pair."""
    question_number: int
    question_text: str
    conclusion_text: str
    confidence: float  # 0.0 to 1.0
    reasoning: str  # Why this mapping was made


class QuestionConclusionLinkingService:
    """
    Service for mapping questions to their conclusions.

    Uses both structural analysis (numbering) and LLM verification
    to ensure accurate question→conclusion relationships.
    """

    def __init__(self, llm_client=None):
        """
        Initialize the linking service.

        Args:
            llm_client: LLM client for semantic verification
        """
        self.llm_client = llm_client
        self.last_linking_prompt = None
        self.last_linking_response = None
        logger.info("QuestionConclusionLinkingService initialized")

    def extract_numbered_items(self, text: str) -> List[Tuple[int, str]]:
        """
        Extract numbered items from text.

        Handles formats like:
        - "1. Was it ethical..."
        - "Was it ethical... Would it be ethical..."

        Returns:
            List of (number, text) tuples
        """
        # Try to find numbered items first
        # Pattern: "1. Text" or "1) Text" or "(1) Text"
        pattern = r'(?:^|\n)\s*(\d+)[\.)]\s*(.+?)(?=\n\s*\d+[\.)]|\Z)'
        matches = re.findall(pattern, text, re.DOTALL | re.MULTILINE)

        if matches:
            items = [(int(num), text.strip()) for num, text in matches]
            logger.info(f"Found {len(items)} numbered items using regex")
            return items

        # Fallback: split by sentence and number them
        # This handles cases where text isn't explicitly numbered
        sentences = [s.strip() for s in text.split('?') if s.strip()]
        if sentences:
            # Add back question marks
            sentences = [s + '?' if '?' not in s else s for s in sentences]
            items = [(i+1, s.strip()) for i, s in enumerate(sentences)]
            logger.info(f"Created {len(items)} items from sentence splitting")
            return items

        return []

    def link_questions_to_conclusions(
        self,
        questions_text: str,
        conclusions_text: str,
        use_llm_verification: bool = True
    ) -> List[QuestionConclusionPair]:
        """
        Create Question→Conclusion mappings.

        Args:
            questions_text: Full text of Questions section
            conclusions_text: Full text of Conclusions section
            use_llm_verification: Whether to verify with LLM (default True)

        Returns:
            List of QuestionConclusionPair objects
        """
        logger.info("Linking questions to conclusions")

        # Extract numbered items
        questions = self.extract_numbered_items(questions_text)
        conclusions = self.extract_numbered_items(conclusions_text)

        logger.info(f"Extracted {len(questions)} questions and {len(conclusions)} conclusions")

        if not questions or not conclusions:
            logger.warning("No questions or conclusions found")
            return []

        # Initial mapping based on numbering
        pairs = []
        for q_num, q_text in questions:
            # Find matching conclusion number
            matching_conclusion = None
            for c_num, c_text in conclusions:
                if c_num == q_num:
                    matching_conclusion = c_text
                    break

            if matching_conclusion:
                pairs.append(QuestionConclusionPair(
                    question_number=q_num,
                    question_text=q_text,
                    conclusion_text=matching_conclusion,
                    confidence=0.95,  # High confidence for number-based matching
                    reasoning=f"Matched by number {q_num}"
                ))

        logger.info(f"Created {len(pairs)} question→conclusion pairs from numbering")

        # LLM verification to ensure semantic correctness
        if use_llm_verification and self.llm_client and pairs:
            pairs = self._verify_links_with_llm(pairs)

        return pairs

    def _verify_links_with_llm(
        self,
        pairs: List[QuestionConclusionPair]
    ) -> List[QuestionConclusionPair]:
        """
        Use LLM to verify that question→conclusion mappings are semantically correct.

        This catches cases where numbering might be misleading or incorrect.
        """
        logger.info(f"Verifying {len(pairs)} question→conclusion links with LLM")

        # Build verification prompt
        prompt = self._create_verification_prompt(pairs)
        self.last_linking_prompt = prompt

        try:
            # Call LLM
            response = self.llm_client.messages.create(
                model=ModelConfig.get_claude_model("default"),
                max_tokens=4000,
                temperature=0.0,  # Deterministic for verification
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = response.content[0].text
            self.last_linking_response = response_text

            # Parse LLM response
            verified_pairs = self._parse_verification_response(response_text, pairs)

            logger.info(f"LLM verified {len(verified_pairs)} links")
            return verified_pairs

        except Exception as e:
            logger.error(f"LLM verification failed: {e}")
            # Return original pairs on error
            return pairs

    def _create_verification_prompt(self, pairs: List[QuestionConclusionPair]) -> str:
        """Create prompt for LLM verification of question→conclusion links."""

        pairs_text = "\n\n".join([
            f"**Pair {p.question_number}:**\n"
            f"Question: {p.question_text}\n"
            f"Conclusion: {p.conclusion_text}"
            for p in pairs
        ])

        prompt = f"""You are verifying question→conclusion mappings in an NSPE engineering ethics case.

I have mapped questions to conclusions based on their numbering. Please verify that each conclusion actually answers its paired question.

{pairs_text}

For each pair, output a JSON object with:
- pair_number: The pair number
- is_correct: true/false whether the conclusion answers the question
- confidence: 0.0-1.0 confidence in your judgment
- reasoning: Brief explanation

Format your response as a JSON array:
```json
[
  {{"pair_number": 1, "is_correct": true, "confidence": 0.95, "reasoning": "..."}},
  {{"pair_number": 2, "is_correct": true, "confidence": 0.90, "reasoning": "..."}}
]
```"""

        return prompt

    def _parse_verification_response(
        self,
        response_text: str,
        original_pairs: List[QuestionConclusionPair]
    ) -> List[QuestionConclusionPair]:
        """Parse LLM verification response and update pair confidences."""

        import json

        # Extract JSON from response
        json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
        if not json_match:
            logger.warning("Could not find JSON in LLM response")
            return original_pairs

        try:
            verifications = json.loads(json_match.group(1))

            # Update confidences based on LLM verification
            for verification in verifications:
                pair_num = verification['pair_number']
                is_correct = verification['is_correct']
                llm_confidence = verification['confidence']
                llm_reasoning = verification['reasoning']

                # Find the pair
                for pair in original_pairs:
                    if pair.question_number == pair_num:
                        if is_correct:
                            # Use LLM confidence if it verified the link
                            pair.confidence = llm_confidence
                            pair.reasoning += f" (LLM verified: {llm_reasoning})"
                        else:
                            # Mark as low confidence if LLM disagreed
                            pair.confidence = 0.3
                            pair.reasoning += f" (LLM disputed: {llm_reasoning})"
                        break

            return original_pairs

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse verification JSON: {e}")
            return original_pairs

    def store_question_conclusion_links(
        self,
        pairs: List[QuestionConclusionPair],
        case_id: int,
        extraction_session_id: str
    ) -> List[Dict]:
        """
        Prepare storage entries for question→conclusion links.

        Returns:
            List of dictionaries ready for TemporaryRDFStorage insertion
        """
        storage_entries = []

        for pair in pairs:
            entry = {
                'case_id': case_id,
                'extraction_session_id': extraction_session_id,
                'extraction_type': 'question_conclusion_link',
                'storage_type': 'relationship',  # This is a relationship, not an entity
                'entity_type': 'QuestionConclusionLink',
                'entity_label': f"Q{pair.question_number}→C{pair.question_number}",
                'entity_definition': f"Links question {pair.question_number} to its conclusion",
                'rdf_json_ld': {
                    '@type': 'QuestionConclusionLink',
                    'questionNumber': pair.question_number,
                    'questionText': pair.question_text,
                    'conclusionText': pair.conclusion_text,
                    'confidence': pair.confidence,
                    'reasoning': pair.reasoning,
                    'linkType': 'answers'  # The conclusion "answers" the question
                }
            }
            storage_entries.append(entry)

        logger.info(f"Prepared {len(storage_entries)} question→conclusion link storage entries")
        return storage_entries
