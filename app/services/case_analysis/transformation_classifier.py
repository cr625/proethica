"""
Step 4 Part F: Transformation Classifier

Classifies the transformation type and symbolic significance of engineering ethics cases.

Theoretical foundation:
- Marchais-Roubelat & Roubelat (2015): Transformation types in action-based scenarios
  (p. 550: "transfer", "stalemate", "oscillation", "phase lag")
- Scenarios as symbols of strategic ethical issues (p. 552)

Transformation types (Marchais-Roubelat & Roubelat 2015, p. 550):
1. Transfer: Clear shift from one rule set to another
   - Example: Case escalates from routine practice to Board review
   - Indicates: Rule transformation, paradigm shift

2. Stalemate: Stakeholders trapped with no clear ethical path forward
   - Example: Engineer cannot verify AI tool AND cannot complete project otherwise
   - Indicates: Structural ethical dilemma, system constraint

3. Oscillation: Cycling between competing obligations repeatedly
   - Example: Between "trust the tool" and "verify independently" with each calculation
   - Indicates: Unresolved normative tension, competing frameworks

4. Phase lag: Different stakeholders operating under different ethical frames simultaneously
   - Example: Client operates under "efficiency" frame while engineer operates under "competence" frame
   - Indicates: Misaligned values, communication failure, frame mismatch

References:
Marchais-Roubelat, A. and Roubelat, F. (2015), "Designing a moving strategic foresight
approach: ontological and methodological issues of scenario design", Foresight,
Vol. 17 No. 6, pp. 545-555.
"""

import logging
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from app.utils.llm_utils import get_llm_client
from app.models import db
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Valid transformation types from Marchais-Roubelat & Roubelat (2015)
TRANSFORMATION_TYPES = ['transfer', 'stalemate', 'oscillation', 'phase_lag']


@dataclass
class PatternTemplate:
    """
    Reusable pattern structure for cross-case comparison.

    Enables precedent discovery based on transformation patterns
    rather than just semantic similarity.
    """
    pattern_id: str
    pattern_name: str
    institutional_tension: str  # e.g., "efficiency_vs_competence"
    typical_transformation: str  # transfer, stalemate, oscillation, phase_lag
    resolution_approaches: List[str]


