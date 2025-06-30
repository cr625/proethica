"""
Recommendation Engine for ProEthica ethical decision-making system.

This service synthesizes case-guideline associations, pattern recognition,
and similarity analysis to generate actionable ethical recommendations.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy import desc, func
from sqlalchemy.orm import joinedload

from app.models import db
from app.models.document import Document
from app.models.guideline import Guideline
# Import models with graceful fallback for testing
try:
    from app.models.case_guideline_associations import CaseGuidelineAssociation
except ImportError:
    CaseGuidelineAssociation = None

try:
    from app.models.outcome_patterns import OutcomePattern
except ImportError:
    OutcomePattern = None
    
try:
    from app.models.case_prediction_results import CasePredictionResult
except ImportError:
    CasePredictionResult = None
try:
    from app.services.section_similarity_service import SectionSimilarityService
except ImportError:
    SectionSimilarityService = None


logger = logging.getLogger(__name__)


@dataclass
class EthicalRecommendation:
    """A single ethical recommendation with supporting evidence."""
    
    id: str
    title: str
    recommendation_type: str  # 'action', 'principle', 'caution', 'consultation'
    confidence: float  # 0.0 to 1.0
    priority: str  # 'critical', 'high', 'medium', 'low'
    
    # Core recommendation
    summary: str
    detailed_explanation: str
    ethical_reasoning: str
    
    # Supporting evidence
    guideline_concepts: List[Dict[str, Any]]
    similar_cases: List[Dict[str, Any]]
    pattern_indicators: List[Dict[str, Any]]
    
    # Risk/outcome assessment
    predicted_outcome: Optional[str]
    outcome_confidence: Optional[float]
    risk_level: str  # 'low', 'medium', 'high', 'critical'
    
    # Additional context
    stakeholder_considerations: List[str]
    implementation_steps: List[str]
    potential_challenges: List[str]


@dataclass
class RecommendationSummary:
    """Summary of all recommendations for a case."""
    
    case_id: int
    case_title: str
    overall_risk_assessment: str
    key_ethical_themes: List[str]
    recommendations: List[EthicalRecommendation]
    confidence_overview: Dict[str, float]
    processing_metadata: Dict[str, Any]


class RecommendationEngine:
    """
    Core recommendation engine that synthesizes associations into actionable guidance.
    
    This service combines:
    1. Case-guideline associations with confidence scores
    2. Pattern recognition for outcome prediction
    3. Similar case analysis for precedent-based reasoning
    4. Ethical principle analysis for foundational guidance
    """
    
    def __init__(self):
        """Initialize the recommendation engine."""
        self.similarity_service = SectionSimilarityService() if SectionSimilarityService else None
        self.logger = logging.getLogger(f"{__name__}.RecommendationEngine")
        
        # Recommendation type thresholds
        self.confidence_thresholds = {
            'critical': 0.9,
            'high': 0.75,
            'medium': 0.6,
            'low': 0.4
        }
        
        # Pattern risk mappings
        self.risk_patterns = {
            'safety_risk_ignored': 'critical',
            'competence_boundary_exceeded': 'high',
            'dishonest_communication': 'high',
            'public_welfare_deprioritized': 'high',
            'public_safety_prioritized': 'low',
            'honest_communication_maintained': 'low',
            'competence_boundary_respected': 'low',
            'public_welfare_prioritized': 'low'
        }
    
    def generate_recommendations(self, case_id: int) -> RecommendationSummary:
        """
        Generate comprehensive ethical recommendations for a case.
        
        Args:
            case_id: ID of the case to analyze
            
        Returns:
            RecommendationSummary with all recommendations and analysis
        """
        self.logger.info(f"Generating recommendations for case {case_id}")
        
        # Get case and its associations
        case = Document.query.get(case_id)
        if not case:
            raise ValueError(f"Case {case_id} not found")
        
        associations = self._get_case_associations(case_id)
        if not associations:
            return self._generate_no_data_recommendations(case)
        
        # Generate different types of recommendations
        recommendations = []
        
        # 1. Pattern-based outcome predictions
        pattern_recommendations = self._generate_pattern_recommendations(case_id, associations)
        recommendations.extend(pattern_recommendations)
        
        # 2. High-confidence guideline associations
        guideline_recommendations = self._generate_guideline_recommendations(case_id, associations)
        recommendations.extend(guideline_recommendations)
        
        # 3. Similar case analysis
        similar_case_recommendations = self._generate_similar_case_recommendations(case_id)
        recommendations.extend(similar_case_recommendations)
        
        # 4. Risk assessment recommendations
        risk_recommendations = self._generate_risk_recommendations(case_id, associations)
        recommendations.extend(risk_recommendations)
        
        # Sort recommendations by priority and confidence
        recommendations = self._rank_recommendations(recommendations)
        
        # Generate overall assessment
        overall_risk = self._assess_overall_risk(associations, recommendations)
        key_themes = self._extract_key_themes(associations)
        confidence_overview = self._calculate_confidence_overview(associations, recommendations)
        
        return RecommendationSummary(
            case_id=case_id,
            case_title=case.title,
            overall_risk_assessment=overall_risk,
            key_ethical_themes=key_themes,
            recommendations=recommendations,
            confidence_overview=confidence_overview,
            processing_metadata={
                'associations_count': len(associations),
                'recommendation_count': len(recommendations),
                'avg_confidence': sum(r.confidence for r in recommendations) / len(recommendations) if recommendations else 0,
                'generated_at': db.func.now()
            }
        )
    
    def _get_case_associations(self, case_id: int) -> List:
        """Get all associations for a case, ordered by confidence."""
        if CaseGuidelineAssociation is None:
            # Return empty list if model doesn't exist
            return []
        
        return CaseGuidelineAssociation.query.filter_by(case_id=case_id)\
            .options(joinedload(CaseGuidelineAssociation.guideline))\
            .order_by(desc(CaseGuidelineAssociation.overall_confidence))\
            .all()
    
    def _generate_pattern_recommendations(self, case_id: int, associations: List) -> List[EthicalRecommendation]:
        """Generate recommendations based on pattern recognition."""
        recommendations = []
        
        # Get outcome patterns
        if OutcomePattern is None:
            return recommendations
            
        patterns = OutcomePattern.query.all()
        pattern_matches = []
        
        for pattern in patterns:
            # Calculate pattern match score based on associations
            match_score = self._calculate_pattern_match(pattern, associations)
            if match_score > 0.6:  # Threshold for significant pattern match
                pattern_matches.append((pattern, match_score))
        
        # Generate recommendations for significant pattern matches
        for pattern, match_score in sorted(pattern_matches, key=lambda x: x[1], reverse=True)[:3]:
            rec = self._create_pattern_recommendation(pattern, match_score, associations)
            if rec:
                recommendations.append(rec)
        
        return recommendations
    
    def _generate_guideline_recommendations(self, case_id: int, associations: List) -> List[EthicalRecommendation]:
        """Generate recommendations from high-confidence guideline associations."""
        recommendations = []
        
        # Get top associations (high confidence)
        top_associations = [a for a in associations if a.overall_confidence > 0.7][:5]
        
        for i, association in enumerate(top_associations):
            rec = EthicalRecommendation(
                id=f"guideline_{association.id}",
                title=f"Follow {association.guideline_concept_uri} Principle",
                recommendation_type='principle',
                confidence=association.overall_confidence,
                priority=self._get_priority_from_confidence(association.overall_confidence),
                
                summary=f"Apply the {association.guideline_concept_uri} ethical principle based on strong case alignment",
                detailed_explanation=association.association_reasoning or "Strong semantic alignment with guideline principles",
                ethical_reasoning=association.llm_reasoning or "LLM analysis indicates strong relevance to case context",
                
                guideline_concepts=[{
                    'uri': association.guideline_concept_uri,
                    'confidence': association.overall_confidence,
                    'reasoning': association.association_reasoning
                }],
                similar_cases=[],
                pattern_indicators=association.pattern_indicators or [],
                
                predicted_outcome=None,
                outcome_confidence=None,
                risk_level=self._assess_association_risk(association),
                
                stakeholder_considerations=self._extract_stakeholder_considerations(association),
                implementation_steps=self._generate_implementation_steps(association),
                potential_challenges=self._identify_potential_challenges(association)
            )
            recommendations.append(rec)
        
        return recommendations
    
    def _generate_similar_case_recommendations(self, case_id: int) -> List[EthicalRecommendation]:
        """Generate recommendations based on similar cases."""
        recommendations = []
        
        try:
            # Find similar cases using existing similarity service
            if not self.similarity_service:
                return recommendations
                
            similar_cases = self.similarity_service.find_similar_cases(case_id, limit=3)
            
            for i, (similar_case_id, similarity_score, matching_sections) in enumerate(similar_cases):
                if similarity_score > 0.7:  # High similarity threshold
                    rec = self._create_similar_case_recommendation(
                        case_id, similar_case_id, similarity_score, matching_sections
                    )
                    if rec:
                        recommendations.append(rec)
            
        except Exception as e:
            self.logger.warning(f"Could not generate similar case recommendations: {e}")
        
        return recommendations
    
    def _generate_risk_recommendations(self, case_id: int, associations: List) -> List[EthicalRecommendation]:
        """Generate risk-based recommendations."""
        recommendations = []
        
        # Analyze pattern indicators for risk factors
        risk_factors = []
        high_risk_patterns = []
        
        for association in associations:
            if association.pattern_indicators:
                for indicator, value in association.pattern_indicators.items():
                    if value and indicator in ['safety_risk_ignored', 'competence_boundary_exceeded', 'dishonest_communication']:
                        risk_factors.append((indicator, association.overall_confidence))
                        high_risk_patterns.append(indicator)
        
        # Generate risk mitigation recommendations
        if high_risk_patterns:
            risk_rec = EthicalRecommendation(
                id=f"risk_mitigation_{case_id}",
                title="Risk Mitigation Required",
                recommendation_type='caution',
                confidence=max(rf[1] for rf in risk_factors) if risk_factors else 0.8,
                priority='critical' if any(rf[1] > 0.8 for rf in risk_factors) else 'high',
                
                summary="Multiple risk factors identified requiring immediate attention",
                detailed_explanation=f"Analysis identified {len(high_risk_patterns)} significant risk patterns",
                ethical_reasoning="Risk mitigation is essential for ethical compliance",
                
                guideline_concepts=[],
                similar_cases=[],
                pattern_indicators=[{'pattern': p, 'risk_level': 'high'} for p in high_risk_patterns],
                
                predicted_outcome='potential_ethical_violation',
                outcome_confidence=max(rf[1] for rf in risk_factors) if risk_factors else 0.8,
                risk_level='critical',
                
                stakeholder_considerations=['Public safety', 'Professional integrity', 'Legal compliance'],
                implementation_steps=['Immediate risk assessment', 'Stakeholder consultation', 'Alternative evaluation'],
                potential_challenges=['Time constraints', 'Resource limitations', 'Competing priorities']
            )
            recommendations.append(risk_rec)
        
        return recommendations
    
    def _calculate_pattern_match(self, pattern, associations: List) -> float:
        """Calculate how well a pattern matches the case associations."""
        if not pattern.guideline_concepts or not associations:
            return 0.0
        
        # Simple matching based on guideline concept overlap
        pattern_concepts = set(pattern.guideline_concepts)
        case_concepts = set(a.guideline_concept_uri for a in associations)
        
        if not pattern_concepts:
            return 0.0
        
        overlap = len(pattern_concepts.intersection(case_concepts))
        return overlap / len(pattern_concepts)
    
    def _create_pattern_recommendation(self, pattern: OutcomePattern, match_score: float, associations: List[CaseGuidelineAssociation]) -> Optional[EthicalRecommendation]:
        """Create a recommendation based on a pattern match."""
        
        # Determine recommendation based on pattern type
        if pattern.ethical_correlation > 0.8:
            rec_type = 'action'
            title = f"Follow {pattern.pattern_name} Approach"
            summary = f"Pattern analysis suggests following the {pattern.pattern_name} approach"
        else:
            rec_type = 'caution'
            title = f"Avoid {pattern.pattern_name} Pattern"
            summary = f"Pattern analysis indicates {pattern.pattern_name} leads to negative outcomes"
        
        return EthicalRecommendation(
            id=f"pattern_{pattern.id}",
            title=title,
            recommendation_type=rec_type,
            confidence=match_score * pattern.ethical_correlation,
            priority=self._get_priority_from_confidence(match_score),
            
            summary=summary,
            detailed_explanation=f"Pattern '{pattern.pattern_name}' matches with {match_score:.1%} confidence and {pattern.ethical_correlation:.1%} ethical correlation",
            ethical_reasoning=f"Historical analysis shows this pattern correlates with {'positive' if pattern.ethical_correlation > 0.5 else 'negative'} ethical outcomes",
            
            guideline_concepts=[],
            similar_cases=[],
            pattern_indicators=[{'pattern': pattern.pattern_name, 'match_score': match_score}],
            
            predicted_outcome='ethical_compliance' if pattern.ethical_correlation > 0.5 else 'ethical_concern',
            outcome_confidence=pattern.ethical_correlation,
            risk_level=self.risk_patterns.get(pattern.pattern_name, 'medium'),
            
            stakeholder_considerations=[],
            implementation_steps=[],
            potential_challenges=[]
        )
    
    def _create_similar_case_recommendation(self, case_id: int, similar_case_id: int, similarity_score: float, matching_sections: List[str]) -> Optional[EthicalRecommendation]:
        """Create a recommendation based on a similar case."""
        
        similar_case = Document.query.get(similar_case_id)
        if not similar_case:
            return None
        
        return EthicalRecommendation(
            id=f"similar_case_{similar_case_id}",
            title=f"Learn from Similar Case: {similar_case.title[:50]}...",
            recommendation_type='consultation',
            confidence=similarity_score,
            priority=self._get_priority_from_confidence(similarity_score),
            
            summary=f"Case shows {similarity_score:.1%} similarity to {similar_case.title}",
            detailed_explanation=f"Similar patterns found in sections: {', '.join(matching_sections)}",
            ethical_reasoning="Similar cases can provide valuable precedent for ethical decision-making",
            
            guideline_concepts=[],
            similar_cases=[{
                'id': similar_case_id,
                'title': similar_case.title,
                'similarity_score': similarity_score,
                'matching_sections': matching_sections
            }],
            pattern_indicators=[],
            
            predicted_outcome=None,
            outcome_confidence=None,
            risk_level='low',
            
            stakeholder_considerations=[],
            implementation_steps=[f"Review similar case: {similar_case.title}", "Compare decision contexts", "Adapt relevant insights"],
            potential_challenges=["Contextual differences", "Different stakeholder priorities"]
        )
    
    def _rank_recommendations(self, recommendations: List[EthicalRecommendation]) -> List[EthicalRecommendation]:
        """Rank recommendations by priority and confidence."""
        priority_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        
        return sorted(
            recommendations,
            key=lambda r: (priority_order.get(r.priority, 0), r.confidence),
            reverse=True
        )
    
    def _get_priority_from_confidence(self, confidence: float) -> str:
        """Convert confidence score to priority level."""
        if confidence >= self.confidence_thresholds['critical']:
            return 'critical'
        elif confidence >= self.confidence_thresholds['high']:
            return 'high'
        elif confidence >= self.confidence_thresholds['medium']:
            return 'medium'
        else:
            return 'low'
    
    def _assess_association_risk(self, association: CaseGuidelineAssociation) -> str:
        """Assess risk level from association pattern indicators."""
        if not association.pattern_indicators:
            return 'low'
        
        risk_indicators = ['safety_risk_ignored', 'competence_boundary_exceeded', 'dishonest_communication']
        if any(association.pattern_indicators.get(indicator, False) for indicator in risk_indicators):
            return 'high'
        
        return 'medium' if association.overall_confidence > 0.8 else 'low'
    
    def _assess_overall_risk(self, associations: List[CaseGuidelineAssociation], recommendations: List[EthicalRecommendation]) -> str:
        """Assess overall risk level for the case."""
        if any(r.priority == 'critical' for r in recommendations):
            return 'critical'
        elif any(r.priority == 'high' for r in recommendations):
            return 'high'
        elif any(r.priority == 'medium' for r in recommendations):
            return 'medium'
        else:
            return 'low'
    
    def _extract_key_themes(self, associations: List[CaseGuidelineAssociation]) -> List[str]:
        """Extract key ethical themes from associations."""
        themes = set()
        
        for association in associations[:5]:  # Top 5 associations
            if association.guideline_concept_uri:
                # Extract theme from URI (simplified)
                concept = association.guideline_concept_uri.split('#')[-1].split('/')[-1]
                themes.add(concept.replace('_', ' ').title())
        
        return list(themes)
    
    def _calculate_confidence_overview(self, associations: List[CaseGuidelineAssociation], recommendations: List[EthicalRecommendation]) -> Dict[str, float]:
        """Calculate confidence overview statistics."""
        if not associations:
            return {'avg_association_confidence': 0.0, 'avg_recommendation_confidence': 0.0}
        
        avg_association = sum(a.overall_confidence for a in associations) / len(associations)
        avg_recommendation = sum(r.confidence for r in recommendations) / len(recommendations) if recommendations else 0.0
        
        return {
            'avg_association_confidence': avg_association,
            'avg_recommendation_confidence': avg_recommendation,
            'high_confidence_associations': len([a for a in associations if a.overall_confidence > 0.8]),
            'critical_recommendations': len([r for r in recommendations if r.priority == 'critical'])
        }
    
    def _extract_stakeholder_considerations(self, association: CaseGuidelineAssociation) -> List[str]:
        """Extract stakeholder considerations from association."""
        # This could be enhanced with more sophisticated analysis
        considerations = []
        
        if association.pattern_indicators:
            if association.pattern_indicators.get('public_safety_involved'):
                considerations.append('Public safety')
            if association.pattern_indicators.get('client_interests'):
                considerations.append('Client interests')
            if association.pattern_indicators.get('professional_standards'):
                considerations.append('Professional standards')
        
        return considerations or ['General stakeholders']
    
    def _generate_implementation_steps(self, association: CaseGuidelineAssociation) -> List[str]:
        """Generate implementation steps for an association."""
        steps = [
            'Review relevant guideline principles',
            'Assess stakeholder impacts',
            'Consider alternative approaches',
            'Document decision rationale'
        ]
        
        # Add specific steps based on concept type
        if 'safety' in association.guideline_concept_uri.lower():
            steps.insert(1, 'Conduct safety risk assessment')
        if 'competence' in association.guideline_concept_uri.lower():
            steps.insert(1, 'Verify competence boundaries')
        
        return steps
    
    def _identify_potential_challenges(self, association: CaseGuidelineAssociation) -> List[str]:
        """Identify potential implementation challenges."""
        challenges = [
            'Balancing competing interests',
            'Resource constraints',
            'Time pressures'
        ]
        
        if association.overall_confidence < 0.7:
            challenges.append('Uncertain guidance applicability')
        
        return challenges
    
    def _generate_no_data_recommendations(self, case: Document) -> RecommendationSummary:
        """Generate basic recommendations when no association data is available."""
        
        basic_rec = EthicalRecommendation(
            id="basic_ethical_review",
            title="Conduct Comprehensive Ethical Review",
            recommendation_type='action',
            confidence=0.8,
            priority='high',
            
            summary="No specific guideline associations found. Recommend comprehensive ethical analysis.",
            detailed_explanation="This case requires manual ethical review as automated analysis found insufficient guideline associations.",
            ethical_reasoning="All cases should undergo ethical review following established frameworks.",
            
            guideline_concepts=[],
            similar_cases=[],
            pattern_indicators=[],
            
            predicted_outcome=None,
            outcome_confidence=None,
            risk_level='medium',
            
            stakeholder_considerations=['All relevant parties'],
            implementation_steps=[
                'Identify all stakeholders',
                'Review applicable ethical codes',
                'Consult with ethics committee',
                'Document decision process'
            ],
            potential_challenges=['Limited guidance', 'Complex stakeholder dynamics']
        )
        
        return RecommendationSummary(
            case_id=case.id,
            case_title=case.title,
            overall_risk_assessment='unknown',
            key_ethical_themes=['General Ethics'],
            recommendations=[basic_rec],
            confidence_overview={'avg_association_confidence': 0.0, 'avg_recommendation_confidence': 0.8},
            processing_metadata={'associations_count': 0, 'recommendation_count': 1}
        )


# Create singleton instance
recommendation_engine = RecommendationEngine()