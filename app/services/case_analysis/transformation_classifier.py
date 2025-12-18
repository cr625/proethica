"""
Transformation Classifier Service

Classifies the transformation type of NSPE ethics cases based on
how the ethical situation was resolved.

Transformation Types:
- transfer: Shifts from a scenario set to a new one (obligation moves to another party)
- stalemate: Stakeholders trapped in set of rules (competing obligations remain unresolved)
- oscillation: Stakeholders go to and fro between different sets of rules
- phase_lag: Some stakeholders perform parallel scenarios (delayed consequences emerge)

Reference:
    Marchais-Roubelat, A. and Roubelat, F. (2015), "Designing a moving strategic
    foresight approach: ontological and methodological issues of scenario design",
    Foresight, Vol. 17 No. 6, pp. 545-555. Table II (p. 550) - Steering Rule.
    DOI: 10.1108/FS-12-2014-0085
"""

import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import text
from app import db
from app.models import Document
from app.utils.llm_utils import get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class TransformationResult:
    """Result of transformation classification."""
    transformation_type: str  # 'transfer', 'stalemate', 'oscillation', 'phase_lag', 'unclear'
    confidence: float  # 0.0 to 1.0
    reasoning: str
    pattern_description: str
    supporting_evidence: List[str] = field(default_factory=list)
    alternative_classifications: List[Dict[str, Any]] = field(default_factory=list)


