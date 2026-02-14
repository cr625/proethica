"""
Case Feature Extractor for Precedent Discovery

Extracts structured features from NSPE cases at ingestion time
for efficient precedent matching.

References:
- CBR-RAG (Wiratunga et al., 2024): https://aclanthology.org/2024.lrec-main.939/
  Hybrid similarity with intra/inter embeddings
- NS-LCR (Sun et al., 2024): https://aclanthology.org/2024.lrec-main.939/
  Logic rules for explainable case matching
"""

import re
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import text
from app import db
from app.models import Document
from app.models.document_section import DocumentSection
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

# =============================================================================
# Nine-Component Embedding Aggregation Constants
# =============================================================================
# Maps database extraction_type values to canonical component codes.
# These codes correspond to the ProEthica nine-component framework:
#   R=Roles, S=States, Rs=Resources, P=Principles, O=Obligations,
#   Cs=Constraints, Ca=Capabilities, A=Actions, E=Events
#
# See: proethica/docs/concepts/nine-components.md for full definitions
# =============================================================================

EXTRACTION_TYPE_TO_COMPONENT = {
    'roles': 'R',
    'states': 'S',
    'resources': 'Rs',
    'principles': 'P',
    'obligations': 'O',
    'constraints': 'Cs',
    'capabilities': 'Ca',
    # Note: Actions and Events use temporal_dynamics_enhanced + entity_type
}

# For temporal_dynamics_enhanced, map entity_type to component code
ENTITY_TYPE_TO_COMPONENT = {
    'actions': 'A',
    'events': 'E',
}

# Weights for component aggregation based on ethical reasoning importance
# Sum = 1.0 for proper normalization
COMPONENT_WEIGHTS = {
    'R': 0.12,   # Roles - professional positions determine applicable norms
    'S': 0.10,   # States - situational context affects ethical assessment
    'Rs': 0.10,  # Resources - accumulated knowledge and precedents
    'P': 0.20,   # Principles - highest weight, core ethical reasoning
    'O': 0.15,   # Obligations - specific requirements for action
    'Cs': 0.08,  # Constraints - inviolable boundaries
    'Ca': 0.07,  # Capabilities - competencies and permissions
    'A': 0.10,   # Actions - volitional interventions
    'E': 0.08,   # Events - external occurrences
}


@dataclass
class ExtractedFeatures:
    """Container for extracted precedent features."""
    case_id: int
    outcome_type: str  # 'ethical', 'unethical', 'mixed', 'unclear'
    outcome_confidence: float
    outcome_reasoning: str
    provisions_cited: List[str] = field(default_factory=list)
    subject_tags: List[str] = field(default_factory=list)
    principle_tensions: List[Dict] = field(default_factory=list)
    obligation_conflicts: List[Dict] = field(default_factory=list)
    transformation_type: Optional[str] = None
    transformation_pattern: Optional[str] = None
    facts_embedding: Optional[List[float]] = None
    discussion_embedding: Optional[List[float]] = None
    conclusion_embedding: Optional[List[float]] = None
    combined_embedding: Optional[List[float]] = None
    extraction_method: str = 'automatic'