@dataclass
class TransformationClassification:
    """
    Complete transformation analysis for a case.

    Answers:
    - What transformation type occurred? (transfer/stalemate/oscillation/phase_lag)
    - Why did the NSPE Board publish this case?
    - What strategic ethical issue does it represent?
    - What reusable pattern does this exemplify?
    """
    transformation_type: str  # transfer, stalemate, oscillation, phase_lag
    confidence: float  # 0.0-1.0
    type_rationale: str
    indicators: List[str]  # Evidence for classification

    symbolic_significance: str  # What strategic issue this represents

    pattern_template: Optional[PatternTemplate]
    similar_case_ids: List[int]  # Cases with similar transformation patterns

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        return {
            'transformation_type': self.transformation_type,
            'confidence': self.confidence,
            'type_rationale': self.type_rationale,
            'indicators': self.indicators,
            'symbolic_significance': self.symbolic_significance,
            'pattern_template': {
                'pattern_id': self.pattern_template.pattern_id,
                'pattern_name': self.pattern_template.pattern_name,
                'institutional_tension': self.pattern_template.institutional_tension,
                'typical_transformation': self.pattern_template.typical_transformation,
                'resolution_approaches': self.pattern_template.resolution_approaches
            } if self.pattern_template else None,
            'similar_case_ids': self.similar_case_ids
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'TransformationClassification':
        """
        Reconstruct TransformationClassification from dictionary.

        Args:
            data: Dictionary from to_dict()

        Returns:
            TransformationClassification instance
        """
        # Reconstruct pattern template
        pattern_data = data.get('pattern_template')
        pattern_template = None
        if pattern_data:
            pattern_template = PatternTemplate(
                pattern_id=pattern_data.get('pattern_id', ''),
                pattern_name=pattern_data.get('pattern_name', ''),
                institutional_tension=pattern_data.get('institutional_tension', ''),
                typical_transformation=pattern_data.get('typical_transformation', ''),
                resolution_approaches=pattern_data.get('resolution_approaches', [])
            )

        return cls(
            transformation_type=data.get('transformation_type', ''),
            confidence=data.get('confidence', 0.0),
            type_rationale=data.get('type_rationale', ''),
            indicators=data.get('indicators', []),
            symbolic_significance=data.get('symbolic_significance', ''),
            pattern_template=pattern_template,
            similar_case_ids=data.get('similar_case_ids', [])
        )


class TransformationClassifier:
    """
    Classifies case transformation type and symbolic significance.

    Uses institutional analysis (Part D) and action-rule mapping (Part E)
    to determine the transformation pattern that makes this case significant.
    """

    def __init__(self, llm_client=None):
        """
        Initialize classifier with LLM client.

        Args:
            llm_client: Optional pre-initialized LLM client. If None, will get one via get_llm_client().
                       Pass an existing client when calling from SSE generator to avoid Flask context issues.
        """
        if llm_client is not None:
            self.llm_client = llm_client
        else:
            self.llm_client = get_llm_client()
        logger.info("[Transformation Classifier] Initialized")

    def classify_case(
        self,
        case_id: int,
        institutional_analysis: Dict,
        action_mapping: Dict,
        case_context: Optional[Dict] = None
    ) -> TransformationClassification:
        """
        Classify case transformation type and symbolic significance.

        Args:
            case_id: Case ID
            institutional_analysis: Output from Part D (principle tensions, obligation conflicts)
            action_mapping: Output from Part E (three-rule framework)
            case_context: Optional context (questions, conclusions, board decision)

        Returns:
            TransformationClassification with type, significance, and pattern
        """
        logger.info(f"[Transformation Classifier] Classifying case {case_id}")

        # Build prompt for LLM analysis
        prompt = self._build_classification_prompt(
            institutional_analysis,
            action_mapping,
            case_context
        )

        try:
            # Call LLM with Claude Sonnet 4
            # Using Sonnet 4 - Sonnet 4.5 has consistent timeout issues with complex reasoning tasks
            # See: chapter3_notes.md for detailed analysis of this model selection
            logger.info("[Transformation Classifier] Calling LLM for transformation classification...")
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = response.content[0].text
            logger.debug(f"[Transformation Classifier] Response length: {len(response_text)} chars")

            # Store prompt and response for SSE streaming display
            self.last_prompt = prompt
            self.last_response = response_text

            # Extract JSON from response (may be wrapped in markdown code blocks)
            json_text = self._extract_json_from_response(response_text)

            # Parse JSON response
            classification_data = json.loads(json_text)

            # Build TransformationClassification object
            classification = self._parse_classification_response(classification_data)

            logger.info(f"[Transformation Classifier] Classification complete:")
            logger.info(f"  - Type: {classification.transformation_type}")
            logger.info(f"  - Confidence: {classification.confidence}")
            logger.info(f"  - Pattern: {classification.pattern_template.pattern_id if classification.pattern_template else 'None'}")

            return classification

        except json.JSONDecodeError as e:
            logger.error(f"[Transformation Classifier] Failed to parse LLM JSON: {e}")
            logger.debug(f"Raw response: {response_text[:500]}...")
            raise
        except Exception as e:
            logger.error(f"[Transformation Classifier] Classification error: {e}")
            raise

    def save_to_database(
        self,
        case_id: int,
        classification: TransformationClassification,
        llm_model: str = "claude-sonnet-4-20250514"
    ) -> bool:
        """
        Save transformation classification to database.

        Args:
            case_id: Case ID
            classification: TransformationClassification result
            llm_model: LLM model used

        Returns:
            True if successful
        """
        try:
            # Delete existing classification
            delete_query = text("""
                DELETE FROM case_transformation WHERE case_id = :case_id
            """)
            db.session.execute(delete_query, {'case_id': case_id})

            # Insert new classification
            insert_query = text("""
                INSERT INTO case_transformation (
                    case_id, transformation_type, confidence,
                    type_rationale, indicators, symbolic_significance,
                    pattern_id, pattern_name, institutional_tension,
                    typical_transformation, resolution_approaches,
                    similar_case_ids, llm_model, llm_prompt, llm_response
                ) VALUES (
                    :case_id, :transformation_type, :confidence,
                    :type_rationale, :indicators, :symbolic_significance,
                    :pattern_id, :pattern_name, :institutional_tension,
                    :typical_transformation, :resolution_approaches,
                    :similar_case_ids, :llm_model, :llm_prompt, :llm_response
                )
            """)

            # Extract pattern data
            pattern = classification.pattern_template
            pattern_id = pattern.pattern_id if pattern else None
            pattern_name = pattern.pattern_name if pattern else None
            institutional_tension = pattern.institutional_tension if pattern else None
            typical_transformation = pattern.typical_transformation if pattern else None
            resolution_approaches = pattern.resolution_approaches if pattern else []

            db.session.execute(insert_query, {
                'case_id': case_id,
                'transformation_type': classification.transformation_type,
                'confidence': classification.confidence,
                'type_rationale': classification.type_rationale,
                'indicators': json.dumps(classification.indicators),
                'symbolic_significance': classification.symbolic_significance,
                'pattern_id': pattern_id,
                'pattern_name': pattern_name,
                'institutional_tension': institutional_tension,
                'typical_transformation': typical_transformation,
                'resolution_approaches': json.dumps(resolution_approaches),
                'similar_case_ids': classification.similar_case_ids,
                'llm_model': llm_model,
                'llm_prompt': getattr(self, 'last_prompt', ''),
                'llm_response': getattr(self, 'last_response', '')
            })

            db.session.commit()

            logger.info(f"[Transformation Classifier] Saved classification to database for case {case_id}")
            return True

        except Exception as e:
            logger.error(f"[Transformation Classifier] Database save error: {e}")
            db.session.rollback()
            raise

    def _build_classification_prompt(
        self,
        institutional_analysis: Dict,
        action_mapping: Dict,
        case_context: Optional[Dict]
    ) -> str:
        """Build LLM prompt for transformation classification."""

        # Extract key data from previous analyses
        principle_tensions = institutional_analysis.get('principle_tensions', [])
        obligation_conflicts = institutional_analysis.get('obligation_conflicts', [])
        case_significance = institutional_analysis.get('case_significance', '')

        transformation_points = action_mapping.get('steering_rule', {}).get('transformation_points', [])
        rule_shifts = action_mapping.get('steering_rule', {}).get('rule_shifts', [])
        overall_analysis = action_mapping.get('overall_analysis', '')

        prompt = f"""Classify the transformation type for this professional engineering ethics case.

**Context**: NSPE Board of Ethical Review case - determine what transformation pattern makes this case ethically significant.

**Previous Analysis Results**:

**Institutional Analysis** (Part D):
- Case Significance: {case_significance}
- Principle Tensions: {len(principle_tensions)} identified
- Obligation Conflicts: {len(obligation_conflicts)} identified

**Action-Rule Mapping** (Part E - Steering Rule):
- Transformation Points: {json.dumps(transformation_points, indent=2)}
- Rule Shifts: {json.dumps(rule_shifts, indent=2)}
- Overall Analysis: {overall_analysis}

**Task**: Classify the transformation type using the framework from Marchais-Roubelat & Roubelat (2015).

**Transformation Types** (Marchais-Roubelat & Roubelat 2015, p. 550):

1. **transfer**: Clear shift from one rule set to another
   - Example: Case escalates from routine practice to Board review
   - Indicators: Paradigm shift, rule transformation, new ethical frame activated

2. **stalemate**: Stakeholders trapped with no clear ethical path forward
   - Example: Cannot verify AI tool AND cannot complete project otherwise
   - Indicators: Structural dilemma, no acceptable option, decision paralysis

3. **oscillation**: Cycling between competing obligations repeatedly
   - Example: Between "trust tool" and "verify independently" with each calculation
   - Indicators: Unresolved tension, repeated back-and-forth, no stable resolution

4. **phase_lag**: Different stakeholders operating under different ethical frames simultaneously
   - Example: Client operates under "efficiency" frame while engineer operates under "competence" frame
   - Indicators: Misaligned values, frame mismatch, talking past each other

**Analysis Questions**:
1. Which transformation type best describes this case?
2. What evidence supports this classification?
3. Why did the NSPE Board publish this case? What strategic ethical issue does it represent?
4. What reusable pattern does this exemplify for cross-case comparison?

**Output Format** (JSON only, no markdown):
{{
  "transformation_type": "transfer|stalemate|oscillation|phase_lag",
  "confidence": 0.85,
  "type_rationale": "2-3 sentence explanation of why this classification fits",
  "indicators": [
    "Specific evidence from the case supporting this classification",
    "Another indicator",
    "Another indicator"
  ],
  "symbolic_significance": "What strategic ethical issue this case represents for the profession. Why did NSPE publish it?",
  "pattern_template": {{
    "pattern_id": "snake_case_pattern_id",
    "pattern_name": "Human Readable Pattern Name",
    "institutional_tension": "key_tension (e.g., efficiency_vs_competence)",
    "typical_transformation": "transfer|stalemate|oscillation|phase_lag",
    "resolution_approaches": [
      "How this type of case is typically resolved",
      "Another resolution approach",
      "Another resolution approach"
    ]
  }}
}}

**Important**:
- Use EXACTLY one of these transformation_type values: "transfer", "stalemate", "oscillation", "phase_lag"
- Confidence should be 0.0-1.0
- Focus on what makes this case strategically significant for professional ethics
- Pattern template enables cross-case comparison and precedent discovery

Respond with valid JSON only."""

        return prompt

    def _parse_classification_response(self, data: Dict) -> TransformationClassification:
        """Parse LLM JSON response into TransformationClassification object."""

        # Validate transformation type
        transformation_type = data.get('transformation_type', '')
        if transformation_type not in TRANSFORMATION_TYPES:
            logger.warning(f"[Transformation Classifier] Invalid transformation type: {transformation_type}")
            # Default to transfer if invalid
            transformation_type = 'transfer'

        # Parse pattern template
        pattern_data = data.get('pattern_template')
        pattern_template = None
        if pattern_data:
            pattern_template = PatternTemplate(
                pattern_id=pattern_data.get('pattern_id', ''),
                pattern_name=pattern_data.get('pattern_name', ''),
                institutional_tension=pattern_data.get('institutional_tension', ''),
                typical_transformation=pattern_data.get('typical_transformation', transformation_type),
                resolution_approaches=pattern_data.get('resolution_approaches', [])
            )

        return TransformationClassification(
            transformation_type=transformation_type,
            confidence=float(data.get('confidence', 0.0)),
            type_rationale=data.get('type_rationale', ''),
            indicators=data.get('indicators', []),
            symbolic_significance=data.get('symbolic_significance', ''),
            pattern_template=pattern_template,
            similar_case_ids=data.get('similar_case_ids', [])
        )

    def _extract_json_from_response(self, response_text: str) -> str:
        """
        Extract JSON from LLM response, handling markdown code blocks.

        Args:
            response_text: Raw LLM response text

        Returns:
            Extracted JSON string
        """
        import re

        # Try to find JSON in markdown code blocks first
        json_match = re.search(r'```json\s*\n(.*?)\n```', response_text, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()

        # Try generic code block
        code_match = re.search(r'```\s*\n(.*?)\n```', response_text, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # Try to find JSON object directly (starts with { and ends with })
        json_obj_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_obj_match:
            return json_obj_match.group(0).strip()

        # If all else fails, return the original text and let json.loads fail with a better error
        logger.warning("[Transformation Classifier] Could not extract JSON from response, trying raw text")
        return response_text.strip()
