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
from .phase4_connector import (
    update_precedent_features_from_phase4,
    get_phase4_features_summary
)
from .cited_case_ingestor import (
    CitedCaseIngestor,
    get_ingestion_summary
)

__all__ = [
    'CaseFeatureExtractor',
    'PrecedentSimilarityService',
    'PrecedentDiscoveryService',
    'update_precedent_features_from_phase4',
    'get_phase4_features_summary',
    'CitedCaseIngestor',
    'get_ingestion_summary',
]
