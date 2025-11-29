"""
Case Feature Extractor for Precedent Discovery

Extracts structured features from NSPE cases at ingestion time
for efficient precedent matching.

References:
- CBR-RAG (Markel et al., 2024): https://arxiv.org/html/2404.04302v1
  Hybrid similarity with intra/inter embeddings
- NS-LCR (Zhang et al., 2024): https://arxiv.org/html/2403.01457v1
  Logic rules for explainable case matching
"""

import re
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import text
from app import db
from app.models import Document
from app.models.document_section import DocumentSection
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


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