class CaseFeatureExtractor:
    """
    Extracts precedent-relevant features from NSPE cases.

    Features extracted:
    - Outcome classification (ethical/unethical/mixed)
    - NSPE Code provision references
    - Subject tags
    - Principle tensions (from Step 4)
    - Obligation conflicts (from Step 4)
    - Transformation type (from Step 4)
    - Section-level embeddings
    """

    # Patterns for outcome extraction from conclusions
    OUTCOME_PATTERNS = [
        # Clear ethical/unethical patterns
        (r'\b(was|is|would be)\s+(not\s+)?(un)?ethical\b', 'ethical_statement'),
        (r'\b(violat|does not violate|did not violate)\w*\b', 'violation_statement'),
        (r'\bin\s+(?:accordance|compliance)\s+with\b', 'compliance_statement'),
        (r'\b(conflicts?|conflict(?:ed|ing)?)\s+with\b', 'conflict_statement'),
        (r'\b(proper|improper)\s+for\b', 'propriety_statement'),
    ]

    # NSPE Code provision pattern
    # Matches: I.1, II.1.a, III.2.b, II.4.a, etc.
    PROVISION_PATTERN = re.compile(
        r'\b(I{1,3}|IV)\s*\.\s*(\d+)\s*(?:\.\s*([a-z]))?\.?\b',
        re.IGNORECASE
    )

    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        """
        Initialize the feature extractor.

        Args:
            embedding_service: Optional embedding service instance.
                              If not provided, will create one.
        """
        self._embedding_service = embedding_service

    @property
    def embedding_service(self) -> EmbeddingService:
        """Lazy-load embedding service."""
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService.get_instance()
        return self._embedding_service

    def extract_precedent_features(self, case_id: int) -> ExtractedFeatures:
        """
        Extract all precedent-relevant features from a case.

        Args:
            case_id: Database ID of the case document

        Returns:
            ExtractedFeatures object with all extracted data
        """
        logger.info(f"Extracting precedent features for case {case_id}")

        # Get the document
        document = Document.query.get(case_id)
        if not document:
            raise ValueError(f"Document with ID {case_id} not found")

        # Get document sections
        sections = self._get_document_sections(case_id)

        # Get metadata
        metadata = document.doc_metadata or {}
        doc_structure = metadata.get('document_structure', {})
        doc_sections = doc_structure.get('sections', {})

        # Extract outcome from conclusion
        conclusion_text = self._get_section_text(sections, doc_sections, 'conclusion')
        outcome_type, outcome_confidence, outcome_reasoning = self.extract_outcome(
            conclusion_text
        )

        # Extract provisions from references section
        references_text = self._get_section_text(sections, doc_sections, 'references')
        provisions_cited = self.extract_provisions(references_text)

        # Get subject tags from metadata
        subject_tags = metadata.get('subject_tags', [])
        if not subject_tags:
            subject_tags = doc_structure.get('subject_tags', [])

        # Get Step 4 analysis data
        principle_tensions, obligation_conflicts, transformation_type, transformation_pattern = \
            self._get_step4_data(case_id)

        # Generate embeddings
        embeddings = self.generate_hierarchical_embeddings(case_id, sections, doc_sections)

        features = ExtractedFeatures(
            case_id=case_id,
            outcome_type=outcome_type,
            outcome_confidence=outcome_confidence,
            outcome_reasoning=outcome_reasoning,
            provisions_cited=provisions_cited,
            subject_tags=subject_tags,
            principle_tensions=principle_tensions,
            obligation_conflicts=obligation_conflicts,
            transformation_type=transformation_type,
            transformation_pattern=transformation_pattern,
            facts_embedding=embeddings.get('facts'),
            discussion_embedding=embeddings.get('discussion'),
            conclusion_embedding=embeddings.get('conclusion'),
            combined_embedding=embeddings.get('combined'),
            extraction_method='automatic'
        )

        logger.info(
            f"Extracted features for case {case_id}: "
            f"outcome={outcome_type}, provisions={len(provisions_cited)}, "
            f"tags={len(subject_tags)}"
        )

        return features

    def extract_outcome(self, conclusion_text: str) -> Tuple[str, float, str]:
        """
        Extract outcome classification from conclusion text.

        Args:
            conclusion_text: The conclusion section text

        Returns:
            Tuple of (outcome_type, confidence, reasoning)
        """
        if not conclusion_text:
            return 'unclear', 0.0, 'No conclusion text available'

        conclusion_lower = conclusion_text.lower()

        # Check for clear ethical/unethical statements
        ethical_indicators = []
        unethical_indicators = []

        # Pattern: "was/is/would be ethical" (positive) vs negated forms
        # Must check "not ethical" before "ethical" to avoid false positives
        if re.search(r'\b(was|is|would be|were)\s+not\s+ethical\b', conclusion_lower):
            unethical_indicators.append('was not ethical statement')
        elif re.search(r'\b(was|is|would be|were)\s+ethical\b', conclusion_lower):
            ethical_indicators.append('explicit ethical statement')

        # Pattern: "unethical" explicitly
        if re.search(r'\bunethical\b', conclusion_lower):
            unethical_indicators.append('explicit unethical statement')

        # Pattern: "did not violate" / "does not violate" vs "violates"
        if re.search(r'\b(did|does|do)\s+not\s+violate\b', conclusion_lower):
            ethical_indicators.append('does not violate')
        elif re.search(r'\bviolat(es?|ed|ing)\b', conclusion_lower):
            unethical_indicators.append('violates code')

        # Pattern: "in accordance with" vs "conflicts with"
        if re.search(r'\bin\s+(?:accordance|compliance)\s+with\b', conclusion_lower):
            ethical_indicators.append('in accordance with code')
        if re.search(r'\bconflicts?\s+with\b', conclusion_lower):
            unethical_indicators.append('conflicts with code')

        # Pattern: "proper" vs "improper" or "not proper"
        if re.search(r'\bimproper\b', conclusion_lower):
            unethical_indicators.append('improper conduct')
        elif re.search(r'\bnot\s+proper\b', conclusion_lower):
            unethical_indicators.append('not proper conduct')
        elif re.search(r'\bproper\s+(for|to|conduct)\b', conclusion_lower):
            ethical_indicators.append('proper conduct')

        # Determine outcome
        ethical_score = len(ethical_indicators)
        unethical_score = len(unethical_indicators)

        if ethical_score > 0 and unethical_score == 0:
            outcome_type = 'ethical'
            confidence = min(0.5 + (ethical_score * 0.15), 0.95)
            reasoning = f"Ethical indicators: {', '.join(ethical_indicators)}"
        elif unethical_score > 0 and ethical_score == 0:
            outcome_type = 'unethical'
            confidence = min(0.5 + (unethical_score * 0.15), 0.95)
            reasoning = f"Unethical indicators: {', '.join(unethical_indicators)}"
        elif ethical_score > 0 and unethical_score > 0:
            outcome_type = 'mixed'
            confidence = 0.6
            reasoning = (
                f"Mixed indicators - Ethical: {', '.join(ethical_indicators)}; "
                f"Unethical: {', '.join(unethical_indicators)}"
            )
        else:
            outcome_type = 'unclear'
            confidence = 0.3
            reasoning = 'No clear outcome indicators found'

        return outcome_type, confidence, reasoning

    def extract_provisions(self, references_text: str) -> List[str]:
        """
        Extract NSPE Code provision references from text.

        Args:
            references_text: The references section text

        Returns:
            List of provision identifiers (e.g., ['I.1', 'II.1.a'])
        """
        if not references_text:
            return []

        provisions = set()

        # Find all provision matches
        for match in self.PROVISION_PATTERN.finditer(references_text):
            roman = match.group(1).upper()
            number = match.group(2)
            letter = match.group(3).lower() if match.group(3) else None

            if letter:
                provision = f"{roman}.{number}.{letter}"
            else:
                provision = f"{roman}.{number}"

            provisions.add(provision)

        # Sort provisions in a logical order
        def provision_sort_key(p):
            parts = p.split('.')
            roman_order = {'I': 1, 'II': 2, 'III': 3, 'IV': 4}
            roman = roman_order.get(parts[0], 0)
            number = int(parts[1]) if len(parts) > 1 else 0
            letter = ord(parts[2]) - ord('a') if len(parts) > 2 else 0
            return (roman, number, letter)

        return sorted(list(provisions), key=provision_sort_key)

    def llm_extract_features(self, discussion_text: str, conclusion_text: str) -> dict:
        """
        Extract provisions, outcome, and subject tags using Claude API.

        Uses Haiku for cost-efficient structured extraction from case text.
        Identifies NSPE Code provisions even when not explicitly cited by number.

        Args:
            discussion_text: The discussion section text
            conclusion_text: The conclusion section text

        Returns:
            Dict with keys: provisions_cited, outcome_type, outcome_reasoning, subject_tags
        """
        from app.services.llm.manager import LLMManager
        from app.data.nspe_provisions_reference import NSPE_PROVISIONS_TEXT, NSPE_TAG_VOCABULARY
        from app.utils.llm_utils import extract_json_from_response

        llm = LLMManager(model="claude-haiku-4-5-20251001")

        tag_list = '\n'.join(f'- {t}' for t in NSPE_TAG_VOCABULARY)

        system_prompt = f"""You are analyzing an NSPE Board of Ethical Review case. Extract structured data from the case discussion and conclusion.

NSPE Code of Ethics provisions:
{NSPE_PROVISIONS_TEXT}

Available subject tags (use ONLY these exact labels):
{tag_list}

Extract three things:

1. provisions_cited: Which NSPE Code provisions are discussed, applied, or relevant to this case. Use the code format (e.g., "I.1", "II.3.a", "III.4"). Include provisions that are explicitly cited AND provisions that are implicitly referenced through discussion of the ethical duties they describe.

2. outcome_type: The Board's ethical determination about the engineer's conduct. Must be exactly one of: "ethical", "unethical", "mixed". Base this on the Board's conclusion about whether the conduct was ethical or not. If the Board finds the conduct acceptable or not in violation, classify as "ethical". If the Board finds the conduct unacceptable or in violation, classify as "unethical". If the Board addresses multiple questions with different determinations, classify as "mixed".

3. subject_tags: Which subject categories from the vocabulary above apply to this case. Select all that are relevant.

Return ONLY valid JSON in this format:
{{"provisions_cited": ["I.1", "II.3.a"], "outcome_type": "unethical", "outcome_reasoning": "one sentence explanation", "subject_tags": ["Duty to the Public", "Competence"]}}"""

        user_msg = ""
        if discussion_text:
            user_msg += f"Discussion:\n{discussion_text[:3000]}\n\n"
        if conclusion_text:
            user_msg += f"Conclusion:\n{conclusion_text[:1500]}"

        if not user_msg.strip():
            return {
                'provisions_cited': [],
                'outcome_type': 'unclear',
                'outcome_reasoning': 'No discussion or conclusion text available',
                'subject_tags': [],
            }

        response = llm.complete(
            messages=[{"role": "user", "content": user_msg}],
            system=system_prompt,
            max_tokens=500,
            temperature=0.0,
        )

        result = extract_json_from_response(response.text)

        # Validate and normalize provisions
        valid_provisions = []
        provision_pattern = re.compile(r'^(I{1,3}|IV)\.\d+(\.[a-z])?$')
        for p in result.get('provisions_cited', []):
            if provision_pattern.match(p):
                valid_provisions.append(p)
        result['provisions_cited'] = valid_provisions

        # Validate outcome
        if result.get('outcome_type') not in ('ethical', 'unethical', 'mixed'):
            result['outcome_type'] = 'unclear'

        # Validate tags against vocabulary
        tag_set = set(NSPE_TAG_VOCABULARY)
        result['subject_tags'] = [t for t in result.get('subject_tags', []) if t in tag_set]

        return result

    def generate_hierarchical_embeddings(
        self,
        case_id: int,
        sections: Dict[str, DocumentSection],
        doc_sections: Dict
    ) -> Dict[str, List[float]]:
        """
        Generate embeddings at section and combined levels.

        Uses hierarchical approach from CBR-RAG:
        - Section-level embeddings for fine-grained matching
        - Combined embedding for overall case similarity

        Args:
            case_id: The case ID
            sections: DocumentSection records by type
            doc_sections: Section data from document metadata

        Returns:
            Dict with 'facts', 'discussion', 'conclusion', 'combined' embeddings
        """
        embeddings = {}

        # Get text for each section
        facts_text = self._get_section_text(sections, doc_sections, 'facts')
        discussion_text = self._get_section_text(sections, doc_sections, 'discussion')
        conclusion_text = self._get_section_text(sections, doc_sections, 'conclusion')

        # Generate section embeddings
        if facts_text:
            embeddings['facts'] = self.embedding_service.get_embedding(facts_text)

        if discussion_text:
            embeddings['discussion'] = self.embedding_service.get_embedding(discussion_text)

        if conclusion_text:
            embeddings['conclusion'] = self.embedding_service.get_embedding(conclusion_text)

        # Generate combined embedding
        # Weight: facts (0.3), discussion (0.5), conclusion (0.2)
        combined_text = f"{facts_text or ''}\n\n{discussion_text or ''}\n\n{conclusion_text or ''}"
        if combined_text.strip():
            embeddings['combined'] = self.embedding_service.get_embedding(combined_text)

        return embeddings

    def save_features(self, features: ExtractedFeatures) -> int:
        """
        Save extracted features to the database.

        Args:
            features: ExtractedFeatures object

        Returns:
            ID of the saved record
        """
        # Convert embeddings to format suitable for pgvector
        # Database expects 384-dim vectors (local model)
        EXPECTED_DIM = 384

        def format_embedding(emb):
            if emb is None:
                return None
            if isinstance(emb, np.ndarray):
                emb = emb.tolist()
            # Skip embeddings with wrong dimension
            if isinstance(emb, list) and len(emb) != EXPECTED_DIM:
                logger.warning(f"Skipping embedding with dimension {len(emb)}, expected {EXPECTED_DIM}")
                return None
            return emb

        query = text("""
            INSERT INTO case_precedent_features (
                case_id,
                outcome_type,
                outcome_confidence,
                outcome_reasoning,
                provisions_cited,
                provision_count,
                subject_tags,
                principle_tensions,
                obligation_conflicts,
                transformation_type,
                transformation_pattern,
                facts_embedding,
                discussion_embedding,
                conclusion_embedding,
                combined_embedding,
                extraction_method,
                extracted_at
            ) VALUES (
                :case_id,
                :outcome_type,
                :outcome_confidence,
                :outcome_reasoning,
                :provisions_cited,
                :provision_count,
                :subject_tags,
                :principle_tensions,
                :obligation_conflicts,
                :transformation_type,
                :transformation_pattern,
                :facts_embedding,
                :discussion_embedding,
                :conclusion_embedding,
                :combined_embedding,
                :extraction_method,
                :extracted_at
            )
            ON CONFLICT (case_id) DO UPDATE SET
                outcome_type = EXCLUDED.outcome_type,
                outcome_confidence = EXCLUDED.outcome_confidence,
                outcome_reasoning = EXCLUDED.outcome_reasoning,
                provisions_cited = EXCLUDED.provisions_cited,
                provision_count = EXCLUDED.provision_count,
                subject_tags = EXCLUDED.subject_tags,
                principle_tensions = EXCLUDED.principle_tensions,
                obligation_conflicts = EXCLUDED.obligation_conflicts,
                transformation_type = EXCLUDED.transformation_type,
                transformation_pattern = EXCLUDED.transformation_pattern,
                facts_embedding = EXCLUDED.facts_embedding,
                discussion_embedding = EXCLUDED.discussion_embedding,
                conclusion_embedding = EXCLUDED.conclusion_embedding,
                combined_embedding = EXCLUDED.combined_embedding,
                extraction_method = EXCLUDED.extraction_method,
                extracted_at = EXCLUDED.extracted_at
            RETURNING id
        """)

        import json

        # Skip embeddings for now - we use document_sections embeddings for similarity
        # The EmbeddingService returns 1536-dim (OpenAI) but DB expects 384-dim (local)
        # TODO: Fix embedding dimension consistency across services

        result = db.session.execute(query, {
            'case_id': features.case_id,
            'outcome_type': features.outcome_type,
            'outcome_confidence': features.outcome_confidence,
            'outcome_reasoning': features.outcome_reasoning,
            'provisions_cited': features.provisions_cited,
            'provision_count': len(features.provisions_cited),
            'subject_tags': features.subject_tags,
            'principle_tensions': json.dumps(features.principle_tensions) if features.principle_tensions else None,
            'obligation_conflicts': json.dumps(features.obligation_conflicts) if features.obligation_conflicts else None,
            'transformation_type': features.transformation_type,
            'transformation_pattern': features.transformation_pattern,
            'facts_embedding': None,  # Using document_sections embeddings instead
            'discussion_embedding': None,
            'conclusion_embedding': None,
            'combined_embedding': None,
            'extraction_method': features.extraction_method,
            'extracted_at': datetime.utcnow()
        })

        db.session.commit()

        row = result.fetchone()
        return row[0] if row else None

    def extract_and_save_all_cases(self) -> Dict[int, bool]:
        """
        Extract and save features for all cases in the database.

        Returns:
            Dict mapping case_id to success status
        """
        results = {}

        # Get all case documents
        cases = Document.query.filter(
            Document.document_type.in_(['case', 'case_study'])
        ).all()

        logger.info(f"Processing {len(cases)} cases for feature extraction")

        for case in cases:
            try:
                features = self.extract_precedent_features(case.id)
                self.save_features(features)
                results[case.id] = True
                logger.info(f"Successfully processed case {case.id}: {case.title[:50]}...")
            except Exception as e:
                logger.error(f"Error processing case {case.id}: {e}")
                results[case.id] = False

        success_count = sum(1 for v in results.values() if v)
        logger.info(f"Feature extraction complete: {success_count}/{len(cases)} successful")

        return results

    def _get_document_sections(self, case_id: int) -> Dict[str, DocumentSection]:
        """Get DocumentSection records for a case, indexed by section_type."""
        sections = DocumentSection.query.filter_by(document_id=case_id).all()
        return {s.section_type: s for s in sections}

    def _get_section_text(
        self,
        sections: Dict[str, DocumentSection],
        doc_sections: Dict,
        section_type: str
    ) -> str:
        """
        Get text content for a section, preferring DocumentSection over metadata.

        Args:
            sections: Dict of DocumentSection records
            doc_sections: Section data from document metadata
            section_type: The section type to retrieve

        Returns:
            Section text content
        """
        # Try DocumentSection first
        if section_type in sections:
            return sections[section_type].content or ''

        # Fall back to metadata
        if section_type in doc_sections:
            section_data = doc_sections[section_type]
            if isinstance(section_data, dict):
                return section_data.get('content', '')
            return str(section_data)

        return ''

    def _get_step4_data(self, case_id: int) -> Tuple[List[Dict], List[Dict], Optional[str], Optional[str]]:
        """
        Get Step 4 analysis data for a case.

        Returns:
            Tuple of (principle_tensions, obligation_conflicts, transformation_type, transformation_pattern)
        """
        principle_tensions = []
        obligation_conflicts = []
        transformation_type = None
        transformation_pattern = None

        try:
            # Get institutional analysis (principle tensions, obligation conflicts)
            inst_query = text("""
                SELECT
                    principle_tensions,
                    obligation_conflicts
                FROM case_institutional_analysis
                WHERE case_id = :case_id
                ORDER BY created_at DESC
                LIMIT 1
            """)
            result = db.session.execute(inst_query, {'case_id': case_id}).fetchone()

            if result:
                if result[0]:  # principle_tensions
                    import json
                    principle_tensions = json.loads(result[0]) if isinstance(result[0], str) else result[0]
                if result[1]:  # obligation_conflicts
                    import json
                    obligation_conflicts = json.loads(result[1]) if isinstance(result[1], str) else result[1]

            # Get transformation classification
            trans_query = text("""
                SELECT
                    transformation_type,
                    pattern_name
                FROM case_transformation
                WHERE case_id = :case_id
                ORDER BY created_at DESC
                LIMIT 1
            """)
            result = db.session.execute(trans_query, {'case_id': case_id}).fetchone()

            if result:
                transformation_type = result[0]
                transformation_pattern = result[1]

        except Exception as e:
            logger.warning(f"Could not retrieve Step 4 data for case {case_id}: {e}")

        return principle_tensions, obligation_conflicts, transformation_type, transformation_pattern

    # =========================================================================
    # Component-Level Embedding Aggregation
    # =========================================================================

    def _get_local_embedding(self, text: str) -> np.ndarray:
        """
        Get a 384-dimensional embedding using the local SentenceTransformer model.

        Forces local model usage to ensure consistent 384-dim embeddings for
        pgvector storage, bypassing the EmbeddingService provider priority.

        Args:
            text: Text to embed

        Returns:
            numpy array of shape (384,)
        """
        if not text or not text.strip():
            return np.zeros(384)

        # Access the local model directly from the embedding service
        embedding_service = self.embedding_service
        if 'local' not in embedding_service.providers:
            raise RuntimeError("Local embedding provider not available")

        local_provider = embedding_service.providers['local']
        if not local_provider.get('available'):
            raise RuntimeError(
                f"Local embedding provider not available: {local_provider.get('reason')}"
            )

        model = local_provider['model']
        embedding = model.encode(text)

        # Ensure it's a numpy array
        if not isinstance(embedding, np.ndarray):
            embedding = np.array(embedding)

        return embedding

    def generate_component_aggregated_embedding(
        self,
        case_id: int,
        min_components: int = 3,
        weights: Optional[Dict[str, float]] = None
    ) -> Optional[Tuple[np.ndarray, Dict[str, np.ndarray]]]:
        """
        Generate per-component embeddings and their weighted aggregation.

        Queries the nine-component entities from temporary_rdf_storage,
        generates embeddings for each component type, and aggregates them
        using configurable weights.

        Args:
            case_id: Database ID of the case document
            min_components: Minimum number of component types required (default: 3)
            weights: Optional custom weights dict. If None, uses COMPONENT_WEIGHTS.

        Returns:
            Tuple of (L2-normalized aggregated 384-dim array, dict of per-component
            L2-normalized 384-dim arrays), or None if insufficient components.
        """
        if weights is None:
            weights = COMPONENT_WEIGHTS

        # Query all entities for this case from temporary_rdf_storage
        entities = TemporaryRDFStorage.query.filter_by(case_id=case_id).all()

        if not entities:
            logger.warning(f"Case {case_id}: No components found in temporary_rdf_storage")
            return None

        # Group entities by component type
        # IMPORTANT: Handle temporal_dynamics_enhanced specially for Actions/Events
        components_by_type: Dict[str, List[str]] = defaultdict(list)

        for entity in entities:
            comp_code = None

            # Check for standard extraction types first
            if entity.extraction_type in EXTRACTION_TYPE_TO_COMPONENT:
                comp_code = EXTRACTION_TYPE_TO_COMPONENT[entity.extraction_type]

            # Special handling for temporal_dynamics_enhanced (Actions and Events)
            elif entity.extraction_type == 'temporal_dynamics_enhanced':
                if entity.entity_type:
                    comp_code = ENTITY_TYPE_TO_COMPONENT.get(entity.entity_type.lower())

            if comp_code:
                # Combine label and definition for richer semantic content
                text = entity.entity_label or ''
                if entity.entity_definition:
                    text = f"{text}: {entity.entity_definition}"
                if text.strip():
                    components_by_type[comp_code].append(text)

        if len(components_by_type) < min_components:
            logger.warning(
                f"Case {case_id}: Only {len(components_by_type)} component types found "
                f"({list(components_by_type.keys())}), need at least {min_components}"
            )
            return None

        # Generate embedding for each component type
        component_embeddings: Dict[str, np.ndarray] = {}
        for comp_code, texts in components_by_type.items():
            # Concatenate all texts for this component type
            combined_text = ' '.join(texts)

            # Truncate if very long (SentenceTransformer typically has 512 token limit)
            # Rough estimate: 4 chars per token
            max_chars = 2000
            if len(combined_text) > max_chars:
                combined_text = combined_text[:max_chars]
                logger.debug(
                    f"Case {case_id}: Truncated {comp_code} text from "
                    f"{len(' '.join(texts))} to {max_chars} chars"
                )

            try:
                embedding = self._get_local_embedding(combined_text)
                component_embeddings[comp_code] = embedding
            except Exception as e:
                logger.error(f"Case {case_id}: Failed to embed {comp_code}: {e}")
                continue

        if not component_embeddings:
            logger.error(f"Case {case_id}: No component embeddings generated")
            return None

        # Compute weighted aggregation
        # Only use weights for components that actually exist
        aggregated = np.zeros(384)
        total_weight = 0.0

        for comp_code, embedding in component_embeddings.items():
            weight = weights.get(comp_code, 0.0)
            aggregated += weight * embedding
            total_weight += weight

        # Normalize by actual weight sum (in case some components are missing)
        if total_weight > 0:
            aggregated = aggregated / total_weight

        # L2 normalize the final embedding for cosine similarity
        norm = np.linalg.norm(aggregated)
        if norm > 0:
            aggregated = aggregated / norm

        # L2 normalize individual component embeddings for cosine similarity
        normalized_components: Dict[str, np.ndarray] = {}
        for comp_code, emb in component_embeddings.items():
            comp_norm = np.linalg.norm(emb)
            if comp_norm > 0:
                normalized_components[comp_code] = emb / comp_norm
            else:
                normalized_components[comp_code] = emb

        logger.info(
            f"Case {case_id}: Generated component-aggregated embedding from "
            f"{len(component_embeddings)} components: {list(component_embeddings.keys())}"
        )

        return aggregated, normalized_components

    def extract_and_save_component_embedding(self, case_id: int) -> bool:
        """
        Generate and save component embeddings for a case.

        Stores both the aggregated combined_embedding and nine individual
        per-component embeddings (embedding_R, embedding_P, etc.) in
        case_precedent_features.

        Args:
            case_id: Database ID of the case document

        Returns:
            True if successful, False otherwise
        """
        try:
            gen_result = self.generate_component_aggregated_embedding(case_id)

            if gen_result is None:
                logger.warning(f"Case {case_id}: Could not generate component embedding")
                return False

            aggregated, component_embeddings = gen_result

            # Build parameter dict with aggregated and per-component embeddings
            params = {
                'case_id': case_id,
                'combined': aggregated.tolist(),
                'now': datetime.utcnow(),
            }

            # Add per-component embeddings (None for missing components)
            for comp_code in ['R', 'P', 'O', 'S', 'Rs', 'A', 'E', 'Ca', 'Cs']:
                emb = component_embeddings.get(comp_code)
                params[f'emb_{comp_code}'] = emb.tolist() if emb is not None else None

            query = text("""
                UPDATE case_precedent_features
                SET combined_embedding = :combined,
                    embedding_R = :emb_R,
                    embedding_P = :emb_P,
                    embedding_O = :emb_O,
                    embedding_S = :emb_S,
                    embedding_Rs = :emb_Rs,
                    embedding_A = :emb_A,
                    embedding_E = :emb_E,
                    embedding_Ca = :emb_Ca,
                    embedding_Cs = :emb_Cs,
                    extraction_method = 'component_aggregation',
                    extracted_at = :now
                WHERE case_id = :case_id
            """)

            result = db.session.execute(query, params)
            db.session.commit()

            if result.rowcount == 0:
                logger.warning(
                    f"Case {case_id}: No case_precedent_features row to update. "
                    "Run extract_precedent_features first."
                )
                return False

            comp_list = sorted(component_embeddings.keys())
            logger.info(
                f"Case {case_id}: Saved {len(comp_list)} component embeddings "
                f"({', '.join(comp_list)}) + aggregated"
            )
            return True

        except Exception as e:
            logger.error(f"Case {case_id}: Error saving component embedding: {e}")
            db.session.rollback()
            return False
