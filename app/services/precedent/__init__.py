"""
Precedent Discovery Services

This module provides services for finding and analyzing precedent cases
in the NSPE Board of Ethical Review case database.

References:
- CBR-RAG (Markel et al., 2024): https://arxiv.org/html/2404.04302v1
  Case-Based Reasoning for Retrieval Augmented Generation
- NS-LCR (Zhang et al., 2024): https://arxiv.org/html/2403.01457v1
  Logic Rules as Explanations for Legal Case Retrieval
"""

from .case_feature_extractor import CaseFeatureExtractor
from .similarity_service import PrecedentSimilarityService
from .precedent_discovery_service import PrecedentDiscoveryService

__all__ = [
    'CaseFeatureExtractor',
    'PrecedentSimilarityService',
    'PrecedentDiscoveryService',
]
