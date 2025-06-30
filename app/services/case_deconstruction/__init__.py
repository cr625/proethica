"""
Case Deconstruction Services

This module provides services for deconstructing legal/ethical cases into 
structured scenarios for predictive analysis and outcome testing.
"""

from .base_adapter import BaseCaseDeconstructionAdapter
from .data_models import (
    DeconstructedCase, 
    EthicalDecisionPoint, 
    ComponentAction, 
    DecisionOption,
    ReasoningChain,
    ReasoningStep
)

__all__ = [
    'BaseCaseDeconstructionAdapter',
    'DeconstructedCase',
    'EthicalDecisionPoint', 
    'ComponentAction',
    'DecisionOption',
    'ReasoningChain',
    'ReasoningStep'
]