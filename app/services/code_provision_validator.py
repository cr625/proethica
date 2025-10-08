"""
Code Provision Validator

Uses LLM to validate that matched text excerpts actually relate to
the specific code provisions they were matched with.
Eliminates false positives like "II.1.e" text appearing under "I.1.e" heading.
"""

import json
import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating an excerpt against a provision."""
    section: str
    excerpt: str
    matched_text: str
    is_match: bool
    confidence: float
    reasoning: str
    match_quality: str  # 'exact', 'related', 'tangential', 'false_positive'
    original_match_type: str  # From pattern matcher
    original_confidence: float  # From pattern matcher


class CodeProvisionValidator:
    """Validates excerpt-provision matches using LLM semantic analysis."""

    def __init__(self, llm_client=None):
        """
        Initialize validator with LLM client.

        Args:
            llm_client: Claude API client for validation
        """
        self.llm_client = llm_client
        self.last_validation_prompt = None
        self.last_validation_response = None

    def validate_batch(
        self,
        candidates: List,  # List of CandidateMatch objects
        provision: Dict
    ) -> List[ValidationResult]:
        """
        Validate multiple candidate matches in a single LLM call.

        Args:
            candidates: List of CandidateMatch objects from pattern matcher
            provision: Dict with 'code_provision' and 'provision_text'

        Returns:
            List of ValidationResult objects (only validated matches)
        """
        if not self.llm_client:
            logger.warning("No LLM client provided, skipping validation")
            # Return all candidates as unvalidated
            return [
                ValidationResult(
                    section=c.section,
                    excerpt=c.excerpt,
                    matched_text=c.matched_text,
                    is_match=True,  # Assume valid without validation
                    confidence=c.confidence,
                    reasoning="No LLM validation performed",
                    match_quality="unvalidated",
                    original_match_type=c.match_type,
                    original_confidence=c.confidence
                )
                for c in candidates
            ]

        if not candidates:
            return []

        logger.info(
            f"Validating {len(candidates)} candidates for provision "
            f"{provision['code_provision']}"
        )

        # Process in batches of 10 to avoid token limits
        batch_size = 10
        all_validated = []

        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i + batch_size]
            validated_batch = self._validate_batch_llm(batch, provision)
            all_validated.extend(validated_batch)

        # Filter to only validated matches (confidence > 0.5)
        validated_only = [v for v in all_validated if v.is_match and v.confidence > 0.5]

        logger.info(
            f"Validation complete: {len(validated_only)}/{len(candidates)} "
            f"candidates validated as true matches"
        )

        return validated_only

    def _validate_batch_llm(
        self,
        candidates: List,
        provision: Dict
    ) -> List[ValidationResult]:
        """
        Validate a batch of candidates with single LLM call.

        Args:
            candidates: Up to 10 CandidateMatch objects
            provision: Provision dictionary

        Returns:
            List of ValidationResult objects
        """
        prompt = self._create_validation_prompt(candidates, provision)
        self.last_validation_prompt = prompt

        try:
            response = self.llm_client.messages.create(
                model="claude-opus-4-20250514",
                max_tokens=6000,
                temperature=0.1,  # Low temperature for consistent validation
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = response.content[0].text
            self.last_validation_response = response_text

            # Parse LLM response
            validated = self._parse_validation_response(
                response_text,
                candidates,
                provision
            )

            return validated

        except Exception as e:
            logger.error(f"Error in LLM validation: {e}")
            # Return candidates as unvalidated on error
            return [
                ValidationResult(
                    section=c.section,
                    excerpt=c.excerpt,
                    matched_text=c.matched_text,
                    is_match=True,
                    confidence=c.confidence * 0.8,  # Reduce confidence slightly
                    reasoning=f"Validation error: {str(e)}",
                    match_quality="unvalidated",
                    original_match_type=c.match_type,
                    original_confidence=c.confidence
                )
                for c in candidates
            ]

    def _create_validation_prompt(
        self,
        candidates: List,
        provision: Dict
    ) -> str:
        """
        Create LLM prompt for batch validation.

        Args:
            candidates: List of CandidateMatch objects
            provision: Provision dictionary

        Returns:
            Prompt string
        """
        code = provision['code_provision']
        text = provision['provision_text']

        # Format candidates for prompt
        candidates_text = ""
        for i, candidate in enumerate(candidates, 1):
            candidates_text += f"""
CANDIDATE {i}:
Section: {candidate.section}
Matched Citation: "{candidate.matched_text}"
Excerpt: "{candidate.excerpt}"
"""

        prompt = f"""You are validating whether case text excerpts truly discuss a specific NSPE Code of Ethics provision.

**CRITICAL TASK**: Determine if each excerpt is ACTUALLY discussing the provision shown below, or if it's a FALSE POSITIVE (e.g., text about provision II.1.e appearing under heading I.1.e).

**CODE PROVISION**: {code}
**PROVISION TEXT**: "{text}"

**VALIDATION CRITERIA**:
1. **EXACT MATCH**: Excerpt explicitly cites {code} AND discusses its specific content
2. **RELATED MATCH**: Discusses provision content without citing the number
3. **TANGENTIAL**: Mentions {code} but discusses a different topic
4. **FALSE POSITIVE**: Text about a DIFFERENT provision (e.g., II.1.e text under I.1.e heading)

**EXCERPTS TO VALIDATE**:
{candidates_text}

**YOUR TASK**:
For each candidate, determine:
1. Is this excerpt ACTUALLY discussing provision {code}?
2. What is the match quality?
3. What is your confidence (0.0-1.0)?
4. Why did you make this determination?

