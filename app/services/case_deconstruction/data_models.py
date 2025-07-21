"""
Data models for case deconstruction system.

These models represent the structured breakdown of legal/ethical cases
into their component parts for analysis and scenario generation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class DecisionType(Enum):
    """Types of ethical decisions that can be made."""
    DISCLOSURE = "disclosure"
    SAFETY = "safety" 
    CONFIDENTIALITY = "confidentiality"
    PROFESSIONAL_DUTY = "professional_duty"
    PUBLIC_WELFARE = "public_welfare"
    RESOURCE_ALLOCATION = "resource_allocation"
    CONFLICT_OF_INTEREST = "conflict_of_interest"


class StakeholderRole(Enum):
    """Roles that stakeholders can have in ethical scenarios."""
    PROFESSIONAL = "professional"  # Engineer, doctor, lawyer, etc.
    CLIENT = "client"
    EMPLOYER = "employer"
    PUBLIC = "public"
    REGULATOR = "regulator"
    COLLEAGUE = "colleague"
    SUPERVISOR = "supervisor"


@dataclass
class Stakeholder:
    """Represents a stakeholder in an ethical case."""
    name: str
    role: StakeholderRole
    description: str
    interests: List[str] = field(default_factory=list)
    power_level: float = 0.5  # 0.0 to 1.0
    influence_level: float = 0.5  # 0.0 to 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'role': self.role.value,
            'description': self.description,
            'interests': self.interests,
            'power_level': self.power_level,
            'influence_level': self.influence_level
        }


@dataclass
class ComponentAction:
    """Specific actionable steps within a decision option."""
    action_id: str
    description: str
    sequence_order: int
    required_stakeholders: List[str] = field(default_factory=list)
    ethical_considerations: List[str] = field(default_factory=list)
    expected_outcomes: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'action_id': self.action_id,
            'description': self.description,
            'sequence_order': self.sequence_order,
            'required_stakeholders': self.required_stakeholders,
            'ethical_considerations': self.ethical_considerations,
            'expected_outcomes': self.expected_outcomes,
            'risk_factors': self.risk_factors
        }


@dataclass
class DecisionOption:
    """A specific ethical path/choice within a decision point."""
    option_id: str
    title: str
    ethical_justification: str
    component_actions: List[ComponentAction] = field(default_factory=list)
    predicted_outcomes: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    alignment_with_principles: Dict[str, float] = field(default_factory=dict)  # principle -> score
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'option_id': self.option_id,
            'title': self.title,
            'ethical_justification': self.ethical_justification,
            'component_actions': [action.to_dict() for action in self.component_actions],
            'predicted_outcomes': self.predicted_outcomes,
            'risk_factors': self.risk_factors,
            'alignment_with_principles': self.alignment_with_principles
        }


@dataclass
class EthicalDecisionPoint:
    """High-level ethical choice with component actions."""
    decision_id: str
    title: str
    description: str
    decision_type: DecisionType
    ethical_principles: List[str] = field(default_factory=list)
    stakeholder_impacts: Dict[str, str] = field(default_factory=dict)  # stakeholder -> impact description
    primary_options: List[DecisionOption] = field(default_factory=list)
    context_factors: List[str] = field(default_factory=list)
    urgency_level: float = 0.5  # 0.0 to 1.0
    complexity_level: float = 0.5  # 0.0 to 1.0
    
    # Additional fields for interactive scenarios (optional)
    sequence_number: Optional[int] = None
    protagonist: Optional[str] = None
    question_text: Optional[str] = None
    narrative_setup: Optional[str] = None
    case_sections: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = {
            'decision_id': self.decision_id,
            'title': self.title,
            'description': self.description,
            'decision_type': self.decision_type.value,
            'ethical_principles': self.ethical_principles,
            'stakeholder_impacts': self.stakeholder_impacts,
            'primary_options': [option.to_dict() for option in self.primary_options],
            'context_factors': self.context_factors,
            'urgency_level': self.urgency_level,
            'complexity_level': self.complexity_level
        }
        
        # Add interactive fields if present
        if self.sequence_number is not None:
            base_dict['sequence_number'] = self.sequence_number
        if self.protagonist:
            base_dict['protagonist'] = self.protagonist
        if self.question_text:
            base_dict['question_text'] = self.question_text
        if self.narrative_setup:
            base_dict['narrative_setup'] = self.narrative_setup
        if self.case_sections:
            base_dict['case_sections'] = self.case_sections
            
        return base_dict


@dataclass
class ReasoningStep:
    """Individual step in the logical reasoning chain."""
    step_order: int
    reasoning_type: str  # "fact_analysis", "principle_application", "stakeholder_impact", etc.
    input_elements: List[str]  # What facts/principles led to this step
    reasoning_logic: str  # The logical connection
    output_conclusion: str  # What this step concludes
    confidence: float = 0.5  # Confidence in this step (0.0 to 1.0)
    supporting_evidence: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'step_order': self.step_order,
            'reasoning_type': self.reasoning_type,
            'input_elements': self.input_elements,
            'reasoning_logic': self.reasoning_logic,
            'output_conclusion': self.output_conclusion,
            'confidence': self.confidence,
            'supporting_evidence': self.supporting_evidence
        }


@dataclass
class AlternativePath:
    """Alternative reasoning chain that could lead to different conclusions."""
    path_id: str
    description: str
    reasoning_steps: List[ReasoningStep] = field(default_factory=list)
    predicted_outcome: str = ""
    likelihood: float = 0.5  # How likely this path is (0.0 to 1.0)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'path_id': self.path_id,
            'description': self.description,
            'reasoning_steps': [step.to_dict() for step in self.reasoning_steps],
            'predicted_outcome': self.predicted_outcome,
            'likelihood': self.likelihood
        }


@dataclass
class ReasoningChain:
    """Maps the logical progression: Facts → Principles → Conclusion."""
    
    # Input: Case Facts
    case_facts: List[str] = field(default_factory=list)
    contextual_factors: List[str] = field(default_factory=list)
    
    # Intermediate: Ethical Analysis  
    applicable_principles: List[str] = field(default_factory=list)
    principle_conflicts: List[Dict[str, Any]] = field(default_factory=list)
    stakeholder_considerations: Dict[str, List[str]] = field(default_factory=dict)
    
    # Reasoning Steps
    reasoning_steps: List[ReasoningStep] = field(default_factory=list)
    alternative_paths: List[AlternativePath] = field(default_factory=list)
    
    # Output: Predicted Conclusion
    predicted_outcome: str = ""
    confidence_score: float = 0.5  # Overall confidence (0.0 to 1.0)
    actual_outcome: str = ""  # Ground truth for training
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'case_facts': self.case_facts,
            'contextual_factors': self.contextual_factors,
            'applicable_principles': self.applicable_principles,
            'principle_conflicts': self.principle_conflicts,
            'stakeholder_considerations': self.stakeholder_considerations,
            'reasoning_steps': [step.to_dict() for step in self.reasoning_steps],
            'alternative_paths': [path.to_dict() for path in self.alternative_paths],
            'predicted_outcome': self.predicted_outcome,
            'confidence_score': self.confidence_score,
            'actual_outcome': self.actual_outcome,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


@dataclass
class DeconstructionAnalysis:
    """Result of case deconstruction analysis with confidence scores."""
    stakeholders: List[Stakeholder] = field(default_factory=list)
    decision_points: List[EthicalDecisionPoint] = field(default_factory=list)
    reasoning_chain: Optional[ReasoningChain] = None
    
    # Confidence scores for each component
    stakeholder_confidence: float = 0.0
    decision_points_confidence: float = 0.0
    reasoning_confidence: float = 0.0
    
    # Overall metadata
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    adapter_version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'stakeholders': [s.to_dict() for s in self.stakeholders],
            'decision_points': [dp.to_dict() for dp in self.decision_points],
            'reasoning_chain': self.reasoning_chain.to_dict() if self.reasoning_chain else None,
            'stakeholder_confidence': self.stakeholder_confidence,
            'decision_points_confidence': self.decision_points_confidence,
            'reasoning_confidence': self.reasoning_confidence,
            'analysis_timestamp': self.analysis_timestamp.isoformat(),
            'adapter_version': self.adapter_version
        }


@dataclass 
class DeconstructedCase:
    """Complete deconstruction of a case with all analysis components."""
    case_id: int
    adapter_type: str
    analysis: DeconstructionAnalysis
    human_validated: bool = False
    validation_notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'case_id': self.case_id,
            'adapter_type': self.adapter_type,
            'analysis': self.analysis.to_dict(),
            'human_validated': self.human_validated,
            'validation_notes': self.validation_notes
        }