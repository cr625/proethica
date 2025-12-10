"""
Precedent Discovery Services

This module provides services for finding and analyzing precedent cases
in the NSPE Board of Ethical Review case database.

References:
- CBR-RAG (Wiratunga et al., 2024): https://aclanthology.org/2024.lrec-main.939/
  Case-Based Reasoning for Retrieval Augmented Generation
- NS-LCR (Sun et al., 2024): https://aclanthology.org/2024.lrec-main.939/
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
