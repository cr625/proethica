"""
Base adapter class for case deconstruction.

This module provides the abstract base class that all domain-specific
case deconstruction adapters must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import logging

from .data_models import (
    DeconstructedCase, 
    DeconstructionAnalysis,
    EthicalDecisionPoint, 
    Stakeholder,
    ReasoningChain
)


logger = logging.getLogger(__name__)


class BaseCaseDeconstructionAdapter(ABC):
    """
    Abstract base class for domain-specific case deconstruction.
    
    Each domain (e.g., engineering ethics, medical ethics, legal ethics)
    should implement this interface to provide domain-specific analysis.
    """
    
    def __init__(self, domain_name: str, version: str = "1.0"):
        """
        Initialize the adapter.
        
        Args:
            domain_name: Name of the domain this adapter handles
            version: Version of this adapter implementation
        """
        self.domain_name = domain_name
        self.version = version
        self.logger = logging.getLogger(f"{__name__}.{domain_name}")
    
    @abstractmethod
    def extract_stakeholders(self, case_content: Dict[str, Any]) -> List[Stakeholder]:
        """
        Extract key stakeholders/actors from case content.
        
        Args:
            case_content: Dictionary containing case sections and metadata
            
        Returns:
            List of Stakeholder objects representing key actors
        """
        pass
    
    @abstractmethod
    def identify_ethical_decision_points(self, case_content: Dict[str, Any]) -> List[EthicalDecisionPoint]:
        """
        Identify high-level ethical choices in the case.
        
        Args:
            case_content: Dictionary containing case sections and metadata
            
        Returns:
            List of EthicalDecisionPoint objects representing key ethical choices
        """
        pass
    
    @abstractmethod
    def extract_reasoning_chain(self, case_content: Dict[str, Any]) -> ReasoningChain:
        """
        Extract facts → principles → conclusion reasoning chain.
        
        Args:
            case_content: Dictionary containing case sections and metadata
            
        Returns:
            ReasoningChain object mapping logical progression
        """
        pass
    
    def calculate_confidence_scores(self, analysis: DeconstructionAnalysis) -> DeconstructionAnalysis:
        """
        Calculate confidence scores for each component of the analysis.
        
        This base implementation provides simple heuristics. Subclasses can override
        for more sophisticated domain-specific confidence calculation.
        
        Args:
            analysis: DeconstructionAnalysis to score
            
        Returns:
            Updated analysis with confidence scores
        """
        # Simple heuristics for confidence scoring
        stakeholder_count = len(analysis.stakeholders)
        decision_point_count = len(analysis.decision_points)
        
        # Stakeholder confidence based on count and completeness
        analysis.stakeholder_confidence = min(1.0, stakeholder_count * 0.2)
        if stakeholder_count > 0:
            # Boost confidence if stakeholders have detailed information
            avg_interests = sum(len(s.interests) for s in analysis.stakeholders) / stakeholder_count
            analysis.stakeholder_confidence = min(1.0, analysis.stakeholder_confidence + avg_interests * 0.1)
        
        # Decision points confidence based on count and option completeness  
        analysis.decision_points_confidence = min(1.0, decision_point_count * 0.3)
        if decision_point_count > 0:
            avg_options = sum(len(dp.primary_options) for dp in analysis.decision_points) / decision_point_count
            analysis.decision_points_confidence = min(1.0, analysis.decision_points_confidence + avg_options * 0.1)
        
        # Reasoning confidence based on step count and completeness
        if analysis.reasoning_chain:
            step_count = len(analysis.reasoning_chain.reasoning_steps)
            analysis.reasoning_confidence = min(1.0, step_count * 0.15)
            
            # Boost if we have facts, principles, and conclusion
            has_facts = len(analysis.reasoning_chain.case_facts) > 0
            has_principles = len(analysis.reasoning_chain.applicable_principles) > 0
            has_outcome = bool(analysis.reasoning_chain.predicted_outcome)
            
            completeness_bonus = sum([has_facts, has_principles, has_outcome]) * 0.1
            analysis.reasoning_confidence = min(1.0, analysis.reasoning_confidence + completeness_bonus)
        
        return analysis
    
    def deconstruct_case(self, case_content: Dict[str, Any]) -> DeconstructedCase:
        """
        Main method to deconstruct a case into structured components.
        
        This orchestrates the entire deconstruction process by calling
        the abstract methods in sequence.
        
        Args:
            case_content: Dictionary containing case sections and metadata
            
        Returns:
            DeconstructedCase with complete analysis
        """
        self.logger.info(f"Starting case deconstruction with {self.domain_name} adapter v{self.version}")
        
        try:
            # Extract components
            stakeholders = self.extract_stakeholders(case_content)
            decision_points = self.identify_ethical_decision_points(case_content)
            reasoning_chain = self.extract_reasoning_chain(case_content)
            
            # Create analysis object
            analysis = DeconstructionAnalysis(
                stakeholders=stakeholders,
                decision_points=decision_points,
                reasoning_chain=reasoning_chain,
                adapter_version=self.version
            )
            
            # Calculate confidence scores
            analysis = self.calculate_confidence_scores(analysis)
            
            # Create final result
            case_id = case_content.get('id', 0)
            deconstructed_case = DeconstructedCase(
                case_id=case_id,
                adapter_type=self.domain_name,
                analysis=analysis
            )
            
            self.logger.info(f"Case deconstruction complete: {len(stakeholders)} stakeholders, "
                           f"{len(decision_points)} decision points")
            
            return deconstructed_case
            
        except Exception as e:
            self.logger.error(f"Error deconstructing case: {str(e)}")
            raise
    
    def get_adapter_info(self) -> Dict[str, Any]:
        """
        Get information about this adapter.
        
        Returns:
            Dictionary with adapter metadata
        """
        return {
            'domain_name': self.domain_name,
            'version': self.version,
            'adapter_class': self.__class__.__name__
        }
    
    def validate_case_content(self, case_content: Dict[str, Any]) -> bool:
        """
        Validate that case content has required fields for this adapter.
        
        Args:
            case_content: Case content to validate
            
        Returns:
            True if content is valid for this adapter
        """
        required_fields = ['id', 'title', 'content']
        
        for field in required_fields:
            if field not in case_content:
                self.logger.warning(f"Missing required field: {field}")
                return False
        
        return True