**CRITICAL**: If the excerpt mentions a DIFFERENT provision number (e.g., II.1.e when we're validating I.1.e), mark it as FALSE POSITIVE with confidence 0.0.

**OUTPUT FORMAT** (JSON array):
```json
[
  {{
    "candidate_number": 1,
    "is_match": true,
    "confidence": 0.95,
    "match_quality": "exact",
    "reasoning": "Excerpt explicitly cites {code} and discusses [specific aspect]. The citation and content both match this provision."
  }},
  {{
    "candidate_number": 2,
    "is_match": false,
    "confidence": 0.0,
    "match_quality": "false_positive",
    "reasoning": "This excerpt discusses provision II.1.e, not {code}. The matched text appears to be a citation error or formatting issue."
  }}
]
```

**IMPORTANT**:
- Be strict about false positives - if provision numbers don't match, it's FALSE POSITIVE
- "exact" requires both citation AND content match
- "related" means content matches even without citation
- "tangential" means weak connection
- Confidence should reflect certainty of your determination
"""

        return prompt

    def _parse_validation_response(
        self,
        response_text: str,
        candidates: List,
        provision: Dict
    ) -> List[ValidationResult]:
        """
        Parse LLM validation response into ValidationResult objects.

        Args:
            response_text: LLM response text
            candidates: Original candidates
            provision: Provision being validated

        Returns:
            List of ValidationResult objects
        """
        # Extract JSON from response
        json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
        if not json_match:
            # Try without code blocks
            json_match = re.search(r'\[\s*\{.*?\}\s*\]', response_text, re.DOTALL)
            if not json_match:
                logger.warning("Could not find JSON in validation response")
                # Return all candidates as unvalidated
                return [
                    ValidationResult(
                        section=c.section,
                        excerpt=c.excerpt,
                        matched_text=c.matched_text,
                        is_match=True,
                        confidence=c.confidence * 0.7,
                        reasoning="Could not parse validation response",
                        match_quality="unvalidated",
                        original_match_type=c.match_type,
                        original_confidence=c.confidence
                    )
                    for c in candidates
                ]

        try:
            json_text = json_match.group(1) if '```json' in response_text else json_match.group(0)
            validations = json.loads(json_text)

            # Create mapping from candidate number to validation
            validation_map = {
                v.get('candidate_number'): v
                for v in validations
            }

            # Build ValidationResult objects
            results = []
            for i, candidate in enumerate(candidates, 1):
                validation = validation_map.get(i)

                if validation:
                    result = ValidationResult(
                        section=candidate.section,
                        excerpt=candidate.excerpt,
                        matched_text=candidate.matched_text,
                        is_match=validation.get('is_match', False),
                        confidence=validation.get('confidence', 0.0),
                        reasoning=validation.get('reasoning', ''),
                        match_quality=validation.get('match_quality', 'unknown'),
                        original_match_type=candidate.match_type,
                        original_confidence=candidate.confidence
                    )
                else:
                    # No validation found - mark as unvalidated
                    result = ValidationResult(
                        section=candidate.section,
                        excerpt=candidate.excerpt,
                        matched_text=candidate.matched_text,
                        is_match=True,
                        confidence=candidate.confidence * 0.7,
                        reasoning="No validation data returned",
                        match_quality="unvalidated",
                        original_match_type=candidate.match_type,
                        original_confidence=candidate.confidence
                    )

                results.append(result)

                logger.debug(
                    f"Candidate {i}: is_match={result.is_match}, "
                    f"quality={result.match_quality}, confidence={result.confidence}"
                )

            return results

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse validation JSON: {e}")
            # Return all candidates as unvalidated
            return [
                ValidationResult(
                    section=c.section,
                    excerpt=c.excerpt,
                    matched_text=c.matched_text,
                    is_match=True,
                    confidence=c.confidence * 0.7,
                    reasoning=f"JSON parse error: {str(e)}",
                    match_quality="unvalidated",
                    original_match_type=c.match_type,
                    original_confidence=c.confidence
                )
                for c in candidates
            ]

    def get_last_prompt_and_response(self) -> Dict:
        """Return last validation prompt and response for debugging."""
        return {
            'prompt': self.last_validation_prompt,
            'response': self.last_validation_response
        }

    def validate_single(
        self,
        excerpt: str,
        matched_text: str,
        section: str,
        code_provision: str,
        provision_text: str,
        match_type: str,
        match_confidence: float
    ) -> ValidationResult:
        """
        Validate a single excerpt (convenience method).

        Args:
            excerpt: The text excerpt
            matched_text: The citation that was matched
            section: Section name
            code_provision: Code provision number
            provision_text: Provision text
            match_type: Type from pattern matcher
            match_confidence: Confidence from pattern matcher

        Returns:
            ValidationResult object
        """
        # Create mock candidate
        from collections import namedtuple
        Candidate = namedtuple(
            'Candidate',
            ['section', 'excerpt', 'matched_text', 'match_type', 'confidence']
        )

        candidate = Candidate(
            section=section,
            excerpt=excerpt,
            matched_text=matched_text,
            match_type=match_type,
            confidence=match_confidence
        )

        provision = {
            'code_provision': code_provision,
            'provision_text': provision_text
        }

        results = self.validate_batch([candidate], provision)
        return results[0] if results else ValidationResult(
            section=section,
            excerpt=excerpt,
            matched_text=matched_text,
            is_match=False,
            confidence=0.0,
            reasoning="Validation failed",
            match_quality="error",
            original_match_type=match_type,
            original_confidence=match_confidence
        )
