"""
Precedent Discovery Service

Orchestrates multi-factor similarity search with LLM-enhanced analysis.
Supports both interactive queries and batch processing.

References:
- CBR-RAG (Wiratunga et al., 2024): https://aclanthology.org/2024.lrec-main.939/
  Case-based reasoning for RAG
- NS-LCR (Sun et al., 2024): https://aclanthology.org/2024.lrec-main.939/
  Logic rules for legal case retrieval
"""

import logging
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import text
from app import db
from app.models import Document

from .case_feature_extractor import CaseFeatureExtractor, ExtractedFeatures
from .similarity_service import PrecedentSimilarityService, SimilarityResult
from models import ModelConfig

logger = logging.getLogger(__name__)


@dataclass
class PrecedentMatch:
    """A matched precedent case with analysis."""
    target_case_id: int
    target_case_title: str
    target_case_url: Optional[str]
    overall_score: float
    component_scores: Dict[str, float]
    matching_provisions: List[str]
    outcome_match: bool
    llm_analysis: Optional[str] = None
    relevance_explanation: Optional[str] = None
    target_outcome: Optional[str] = None
    target_transformation: Optional[str] = None


@dataclass
class PrecedentAnalysis:
    """Deep analysis of precedent relationship between two cases."""
    source_case_id: int
    target_case_id: int
    similarity_score: float
    relationship_type: str  # 'supporting', 'distinguishing', 'analogous', 'contrasting'
    key_similarities: List[str]
    key_differences: List[str]
    applicable_principles: List[str]
    recommendation: str
    llm_reasoning: str


