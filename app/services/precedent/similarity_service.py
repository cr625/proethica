"""
Multi-Factor Similarity Service for Precedent Discovery

Implements CBR-RAG hybrid similarity approach with LLM-based
dynamic weight adjustment.

References:
- CBR-RAG (Wiratunga et al., 2024): https://aclanthology.org/2024.lrec-main.939/
  Weighted combination: w1*Sim(Q,Q) + w2*Sim(Q,S) + w3*Sim(Q,E)
- NS-LCR (Sun et al., 2024): https://aclanthology.org/2024.lrec-main.939/
  Dual-level matching for explainability
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from sqlalchemy import text

from app import db

logger = logging.getLogger(__name__)


@dataclass
class SimilarityResult:
    """Result of similarity calculation between two cases."""
    source_case_id: int
    target_case_id: int
    overall_similarity: float
    component_scores: Dict[str, float]
    matching_provisions: List[str]
    outcome_match: bool
    weights_used: Dict[str, float]
    method: str = 'section'  # 'section' or 'component'
    per_component_scores: Optional[Dict[str, float]] = None  # D-tuple component cosine similarities


class PrecedentSimilarityService:
    """
    Calculates multi-factor similarity between cases for precedent discovery.

    Two similarity modes:
    1. Section-based (default): Uses facts + discussion embeddings separately
    2. Component-based: Uses combined_embedding (weighted aggregation of 9 components)

    Section-based formula:
        Score = w1*facts_sim + w2*discussion_sim + w3*provision_overlap +
                w4*outcome_alignment + w5*tag_overlap + w6*principle_overlap

    Component-based formula:
        Score = w1*component_sim + w2*provision_overlap +
                w3*outcome_alignment + w4*tag_overlap + w5*principle_overlap
    """

    # Original section-based weights
    DEFAULT_WEIGHTS = {
        'facts_similarity': 0.15,
        'discussion_similarity': 0.25,
        'provision_overlap': 0.25,
        'outcome_alignment': 0.15,
        'tag_overlap': 0.10,
        'principle_overlap': 0.10
    }

    # Component-aware weights - uses combined_embedding which aggregates
    # all 9 components with their ethical importance weights
    COMPONENT_AWARE_WEIGHTS = {
        'component_similarity': 0.40,  # Uses combined_embedding (9-component weighted)
        'provision_overlap': 0.25,
        'outcome_alignment': 0.15,
        'tag_overlap': 0.10,
        'principle_overlap': 0.10
    }

    def __init__(self, llm_client=None):
        """
        Initialize the similarity service.

        Args:
            llm_client: Optional LLM client for dynamic weight adjustment
        """
        self.llm_client = llm_client

    def calculate_similarity(
        self,
        source_case_id: int,
        target_case_id: int,
        weights: Optional[Dict[str, float]] = None,
        use_component_embedding: bool = False
    ) -> SimilarityResult:
        """
        Calculate multi-factor similarity between two cases.

        Args:
            source_case_id: ID of the source case
            target_case_id: ID of the target case
            weights: Optional custom weights. Uses DEFAULT_WEIGHTS or
                     COMPONENT_AWARE_WEIGHTS based on use_component_embedding.
            use_component_embedding: If True, use combined_embedding (9-component
                     weighted aggregation) instead of separate section embeddings.

        Returns:
            SimilarityResult with overall score and component breakdown
        """
        # Select appropriate default weights
        if weights is None:
            weights = self.COMPONENT_AWARE_WEIGHTS if use_component_embedding else self.DEFAULT_WEIGHTS

        # Normalize weights to sum to 1.0
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        # Get features for both cases
        source_features = self._get_case_features(source_case_id)
        target_features = self._get_case_features(target_case_id)

        method = 'component' if use_component_embedding else 'section'

        if source_features is None or target_features is None:
            return SimilarityResult(
                source_case_id=source_case_id,
                target_case_id=target_case_id,
                overall_similarity=0.0,
                component_scores={},
                matching_provisions=[],
                outcome_match=False,
                weights_used=weights,
                method=method
            )

        # Calculate component similarities
        component_scores = {}
        per_comp = None

        if use_component_embedding:
            # Component-aware mode: per-component cosine similarities
            from app.services.precedent.case_feature_extractor import COMPONENT_WEIGHTS
            per_comp = {}
            comp_weighted_sum = 0.0
            comp_total_weight = 0.0

            for comp_code in ['R', 'P', 'O', 'S', 'Rs', 'A', 'E', 'Ca', 'Cs']:
                src_emb = source_features.get(f'embedding_{comp_code}')
                tgt_emb = target_features.get(f'embedding_{comp_code}')
                if src_emb is not None and tgt_emb is not None:
                    sim = self._cosine_similarity(src_emb, tgt_emb)
                    per_comp[comp_code] = sim
                    w = COMPONENT_WEIGHTS.get(comp_code, 0.0)
                    comp_weighted_sum += w * sim
                    comp_total_weight += w

            component_scores['component_similarity'] = (
                comp_weighted_sum / comp_total_weight if comp_total_weight > 0 else 0.0
            )
        else:
            # Section-based mode: use separate embeddings
            component_scores['facts_similarity'] = self._cosine_similarity(
                source_features.get('facts_embedding'),
                target_features.get('facts_embedding')
            )
            component_scores['discussion_similarity'] = self._cosine_similarity(
                source_features.get('discussion_embedding'),
                target_features.get('discussion_embedding')
            )

        # Provision overlap (Jaccard)
        component_scores['provision_overlap'], matching_provisions = self._calculate_provision_overlap(
            source_features.get('provisions_cited', []),
            target_features.get('provisions_cited', [])
        )

        # Outcome alignment
        component_scores['outcome_alignment'] = self._calculate_outcome_alignment(
            source_features.get('outcome_type'),
            target_features.get('outcome_type')
        )

        # Tag overlap (Jaccard)
        component_scores['tag_overlap'] = self._calculate_jaccard_similarity(
            set(source_features.get('subject_tags', [])),
            set(target_features.get('subject_tags', []))
        )

        # Principle overlap (from Step 4 data)
        component_scores['principle_overlap'] = self._calculate_principle_overlap(
            source_features.get('principle_tensions', []),
            target_features.get('principle_tensions', [])
        )

        # Calculate weighted overall score
        overall_similarity = sum(
            weights.get(component, 0) * score
            for component, score in component_scores.items()
        )

        outcome_match = source_features.get('outcome_type') == target_features.get('outcome_type')

        return SimilarityResult(
            source_case_id=source_case_id,
            target_case_id=target_case_id,
            overall_similarity=overall_similarity,
            component_scores=component_scores,
            matching_provisions=matching_provisions,
            outcome_match=outcome_match,
            weights_used=weights,
            method=method,
            per_component_scores=per_comp,
        )

    def find_similar_cases(
        self,
        source_case_id: int,
        limit: int = 10,
        min_score: float = 0.0,
        weights: Optional[Dict[str, float]] = None,
        exclude_self: bool = True,
        use_component_embedding: bool = False
    ) -> List[SimilarityResult]:
        """
        Find cases most similar to the source case.

        Uses a two-stage approach:
        1. Fast embedding similarity for candidate retrieval
        2. Multi-factor scoring for final ranking

        Args:
            source_case_id: ID of the source case
            limit: Maximum number of results
            min_score: Minimum similarity score threshold
            weights: Optional custom weights
            exclude_self: Whether to exclude the source case from results
            use_component_embedding: If True, use combined_embedding (9-component
                     weighted aggregation) instead of separate section embeddings.

        Returns:
            List of SimilarityResult objects, sorted by overall_similarity
        """
        # Get all case IDs with features
        all_case_ids = self._get_all_case_ids_with_features()

        if exclude_self:
            all_case_ids = [cid for cid in all_case_ids if cid != source_case_id]

        # Calculate similarity for each candidate
        results = []
        for target_case_id in all_case_ids:
            try:
                result = self.calculate_similarity(
                    source_case_id, target_case_id, weights,
                    use_component_embedding=use_component_embedding
                )
                if result.overall_similarity >= min_score:
                    results.append(result)
            except Exception as e:
                logger.warning(f"Error calculating similarity for case {target_case_id}: {e}")

        # Sort by overall similarity descending
        results.sort(key=lambda r: r.overall_similarity, reverse=True)

        return results[:limit]

    def get_dynamic_weights(
        self,
        case_id: int,
        focus: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Use LLM to determine optimal weights based on case characteristics.

        Args:
            case_id: The case to analyze
            focus: Optional focus area (e.g., 'provisions', 'outcomes', 'principles')

        Returns:
            Dict of weights for each similarity component
        """
        if not self.llm_client:
            logger.info("No LLM client available, using default weights")
            return self.DEFAULT_WEIGHTS.copy()

        # Get case features for context
        features = self._get_case_features(case_id)
        if not features:
            return self.DEFAULT_WEIGHTS.copy()

        # Build prompt for weight determination
        prompt = self._build_weight_prompt(features, focus)

        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse weights from response
            weights = self._parse_weight_response(response.content[0].text)
            return weights

        except Exception as e:
            logger.error(f"Error getting dynamic weights: {e}")
            return self.DEFAULT_WEIGHTS.copy()

    def cache_similarity(self, result: SimilarityResult):
        """
        Cache a similarity result for faster future retrieval.

        Args:
            result: SimilarityResult to cache
        """
        import json
        query = text("""
            INSERT INTO precedent_similarity_cache (
                source_case_id,
                target_case_id,
                facts_similarity,
                discussion_similarity,
                provision_overlap,
                outcome_alignment,
                tag_overlap,
                principle_overlap,
                overall_similarity,
                weights_used,
                computation_method
            ) VALUES (
                :source_case_id,
                :target_case_id,
                :facts_similarity,
                :discussion_similarity,
                :provision_overlap,
                :outcome_alignment,
                :tag_overlap,
                :principle_overlap,
                :overall_similarity,
                :weights_used,
                :computation_method
            )
            ON CONFLICT (source_case_id, target_case_id) DO UPDATE SET
                facts_similarity = EXCLUDED.facts_similarity,
                discussion_similarity = EXCLUDED.discussion_similarity,
                provision_overlap = EXCLUDED.provision_overlap,
                outcome_alignment = EXCLUDED.outcome_alignment,
                tag_overlap = EXCLUDED.tag_overlap,
                principle_overlap = EXCLUDED.principle_overlap,
                overall_similarity = EXCLUDED.overall_similarity,
                weights_used = EXCLUDED.weights_used,
                computed_at = CURRENT_TIMESTAMP
        """)

        db.session.execute(query, {
            'source_case_id': result.source_case_id,
            'target_case_id': result.target_case_id,
            'facts_similarity': result.component_scores.get('facts_similarity', 0),
            'discussion_similarity': result.component_scores.get('discussion_similarity', 0),
            'provision_overlap': result.component_scores.get('provision_overlap', 0),
            'outcome_alignment': result.component_scores.get('outcome_alignment', 0),
            'tag_overlap': result.component_scores.get('tag_overlap', 0),
            'principle_overlap': result.component_scores.get('principle_overlap', 0),
            'overall_similarity': result.overall_similarity,
            'weights_used': json.dumps(result.weights_used),
            'computation_method': 'static_weights'
        })
        db.session.commit()

    def _get_case_features(self, case_id: int) -> Optional[Dict]:
        """Retrieve features for a case from the database."""
        query = text("""
            SELECT
                case_id,
                outcome_type,
                outcome_confidence,
                provisions_cited,
                subject_tags,
                principle_tensions,
                obligation_conflicts,
                transformation_type,
                facts_embedding,
                discussion_embedding,
                conclusion_embedding,
                combined_embedding,
                embedding_R,
                embedding_P,
                embedding_O,
                embedding_S,
                embedding_Rs,
                embedding_A,
                embedding_E,
                embedding_Ca,
                embedding_Cs
            FROM case_precedent_features
            WHERE case_id = :case_id
        """)

        result = db.session.execute(query, {'case_id': case_id}).fetchone()

        if not result:
            return None

        return {
            'case_id': result[0],
            'outcome_type': result[1],
            'outcome_confidence': result[2],
            'provisions_cited': result[3] or [],
            'subject_tags': result[4] or [],
            'principle_tensions': result[5] or [],
            'obligation_conflicts': result[6] or [],
            'transformation_type': result[7],
            'facts_embedding': self._parse_embedding(result[8]),
            'discussion_embedding': self._parse_embedding(result[9]),
            'conclusion_embedding': self._parse_embedding(result[10]),
            'combined_embedding': self._parse_embedding(result[11]),
            'embedding_R': self._parse_embedding(result[12]),
            'embedding_P': self._parse_embedding(result[13]),
            'embedding_O': self._parse_embedding(result[14]),
            'embedding_S': self._parse_embedding(result[15]),
            'embedding_Rs': self._parse_embedding(result[16]),
            'embedding_A': self._parse_embedding(result[17]),
            'embedding_E': self._parse_embedding(result[18]),
            'embedding_Ca': self._parse_embedding(result[19]),
            'embedding_Cs': self._parse_embedding(result[20]),
        }

    def _get_all_case_ids_with_features(self) -> List[int]:
        """Get all case IDs that have extracted features."""
        query = text("SELECT case_id FROM case_precedent_features")
        results = db.session.execute(query).fetchall()
        return [r[0] for r in results]

    def _parse_embedding(self, embedding_str) -> Optional[np.ndarray]:
        """Parse embedding from database string format."""
        if embedding_str is None:
            return None

        try:
            if isinstance(embedding_str, (list, np.ndarray)):
                return np.array(embedding_str)

            # Parse string representation
            if isinstance(embedding_str, str):
                # Remove brackets and split
                clean = embedding_str.strip('[]')
                values = [float(x.strip()) for x in clean.split(',')]
                return np.array(values)

            return None
        except Exception as e:
            logger.warning(f"Error parsing embedding: {e}")
            return None

    def _cosine_similarity(
        self,
        vec1: Optional[np.ndarray],
        vec2: Optional[np.ndarray]
    ) -> float:
        """Calculate cosine similarity between two vectors."""
        if vec1 is None or vec2 is None:
            return 0.0

        try:
            vec1 = np.array(vec1).flatten()
            vec2 = np.array(vec2).flatten()

            if len(vec1) != len(vec2):
                return 0.0

            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return float(np.dot(vec1, vec2) / (norm1 * norm2))
        except Exception as e:
            logger.warning(f"Error calculating cosine similarity: {e}")
            return 0.0

    def _calculate_provision_overlap(
        self,
        provisions_a: List[str],
        provisions_b: List[str]
    ) -> Tuple[float, List[str]]:
        """
        Calculate Jaccard similarity of provision sets.

        Returns:
            Tuple of (similarity_score, list_of_matching_provisions)
        """
        if not provisions_a or not provisions_b:
            return 0.0, []

        set_a = set(provisions_a)
        set_b = set(provisions_b)

        intersection = set_a & set_b
        union = set_a | set_b

        if not union:
            return 0.0, []

        similarity = len(intersection) / len(union)
        matching = sorted(list(intersection))

        return similarity, matching

    def _calculate_outcome_alignment(
        self,
        outcome_a: Optional[str],
        outcome_b: Optional[str]
    ) -> float:
        """
        Score outcome alignment.

        Returns:
            1.0 for same outcome, 0.0 for opposite, 0.5 for mixed/unclear
        """
        if outcome_a is None or outcome_b is None:
            return 0.5

        if outcome_a == outcome_b:
            return 1.0

        # Opposite outcomes
        if (outcome_a == 'ethical' and outcome_b == 'unethical') or \
           (outcome_a == 'unethical' and outcome_b == 'ethical'):
            return 0.0

        # Mixed or unclear
        return 0.5

    def _calculate_jaccard_similarity(
        self,
        set_a: set,
        set_b: set
    ) -> float:
        """Calculate Jaccard similarity between two sets."""
        if not set_a and not set_b:
            return 0.0

        intersection = len(set_a & set_b)
        union = len(set_a | set_b)

        if union == 0:
            return 0.0

        return intersection / union

    def _calculate_principle_overlap(
        self,
        tensions_a: List[Dict],
        tensions_b: List[Dict]
    ) -> float:
        """
        Calculate similarity based on principle tensions.

        Compares the principles mentioned in tensions from Step 4 analysis.
        """
        if not tensions_a or not tensions_b:
            return 0.0

        # Extract principle names from tensions
        def extract_principles(tensions):
            principles = set()
            for t in tensions:
                if isinstance(t, dict):
                    principles.add(t.get('principle1', ''))
                    principles.add(t.get('principle2', ''))
            principles.discard('')
            return principles

        principles_a = extract_principles(tensions_a)
        principles_b = extract_principles(tensions_b)

        return self._calculate_jaccard_similarity(principles_a, principles_b)

    def _build_weight_prompt(self, features: Dict, focus: Optional[str]) -> str:
        """Build prompt for LLM weight determination."""
        prompt = f"""Analyze this ethics case and determine optimal weights for precedent matching.

Case characteristics:
- Outcome: {features.get('outcome_type', 'unknown')}
- Provisions cited: {len(features.get('provisions_cited', []))} ({', '.join(features.get('provisions_cited', [])[:5])})
- Subject tags: {', '.join(features.get('subject_tags', [])[:5])}
- Transformation type: {features.get('transformation_type', 'unknown')}
- Principle tensions: {len(features.get('principle_tensions', []))}

User focus: {focus or 'general precedent matching'}

Determine weights (0.0-1.0) for each similarity component:
1. facts_similarity - How similar are the factual situations?
2. discussion_similarity - How similar is the ethical analysis?
3. provision_overlap - How important is matching NSPE Code provisions?
4. outcome_alignment - Should we prioritize cases with same outcome?
5. tag_overlap - How important are matching subject categories?
6. principle_overlap - How important are similar principle tensions?

Return weights as JSON:
{{"facts_similarity": 0.X, "discussion_similarity": 0.X, "provision_overlap": 0.X, "outcome_alignment": 0.X, "tag_overlap": 0.X, "principle_overlap": 0.X}}
"""
        return prompt

    def _parse_weight_response(self, response_text: str) -> Dict[str, float]:
        """Parse weight values from LLM response."""
        import json
        import re

        try:
            # Try to find JSON in response
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                weights = json.loads(json_match.group())
                # Validate weights
                if all(k in weights for k in self.DEFAULT_WEIGHTS.keys()):
                    # Normalize
                    total = sum(weights.values())
                    if total > 0:
                        return {k: v / total for k, v in weights.items()}
        except Exception as e:
            logger.warning(f"Error parsing weight response: {e}")

        return self.DEFAULT_WEIGHTS.copy()