class TransformationClassifier:
    """
    Classifies case transformation type from synthesis data.

    Uses resolution patterns and conclusion analysis to determine
    how the ethical situation was resolved.
    """

    TRANSFORMATION_TYPES = {
        'transfer': {
            'description': 'Resolution transfers obligation/responsibility to another party',
            'indicators': [
                'responsibility transferred',
                'duty passed to',
                'obligation shifted',
                'another party should',
                'client must now',
                'employer takes responsibility'
            ]
        },
        'stalemate': {
            'description': 'Competing obligations remain in tension without clear resolution',
            'indicators': [
                'both obligations valid',
                'competing duties',
                'ethical dilemma remains',
                'no clear resolution',
                'conflict persists',
                'equally compelling'
            ]
        },
        'oscillation': {
            'description': 'Duties shift back and forth between parties over time',
            'indicators': [
                'duty returns to',
                'responsibility cycles',
                'alternating obligation',
                'back and forth',
                'recurring duty',
                'periodic responsibility'
            ]
        },
        'phase_lag': {
            'description': 'Delayed consequences reveal obligations not initially apparent',
            'indicators': [
                'later discovered',
                'subsequently revealed',
                'delayed consequence',
                'hidden defect',
                'future harm',
                'temporal gap'
            ]
        }
    }

    def __init__(self, llm_client=None):
        """
        Initialize the classifier.

        Args:
            llm_client: Optional Anthropic client. If not provided, will create one.
        """
        self._llm_client = llm_client
        self.last_prompt = None
        self.last_response = None

    @property
    def llm_client(self):
        """Lazy-load LLM client."""
        if self._llm_client is None:
            self._llm_client = get_llm_client()
        return self._llm_client

    def classify(
        self,
        case_id: int,
        questions: List[Dict] = None,
        conclusions: List[Dict] = None,
        resolution_patterns: List[Dict] = None,
        use_llm: bool = True,
        case_title: str = None,
        case_facts: str = None,
        all_entities: Dict[str, List] = None
    ) -> TransformationResult:
        """
        Classify transformation type for a case.

        Args:
            case_id: The case ID
            questions: List of question dicts from Step 4
            conclusions: List of conclusion dicts from Step 4
            resolution_patterns: Resolution patterns from synthesis (if available)
            use_llm: Whether to use LLM for classification
            case_title: Optional case title
            case_facts: Optional facts section text for context
            all_entities: Optional dict of entities by type from Passes 1-3

        Returns:
            TransformationResult with type, confidence, and reasoning
        """
        logger.info(f"Classifying transformation for case {case_id}")

        # If data not provided, load from database
        if questions is None or conclusions is None:
            questions, conclusions = self._load_qc_from_db(case_id)

        if resolution_patterns is None:
            resolution_patterns = self._load_resolution_patterns(case_id)

        # Load case facts if not provided
        if case_facts is None:
            case_facts = self._load_case_facts(case_id)

        # Load entities if not provided
        if all_entities is None:
            all_entities = self._load_entities(case_id)

        # First try rule-based classification
        rule_result = self._rule_based_classification(questions, conclusions)

        # If confidence is low or LLM requested, use LLM
        if use_llm and (rule_result.confidence < 0.7 or True):  # Always use LLM for better results
            try:
                llm_result = self._llm_classification(
                    case_id, questions, conclusions, resolution_patterns,
                    case_title, case_facts, all_entities
                )
                # Merge results, preferring LLM if confident
                if llm_result.confidence > rule_result.confidence:
                    return llm_result
                else:
                    # Add LLM as alternative
                    rule_result.alternative_classifications.append({
                        'type': llm_result.transformation_type,
                        'confidence': llm_result.confidence,
                        'source': 'llm'
                    })
                    return rule_result
            except Exception as e:
                logger.warning(f"LLM classification failed, using rule-based: {e}")
                return rule_result

        return rule_result

    def _rule_based_classification(
        self,
        questions: List[Dict],
        conclusions: List[Dict]
    ) -> TransformationResult:
        """
        Rule-based transformation classification using text patterns.

        Args:
            questions: Question data
            conclusions: Conclusion data

        Returns:
            TransformationResult
        """
        # Combine all text for analysis
        all_text = ""
        for q in questions:
            all_text += q.get('entity_definition', '') + " "
        for c in conclusions:
            all_text += c.get('entity_definition', '') + " "
            if c.get('rdf_json_ld'):
                all_text += c['rdf_json_ld'].get('conclusionType', '') + " "

        all_text_lower = all_text.lower()

        # Score each transformation type
        scores = {}
        evidence = {}

        for trans_type, info in self.TRANSFORMATION_TYPES.items():
            score = 0
            found_indicators = []

            for indicator in info['indicators']:
                if indicator in all_text_lower:
                    score += 1
                    found_indicators.append(indicator)

            scores[trans_type] = score
            evidence[trans_type] = found_indicators

        # Find best match
        max_score = max(scores.values()) if scores else 0

        if max_score == 0:
            return TransformationResult(
                transformation_type='unclear',
                confidence=0.3,
                reasoning='No clear transformation indicators found in text',
                pattern_description='Unable to determine transformation pattern',
                supporting_evidence=[]
            )

        # Get type with highest score
        best_type = max(scores, key=scores.get)
        confidence = min(0.4 + (max_score * 0.15), 0.85)

        return TransformationResult(
            transformation_type=best_type,
            confidence=confidence,
            reasoning=f"Rule-based classification found {max_score} indicators for {best_type}",
            pattern_description=self.TRANSFORMATION_TYPES[best_type]['description'],
            supporting_evidence=evidence[best_type],
            alternative_classifications=[
                {'type': t, 'score': s, 'source': 'rule_based'}
                for t, s in scores.items() if s > 0 and t != best_type
            ]
        )

    def _llm_classification(
        self,
        case_id: int,
        questions: List[Dict],
        conclusions: List[Dict],
        resolution_patterns: List[Dict],
        case_title: str = None,
        case_facts: str = None,
        all_entities: Dict[str, List] = None
    ) -> TransformationResult:
        """
        LLM-based transformation classification with full context.

        Args:
            case_id: Case ID
            questions: Question data
            conclusions: Conclusion data
            resolution_patterns: Resolution patterns from synthesis
            case_title: Optional case title (avoids DB lookup)
            case_facts: Facts section text
            all_entities: Entities from Passes 1-3

        Returns:
            TransformationResult
        """
        # Get case title if not provided
        if case_title is None:
            try:
                case = Document.query.get(case_id)
                case_title = case.title if case else f"Case {case_id}"
            except Exception:
                case_title = f"Case {case_id}"

        # Try to get academic framework context
        framework_context = ""
        try:
            from app.academic_references.frameworks.transformation_classification import (
                get_prompt_context, CITATION_SHORT
            )
            framework_context = get_prompt_context(include_examples=True, include_mapping=False)
        except ImportError:
            # Fall back to built-in definitions
            framework_context = self._get_builtin_framework_context()

        # Format questions - handle both data structures
        questions_text = ""
        if questions:
            q_lines = []
            for i, q in enumerate(questions):
                # Try multiple possible keys for the text
                q_text = (q.get('text') or q.get('entity_definition') or
                         q.get('question_text') or q.get('label') or 'No text')
                q_type = q.get('type', q.get('question_type', ''))
                q_lines.append(f"Q{i+1}: {q_text}" + (f" [{q_type}]" if q_type else ""))
            questions_text = "\n".join(q_lines)
        else:
            questions_text = "(No questions extracted)"

        # Format conclusions - handle both data structures
        conclusions_text = ""
        if conclusions:
            c_lines = []
            for i, c in enumerate(conclusions):
                # Try multiple possible keys for the text
                c_text = (c.get('text') or c.get('entity_definition') or
                         c.get('conclusion_text') or c.get('label') or 'No text')
                c_type = c.get('rdf_json_ld', {}).get('conclusionType', '') or c.get('type', '')
                c_lines.append(f"C{i+1}: {c_text}" + (f" [{c_type}]" if c_type else ""))
            conclusions_text = "\n".join(c_lines)
        else:
            conclusions_text = "(No conclusions extracted)"

        # Format resolution patterns if available
        patterns_text = ""
        if resolution_patterns:
            patterns_text = "\n".join([
                f"- {p.get('pattern_type', 'unknown')}: {p.get('resolution_narrative', 'No narrative')}"
                for p in resolution_patterns[:3]
            ])

        # Format key entities for context
        entities_context = ""
        if all_entities:
            entity_parts = []

            # Roles
            roles = all_entities.get('roles', [])
            if roles:
                role_labels = [self._get_entity_label(r) for r in roles[:5]]
                entity_parts.append(f"ROLES: {', '.join(role_labels)}")

            # Obligations
            obligations = all_entities.get('obligations', [])
            if obligations:
                obl_labels = [self._get_entity_label(o) for o in obligations[:5]]
                entity_parts.append(f"OBLIGATIONS: {', '.join(obl_labels)}")

            # Actions
            actions = all_entities.get('actions', [])
            if actions:
                action_labels = [self._get_entity_label(a) for a in actions[:5]]
                entity_parts.append(f"KEY ACTIONS: {', '.join(action_labels)}")

            # Constraints
            constraints = all_entities.get('constraints', [])
            if constraints:
                const_labels = [self._get_entity_label(c) for c in constraints[:3]]
                entity_parts.append(f"CONSTRAINTS: {', '.join(const_labels)}")

            if entity_parts:
                entities_context = "\n".join(entity_parts)

        # Build comprehensive prompt
        prompt = f"""{framework_context}

CASE ANALYSIS: {case_title}

CASE FACTS:
{case_facts[:2000] if case_facts else "(Facts not available - analyze based on questions and conclusions)"}

{f"EXTRACTED ENTITIES:{chr(10)}{entities_context}" if entities_context else ""}

ETHICAL QUESTIONS POSED TO THE BOARD:
{questions_text}

BOARD'S CONCLUSIONS:
{conclusions_text}

{f"RESOLUTION PATTERNS:{chr(10)}{patterns_text}" if patterns_text else ""}

ANALYSIS TASK:
Based on the academic framework above and the case details, classify HOW the ethical situation
was transformed through the Board's resolution. Focus on:
1. How obligations shifted between parties
2. Whether tensions were resolved or remain
3. The temporal pattern of responsibility

Return your analysis as JSON:
{{
    "transformation_type": "transfer|stalemate|oscillation|phase_lag|unclear",
    "confidence": 0.0-1.0,
    "reasoning": "2-3 sentence explanation grounded in the case facts and framework definitions",
    "pattern_description": "Specific description of the transformation pattern in THIS case",
    "supporting_evidence": ["quote or fact 1", "quote or fact 2", "quote or fact 3"],
    "involved_roles": ["role1", "role2"],
    "obligation_shifts": ["description of how obligations moved"]
}}"""

        self.last_prompt = prompt

        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text
            self.last_response = response_text

            # Parse JSON response
            # Handle potential markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            result_data = json.loads(response_text.strip())

            return TransformationResult(
                transformation_type=result_data.get('transformation_type', 'unclear'),
                confidence=float(result_data.get('confidence', 0.5)),
                reasoning=result_data.get('reasoning', ''),
                pattern_description=result_data.get('pattern_description', ''),
                supporting_evidence=result_data.get('supporting_evidence', [])
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"Response was: {self.last_response}")
            raise
        except Exception as e:
            logger.error(f"LLM classification error: {e}")
            raise

    def save_to_features(self, case_id: int, result: TransformationResult) -> bool:
        """
        Save transformation result to case_precedent_features table.

        Args:
            case_id: Case ID
            result: TransformationResult to save

        Returns:
            True if saved successfully
        """
        try:
            # Check if features exist
            check_query = text("""
                SELECT id FROM case_precedent_features WHERE case_id = :case_id
            """)
            existing = db.session.execute(check_query, {'case_id': case_id}).fetchone()

            if existing:
                # Update existing
                update_query = text("""
                    UPDATE case_precedent_features
                    SET transformation_type = :transformation_type,
                        transformation_pattern = :transformation_pattern,
                        extracted_at = CURRENT_TIMESTAMP
                    WHERE case_id = :case_id
                """)
                db.session.execute(update_query, {
                    'case_id': case_id,
                    'transformation_type': result.transformation_type,
                    'transformation_pattern': result.pattern_description
                })
            else:
                # Insert new (minimal record, other fields will be filled by feature extractor)
                insert_query = text("""
                    INSERT INTO case_precedent_features (
                        case_id, transformation_type, transformation_pattern, extracted_at
                    ) VALUES (
                        :case_id, :transformation_type, :transformation_pattern, CURRENT_TIMESTAMP
                    )
                """)
                db.session.execute(insert_query, {
                    'case_id': case_id,
                    'transformation_type': result.transformation_type,
                    'transformation_pattern': result.pattern_description
                })

            db.session.commit()
            logger.info(f"Saved transformation classification for case {case_id}: {result.transformation_type}")
            return True

        except Exception as e:
            logger.error(f"Failed to save transformation for case {case_id}: {e}")
            db.session.rollback()
            return False

    def _load_qc_from_db(self, case_id: int) -> tuple:
        """Load questions and conclusions from database."""
        from app.models import TemporaryRDFStorage

        questions = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_question'
        ).all()

        conclusions = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_conclusion'
        ).all()

        return (
            [{'entity_definition': q.entity_definition, 'rdf_json_ld': q.rdf_json_ld or {}} for q in questions],
            [{'entity_definition': c.entity_definition, 'rdf_json_ld': c.rdf_json_ld or {}} for c in conclusions]
        )

    def _load_resolution_patterns(self, case_id: int) -> List[Dict]:
        """Load resolution patterns from synthesis data if available."""
        from app.models import ExtractionPrompt

        synthesis = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='whole_case_synthesis'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        if synthesis and synthesis.raw_response:
            try:
                data = json.loads(synthesis.raw_response)
                return data.get('resolution_patterns', [])
            except json.JSONDecodeError:
                pass

        return []

    def _load_case_facts(self, case_id: int) -> str:
        """Load case facts section from document."""
        try:
            case = Document.query.get(case_id)
            if case and case.doc_metadata:
                sections = case.doc_metadata.get('sections_dual', {})
                facts_data = sections.get('facts', {})
                if isinstance(facts_data, dict):
                    return facts_data.get('text', '')
                return str(facts_data) if facts_data else ''
        except Exception as e:
            logger.warning(f"Could not load case facts for {case_id}: {e}")
        return ''

    def _load_entities(self, case_id: int) -> Dict[str, List]:
        """Load entities from Passes 1-3."""
        from app.models import TemporaryRDFStorage

        entities = {
            'roles': [],
            'obligations': [],
            'constraints': [],
            'actions': [],
            'principles': [],
            'states': [],
            'resources': []
        }

        # Map extraction types to entity keys
        type_map = {
            'role': 'roles',
            'obligation': 'obligations',
            'constraint': 'constraints',
            'action': 'actions',
            'principle': 'principles',
            'state': 'states',
            'resource': 'resources'
        }

        try:
            all_entities = TemporaryRDFStorage.query.filter_by(
                case_id=case_id
            ).filter(
                TemporaryRDFStorage.extraction_type.in_(type_map.keys())
            ).all()

            for entity in all_entities:
                key = type_map.get(entity.extraction_type)
                if key:
                    entities[key].append({
                        'label': entity.entity_label,
                        'definition': entity.entity_definition,
                        'uri': entity.entity_uri
                    })
        except Exception as e:
            logger.warning(f"Could not load entities for case {case_id}: {e}")

        return entities

    def _get_entity_label(self, entity: Any) -> str:
        """Extract label from entity dict or object."""
        if isinstance(entity, dict):
            return entity.get('label') or entity.get('entity_label') or 'Unknown'
        return getattr(entity, 'entity_label', 'Unknown')

    def _get_builtin_framework_context(self) -> str:
        """Return built-in transformation framework if academic module unavailable."""
        return """TRANSFORMATION CLASSIFICATION FRAMEWORK
Based on: Marchais-Roubelat & Roubelat (2015) Scenario Design Methodology

TRANSFORMATION TYPES:

1. TRANSFER
Definition: Resolution transfers obligation/responsibility to another party.
The ethical obligation moves from one stakeholder to another. The original party
is relieved of the duty, which now falls to a different actor.
Example: Engineer reports to authorities, transferring responsibility to regulatory body.
Indicators: "responsibility transferred", "duty passed to", "now falls to", "referred to"

2. STALEMATE
Definition: Competing obligations remain in tension without clear resolution.
Multiple valid but incompatible obligations exist. The Board may acknowledge this
tension without definitively prioritizing one over another.
Example: Duty to client confidentiality vs. duty to public safety, both valid.
Indicators: "both obligations valid", "competing duties", "tension between", "conflict persists"

3. OSCILLATION
Definition: Duties shift back and forth between parties over time.
Responsibility cycles between parties as circumstances change, often in ongoing
professional relationships.
Example: Design responsibility alternates between engineer and contractor by phase.
Indicators: "responsibility cycles", "alternating obligation", "at different stages"

4. PHASE_LAG
Definition: Delayed consequences reveal obligations not initially apparent.
A temporal gap exists between action and revelation of consequences, creating
retrospective ethical duties.
Example: Defect discovered years after construction creates new obligations.
Indicators: "later discovered", "subsequently revealed", "hidden defect", "years after"
"""