class PrecedentDiscoveryService:
    """
    Main service for precedent discovery and analysis.

    Provides:
    - Interactive precedent search for individual cases
    - Batch processing for all cases
    - LLM-enhanced relationship analysis
    - Storage to precedent_discoveries table
    """

    def __init__(self, llm_client=None):
        """
        Initialize the service.

        Args:
            llm_client: Optional Anthropic client for LLM analysis
        """
        self.llm_client = llm_client
        self.feature_extractor = CaseFeatureExtractor()
        self.similarity_service = PrecedentSimilarityService(llm_client)

    def find_precedents(
        self,
        source_case_id: int,
        limit: int = 10,
        min_score: float = 0.3,
        focus: Optional[str] = None,
        use_dynamic_weights: bool = False,
        include_llm_analysis: bool = True
    ) -> List[PrecedentMatch]:
        """
        Find precedent cases for a given source case.

        Args:
            source_case_id: ID of the case to find precedents for
            limit: Maximum number of precedents to return
            min_score: Minimum similarity score threshold
            focus: Optional focus area for weight adjustment
            use_dynamic_weights: Whether to use LLM for dynamic weight determination
            include_llm_analysis: Whether to include LLM analysis of relationships

        Returns:
            List of PrecedentMatch objects, sorted by relevance
        """
        logger.info(f"Finding precedents for case {source_case_id}")

        # Ensure source case has features
        self._ensure_features_exist(source_case_id)

        # Get weights
        if use_dynamic_weights and self.llm_client:
            weights = self.similarity_service.get_dynamic_weights(source_case_id, focus)
        else:
            weights = None  # Use defaults

        # Find similar cases
        similarity_results = self.similarity_service.find_similar_cases(
            source_case_id=source_case_id,
            limit=limit,
            min_score=min_score,
            weights=weights
        )

        # Convert to PrecedentMatch objects with case details
        matches = []
        for result in similarity_results:
            match = self._create_precedent_match(result)

            # Add LLM analysis if requested
            if include_llm_analysis and self.llm_client:
                analysis = self._generate_quick_analysis(source_case_id, result.target_case_id, result)
                match.llm_analysis = analysis.get('summary')
                match.relevance_explanation = analysis.get('relevance')

            matches.append(match)

        logger.info(f"Found {len(matches)} precedents for case {source_case_id}")
        return matches

    def analyze_precedent_relationship(
        self,
        source_case_id: int,
        target_case_id: int
    ) -> PrecedentAnalysis:
        """
        Perform deep LLM analysis of precedent relationship between two cases.

        Args:
            source_case_id: ID of the source case
            target_case_id: ID of the potential precedent case

        Returns:
            PrecedentAnalysis with detailed relationship analysis
        """
        logger.info(f"Analyzing relationship between case {source_case_id} and {target_case_id}")

        # Ensure features exist
        self._ensure_features_exist(source_case_id)
        self._ensure_features_exist(target_case_id)

        # Get similarity result
        similarity = self.similarity_service.calculate_similarity(source_case_id, target_case_id)

        # Get case details
        source_case = Document.query.get(source_case_id)
        target_case = Document.query.get(target_case_id)

        if not source_case or not target_case:
            raise ValueError("Case not found")

        # Get section content for analysis
        source_sections = self._get_case_sections(source_case_id)
        target_sections = self._get_case_sections(target_case_id)

        # Generate LLM analysis
        if self.llm_client:
            analysis = self._generate_deep_analysis(
                source_case, target_case,
                source_sections, target_sections,
                similarity
            )
        else:
            # Fallback to rule-based analysis
            analysis = self._generate_rule_based_analysis(similarity)

        return PrecedentAnalysis(
            source_case_id=source_case_id,
            target_case_id=target_case_id,
            similarity_score=similarity.overall_similarity,
            relationship_type=analysis['relationship_type'],
            key_similarities=analysis['similarities'],
            key_differences=analysis['differences'],
            applicable_principles=analysis['principles'],
            recommendation=analysis['recommendation'],
            llm_reasoning=analysis['reasoning']
        )

    def save_precedent_discovery(
        self,
        source_case_id: int,
        match: PrecedentMatch,
        precedent_type: str = 'similar'
    ) -> int:
        """
        Save a precedent discovery to the database.

        Args:
            source_case_id: ID of the source case
            match: PrecedentMatch object
            precedent_type: Type of precedent relationship

        Returns:
            ID of the saved record
        """
        query = text("""
            INSERT INTO precedent_discoveries (
                source_case_id,
                source_decision_id,
                target_case_id,
                target_decision_id,
                similarity_score,
                precedent_type,
                llm_analysis,
                component_scores,
                matching_provisions,
                relevance_explanation,
                classified_by
            ) VALUES (
                :source_case_id,
                :source_decision_id,
                :target_case_id,
                :target_decision_id,
                :similarity_score,
                :precedent_type,
                :llm_analysis,
                :component_scores,
                :matching_provisions,
                :relevance_explanation,
                :classified_by
            )
            ON CONFLICT (source_case_id, source_decision_id, target_case_id, target_decision_id)
            DO UPDATE SET
                similarity_score = EXCLUDED.similarity_score,
                precedent_type = EXCLUDED.precedent_type,
                llm_analysis = EXCLUDED.llm_analysis,
                component_scores = EXCLUDED.component_scores,
                matching_provisions = EXCLUDED.matching_provisions,
                relevance_explanation = EXCLUDED.relevance_explanation,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """)

        result = db.session.execute(query, {
            'source_case_id': source_case_id,
            'source_decision_id': 'main',
            'target_case_id': match.target_case_id,
            'target_decision_id': 'main',
            'similarity_score': match.overall_score,
            'precedent_type': precedent_type,
            'llm_analysis': json.dumps({'analysis': match.llm_analysis}) if match.llm_analysis else None,
            'component_scores': json.dumps(match.component_scores),
            'matching_provisions': match.matching_provisions,
            'relevance_explanation': match.relevance_explanation,
            'classified_by': 'claude' if self.llm_client else 'automatic'
        })

        db.session.commit()

        row = result.fetchone()
        return row[0] if row else None

    def batch_discover_all(
        self,
        min_score: float = 0.3,
        top_k: int = 5,
        save_results: bool = True
    ) -> Dict[int, List[PrecedentMatch]]:
        """
        Batch process all cases for precedent discovery.

        Args:
            min_score: Minimum similarity threshold
            top_k: Number of top precedents per case
            save_results: Whether to save results to database

        Returns:
            Dict mapping case_id to list of PrecedentMatch objects
        """
        logger.info("Starting batch precedent discovery for all cases")

        # Ensure all cases have features
        self.feature_extractor.extract_and_save_all_cases()

        # Get all case IDs
        cases = Document.query.filter(
            Document.document_type.in_(['case', 'case_study'])
        ).all()

        results = {}

        for case in cases:
            try:
                matches = self.find_precedents(
                    source_case_id=case.id,
                    limit=top_k,
                    min_score=min_score,
                    include_llm_analysis=False  # Skip LLM for batch processing
                )

                results[case.id] = matches

                if save_results:
                    for match in matches:
                        self.save_precedent_discovery(case.id, match)

                logger.info(f"Processed case {case.id}: {len(matches)} precedents found")

            except Exception as e:
                logger.error(f"Error processing case {case.id}: {e}")
                results[case.id] = []

        total_precedents = sum(len(m) for m in results.values())
        logger.info(f"Batch discovery complete: {total_precedents} total precedent relationships")

        return results

    def get_precedent_summary(self, case_id: int) -> Dict:
        """
        Get a summary of precedent relationships for a case.

        Args:
            case_id: ID of the case

        Returns:
            Dict with summary statistics and top precedents
        """
        query = text("""
            SELECT
                pd.target_case_id,
                d.title,
                pd.similarity_score,
                pd.precedent_type,
                pd.matching_provisions,
                pd.component_scores
            FROM precedent_discoveries pd
            JOIN documents d ON pd.target_case_id = d.id
            WHERE pd.source_case_id = :case_id
            ORDER BY pd.similarity_score DESC
            LIMIT 10
        """)

        results = db.session.execute(query, {'case_id': case_id}).fetchall()

        precedents = []
        for row in results:
            precedents.append({
                'case_id': row[0],
                'title': row[1],
                'score': row[2],
                'type': row[3],
                'matching_provisions': row[4] or [],
                'component_scores': row[5] or {}
            })

        return {
            'case_id': case_id,
            'precedent_count': len(precedents),
            'top_precedents': precedents[:5],
            'all_precedents': precedents
        }

    def _ensure_features_exist(self, case_id: int):
        """Ensure precedent features exist for a case, extracting if necessary."""
        query = text("SELECT id FROM case_precedent_features WHERE case_id = :case_id")
        result = db.session.execute(query, {'case_id': case_id}).fetchone()

        if not result:
            logger.info(f"Extracting features for case {case_id}")
            features = self.feature_extractor.extract_precedent_features(case_id)
            self.feature_extractor.save_features(features)

    def _create_precedent_match(self, similarity: SimilarityResult) -> PrecedentMatch:
        """Create a PrecedentMatch from a SimilarityResult."""
        # Get case details
        case = Document.query.get(similarity.target_case_id)

        # Get features for additional info
        query = text("""
            SELECT outcome_type, transformation_type
            FROM case_precedent_features
            WHERE case_id = :case_id
        """)
        features = db.session.execute(query, {'case_id': similarity.target_case_id}).fetchone()

        return PrecedentMatch(
            target_case_id=similarity.target_case_id,
            target_case_title=case.title if case else f"Case {similarity.target_case_id}",
            target_case_url=case.source if case else None,
            overall_score=similarity.overall_similarity,
            component_scores=similarity.component_scores,
            matching_provisions=similarity.matching_provisions,
            outcome_match=similarity.outcome_match,
            target_outcome=features[0] if features else None,
            target_transformation=features[1] if features else None
        )

    def _get_case_sections(self, case_id: int) -> Dict[str, str]:
        """Get section content for a case."""
        from app.models.document_section import DocumentSection

        sections = DocumentSection.query.filter_by(document_id=case_id).all()
        return {s.section_type: s.content for s in sections}

    def _generate_quick_analysis(
        self,
        source_id: int,
        target_id: int,
        similarity: SimilarityResult
    ) -> Dict[str, str]:
        """Generate a quick LLM analysis of precedent relevance."""
        if not self.llm_client:
            return {
                'summary': None,
                'relevance': f"Similar based on: {', '.join(f'{k}={v:.2f}' for k, v in similarity.component_scores.items() if v > 0.3)}"
            }

        source_case = Document.query.get(source_id)
        target_case = Document.query.get(target_id)

        prompt = f"""Briefly explain why this case is relevant as a precedent.

Source case: {source_case.title if source_case else 'Unknown'}
Potential precedent: {target_case.title if target_case else 'Unknown'}

Similarity scores:
- Facts similarity: {similarity.component_scores.get('facts_similarity', 0):.2f}
- Discussion similarity: {similarity.component_scores.get('discussion_similarity', 0):.2f}
- Provision overlap: {similarity.component_scores.get('provision_overlap', 0):.2f}
- Outcome match: {'Yes' if similarity.outcome_match else 'No'}
- Matching provisions: {', '.join(similarity.matching_provisions) or 'None'}

In 2-3 sentences, explain:
1. What makes this a relevant precedent
2. How it might inform analysis of the source case"""

        try:
            response = self.llm_client.messages.create(
                model=ModelConfig.get_claude_model("default"),
                max_tokens=200,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text

            return {
                'summary': text[:500],
                'relevance': text[:200]
            }
        except Exception as e:
            logger.warning(f"Error generating quick analysis: {e}")
            return {
                'summary': None,
                'relevance': f"Score: {similarity.overall_similarity:.2f}"
            }

    def _generate_deep_analysis(
        self,
        source_case: Document,
        target_case: Document,
        source_sections: Dict[str, str],
        target_sections: Dict[str, str],
        similarity: SimilarityResult
    ) -> Dict:
        """Generate deep LLM analysis of precedent relationship."""
        # Truncate sections for prompt
        def truncate(text, max_len=1000):
            if not text:
                return ""
            return text[:max_len] + "..." if len(text) > max_len else text

        prompt = f"""Analyze the precedent relationship between these two engineering ethics cases.

## Source Case: {source_case.title}
Facts: {truncate(source_sections.get('facts', ''))}
Conclusion: {truncate(source_sections.get('conclusion', ''))}

## Potential Precedent: {target_case.title}
Facts: {truncate(target_sections.get('facts', ''))}
Conclusion: {truncate(target_sections.get('conclusion', ''))}

## Similarity Metrics
- Overall: {similarity.overall_similarity:.2f}
- Matching provisions: {', '.join(similarity.matching_provisions) or 'None'}
- Outcome match: {'Yes' if similarity.outcome_match else 'No'}

Analyze this precedent relationship:

1. RELATIONSHIP_TYPE: Choose one: supporting, distinguishing, analogous, contrasting
2. KEY_SIMILARITIES: List 3-5 key similarities
3. KEY_DIFFERENCES: List 3-5 key differences
4. APPLICABLE_PRINCIPLES: List relevant NSPE principles
5. RECOMMENDATION: How should this precedent inform analysis of the source case?
6. REASONING: Explain your analysis (2-3 paragraphs)

Format your response with clear section headers."""

        try:
            response = self.llm_client.messages.create(
                model=ModelConfig.get_claude_model("default"),
                max_tokens=1000,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text

            # Parse response
            return self._parse_analysis_response(text)

        except Exception as e:
            logger.error(f"Error generating deep analysis: {e}")
            return self._generate_rule_based_analysis(similarity)

    def _generate_rule_based_analysis(self, similarity: SimilarityResult) -> Dict:
        """Generate rule-based analysis when LLM is not available."""
        # Determine relationship type based on scores
        if similarity.outcome_match and similarity.overall_similarity > 0.6:
            relationship_type = 'supporting'
        elif not similarity.outcome_match and similarity.overall_similarity > 0.5:
            relationship_type = 'contrasting'
        elif similarity.overall_similarity > 0.4:
            relationship_type = 'analogous'
        else:
            relationship_type = 'distinguishing'

        similarities = []
        differences = []

        for component, score in similarity.component_scores.items():
            component_name = component.replace('_', ' ').title()
            if score > 0.5:
                similarities.append(f"High {component_name} ({score:.2f})")
            elif score < 0.3:
                differences.append(f"Low {component_name} ({score:.2f})")

        if similarity.matching_provisions:
            similarities.append(f"Shared provisions: {', '.join(similarity.matching_provisions)}")

        if similarity.outcome_match:
            similarities.append("Same ethical outcome")
        else:
            differences.append("Different ethical outcome")

        return {
            'relationship_type': relationship_type,
            'similarities': similarities or ['Similar overall context'],
            'differences': differences or ['Different specific circumstances'],
            'principles': similarity.matching_provisions or ['General ethical principles'],
            'recommendation': f"Consider this case as a {relationship_type} precedent",
            'reasoning': f"Based on similarity score of {similarity.overall_similarity:.2f}"
        }

    def _parse_analysis_response(self, text: str) -> Dict:
        """Parse structured analysis from LLM response."""
        import re

        result = {
            'relationship_type': 'analogous',
            'similarities': [],
            'differences': [],
            'principles': [],
            'recommendation': '',
            'reasoning': ''
        }

        # Extract sections using headers
        sections = {
            'relationship_type': r'RELATIONSHIP_TYPE[:\s]*([^\n]+)',
            'similarities': r'KEY_SIMILARITIES[:\s]*(.+?)(?=KEY_DIFFERENCES|$)',
            'differences': r'KEY_DIFFERENCES[:\s]*(.+?)(?=APPLICABLE_PRINCIPLES|$)',
            'principles': r'APPLICABLE_PRINCIPLES[:\s]*(.+?)(?=RECOMMENDATION|$)',
            'recommendation': r'RECOMMENDATION[:\s]*(.+?)(?=REASONING|$)',
            'reasoning': r'REASONING[:\s]*(.+?)$'
        }

        for key, pattern in sections.items():
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                content = match.group(1).strip()

                if key == 'relationship_type':
                    # Extract single word
                    for rt in ['supporting', 'distinguishing', 'analogous', 'contrasting']:
                        if rt in content.lower():
                            result[key] = rt
                            break
                elif key in ['similarities', 'differences', 'principles']:
                    # Extract list items
                    items = re.findall(r'[-*\d.]\s*(.+?)(?=\n[-*\d.]|\n\n|$)', content)
                    result[key] = [item.strip() for item in items if item.strip()]
                else:
                    result[key] = content[:500]

        return result
