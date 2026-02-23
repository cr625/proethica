"""
Provision Group Validator

Validates that grouped provision mentions actually discuss the provision's content.
Simpler than the original validator because we already know which provision is mentioned.
"""

import logging
from typing import List, Dict
from dataclasses import dataclass

from models import ModelConfig

logger = logging.getLogger(__name__)


@dataclass
class ValidatedMention:
    """A provision mention that has been validated by LLM."""
    section: str
    excerpt: str
    citation_text: str
    is_relevant: bool  # Does it discuss this provision's content?
    confidence: float  # 0.0-1.0
    reasoning: str  # Why validated/rejected
    content_type: str  # What's discussed: 'compliance', 'violation', 'interpretation', etc.


class ProvisionGroupValidator:
    """
    Validates that grouped mentions actually discuss the provision's content.

    This is simpler than pattern-based validation because:
    - We already KNOW which provision is mentioned (it's explicitly cited)
    - Just need to confirm the content is relevant to that provision
    """

    def __init__(self, llm_client=None):
        """
        Initialize validator.

        Args:
            llm_client: Claude API client for validation
        """
        self.llm_client = llm_client
        self.last_validation_prompt = None
        self.last_validation_response = None

    def validate_group(
        self,
        provision_code: str,
        provision_text: str,
        mentions: List,  # List of ProvisionMention objects
        batch_size: int = 10
    ) -> List[ValidatedMention]:
        """
        Validate all mentions for a provision.

        Args:
            provision_code: Code like "II.4.e"
            provision_text: Full text of the provision
            mentions: List of ProvisionMention objects
            batch_size: How many to validate per LLM call

        Returns:
            List of ValidatedMention objects (only relevant ones with confidence > 0.5)
        """
        if not self.llm_client:
            logger.warning("No LLM client, skipping validation")
            # Return all as unvalidated
            return [
                ValidatedMention(
                    section=m.section,
                    excerpt=m.excerpt,
                    citation_text=m.citation_text,
                    is_relevant=True,  # Assume relevant without validation
                    confidence=0.7,  # Lower confidence
                    reasoning="No LLM validation performed",
                    content_type="unvalidated"
                )
                for m in mentions
            ]

        if not mentions:
            return []

        logger.info(
            f"Validating {len(mentions)} mentions for provision {provision_code}"
        )

        # Process in batches
        all_validated = []
        for i in range(0, len(mentions), batch_size):
            batch = mentions[i:i + batch_size]
            validated_batch = self._validate_batch(
                provision_code, provision_text, batch
            )
            all_validated.extend(validated_batch)

        # Filter to only relevant mentions with confidence > 0.5
        relevant = [v for v in all_validated if v.is_relevant and v.confidence > 0.5]

        logger.info(
            f"Validation complete: {len(relevant)}/{len(mentions)} "
            f"mentions are relevant"
        )

        return relevant

    def _validate_batch(
        self,
        provision_code: str,
        provision_text: str,
        mentions: List
    ) -> List[ValidatedMention]:
        """
        Validate a batch of mentions with single LLM call.

        Args:
            provision_code: Code like "II.4.e"
            provision_text: Full text of provision
            mentions: Up to 10 ProvisionMention objects

        Returns:
            List of ValidatedMention objects
        """
        prompt = self._create_validation_prompt(
            provision_code, provision_text, mentions
        )
        self.last_validation_prompt = prompt

        try:
            from app.utils.llm_utils import streaming_completion

            response_text = streaming_completion(
                self.llm_client,
                model=ModelConfig.get_claude_model("default"),
                max_tokens=6000,
                prompt=prompt,
                temperature=0.1
            )
            self.last_validation_response = response_text

            # Parse response
            validated = self._parse_validation_response(
                response_text, mentions
            )

            return validated

        except Exception as e:
            logger.error(f"Error in LLM validation: {e}")
            # Return mentions as unvalidated on error
            return [
                ValidatedMention(
                    section=m.section,
                    excerpt=m.excerpt,
                    citation_text=m.citation_text,
                    is_relevant=True,
                    confidence=0.6,
                    reasoning=f"Validation error: {str(e)}",
                    content_type="error"
                )
                for m in mentions
            ]

    def _create_validation_prompt(
        self,
        provision_code: str,
        provision_text: str,
        mentions: List
    ) -> str:
        """
        Create LLM prompt for validating mentions.

        Args:
            provision_code: Code like "II.4.e"
            provision_text: Full text of provision
            mentions: List of ProvisionMention objects

        Returns:
            Prompt string
        """
        # Format mentions
        mentions_text = ""
        for i, mention in enumerate(mentions, 1):
            mentions_text += f"""
MENTION {i}:
Section: {mention.section}
Citation: "{mention.citation_text}"
Excerpt: "{mention.excerpt}"
"""

        prompt = f"""You are validating that case text excerpts discuss a specific NSPE Code of Ethics provision.

**CODE PROVISION**: {provision_code}
**PROVISION TEXT**: "{provision_text}"

**TASK**: The excerpts below all explicitly mention provision {provision_code}. For each excerpt, determine:

1. **Is it RELEVANT?** Does the excerpt discuss THIS provision's content/requirements?
   - Yes: If it discusses compliance, violation, interpretation, or application of {provision_code}
   - No: If it only cites the number without discussing the content

2. **What is discussed?** (compliance, violation, interpretation, Board reasoning, etc.)

3. **Confidence**: How confident are you? (0.0-1.0)

**EXCERPTS TO VALIDATE**:
{mentions_text}

**OUTPUT FORMAT** (JSON array):
```json
[
  {{
    "mention_number": 1,
    "is_relevant": true,
    "confidence": 0.95,
    "content_type": "violation",
    "reasoning": "This excerpt discusses Engineer A's violation of {provision_code} by accepting a contract while serving on the governmental body."
  }},
  {{
    "mention_number": 2,
    "is_relevant": false,
    "confidence": 0.85,
    "content_type": "citation_only",
    "reasoning": "This excerpt merely cites {provision_code} without discussing what the provision requires or how it applies."
  }}
]
```

**IMPORTANT**:
- "is_relevant": true only if the excerpt discusses the provision's CONTENT
- "content_type" options: compliance, violation, interpretation, Board_reasoning, citation_only, background
- Be specific in reasoning - explain what content is being discussed
"""

        return prompt

    def _parse_validation_response(
        self,
        response_text: str,
        mentions: List
    ) -> List[ValidatedMention]:
        """
        Parse LLM validation response.

        Args:
            response_text: LLM response text
            mentions: Original ProvisionMention objects

        Returns:
            List of ValidatedMention objects
        """
        # Extract JSON
        from app.utils.llm_json_utils import parse_json_response

        validations = parse_json_response(response_text, context="provision_validation")
        if validations is None:
            logger.warning("Could not find JSON in validation response")
            # Return all as unvalidated
            return [
                ValidatedMention(
                    section=m.section,
                    excerpt=m.excerpt,
                    citation_text=m.citation_text,
                    is_relevant=True,
                    confidence=0.6,
                    reasoning="Could not parse validation response",
                    content_type="unvalidated"
                )
                for m in mentions
            ]

        try:

            # Create mapping
            validation_map = {v.get('mention_number'): v for v in validations}

            # Build ValidatedMention objects
            results = []
            for i, mention in enumerate(mentions, 1):
                validation = validation_map.get(i)

                if validation:
                    result = ValidatedMention(
                        section=mention.section,
                        excerpt=mention.excerpt,
                        citation_text=mention.citation_text,
                        is_relevant=validation.get('is_relevant', False),
                        confidence=validation.get('confidence', 0.0),
                        reasoning=validation.get('reasoning', ''),
                        content_type=validation.get('content_type', 'unknown')
                    )
                else:
                    # No validation found
                    result = ValidatedMention(
                        section=mention.section,
                        excerpt=mention.excerpt,
                        citation_text=mention.citation_text,
                        is_relevant=True,
                        confidence=0.6,
                        reasoning="No validation data returned",
                        content_type="unvalidated"
                    )

                results.append(result)

                logger.debug(
                    f"Mention {i}: is_relevant={result.is_relevant}, "
                    f"confidence={result.confidence}, type={result.content_type}"
                )

            return results

        except Exception as e:
            logger.error(f"Failed to process validation response: {e}")
            # Return all as unvalidated
            return [
                ValidatedMention(
                    section=m.section,
                    excerpt=m.excerpt,
                    citation_text=m.citation_text,
                    is_relevant=True,
                    confidence=0.6,
                    reasoning=f"Validation processing error: {str(e)}",
                    content_type="unvalidated"
                )
                for m in mentions
            ]

    def get_last_prompt_and_response(self) -> Dict:
        """Return last validation prompt and response for debugging."""
        return {
            'prompt': self.last_validation_prompt,
            'response': self.last_validation_response
        }
