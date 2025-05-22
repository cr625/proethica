"""
Patching script for the PredictionService class and LLMService.

This script applies fixes to handle edge cases in document section metadata formats
and ensures proper LLM initialization with engineering ethics examples instead of
military medical triage examples, all without modifying the original source code.
"""

import logging
from typing import Dict, Any
from app.services.experiment.prediction_service import PredictionService
from app.services.experiment.prediction_service_fix import fixed_get_document_sections
from app.services.experiment.llm_service_fix import fixed_init
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

def patch_prediction_service():
    """
    Apply patches to the PredictionService class and LLMService class.
    
    This function monkey-patches:
    1. PredictionService with the fixed implementation of get_document_sections
    2. LLMService with a fixed initialization method that ensures proper LLM use
    """
    # Patch the PredictionService.get_document_sections method
    logger.info("Applying patch to PredictionService.get_document_sections")
    
    # Store the original method for potential rollback
    if not hasattr(PredictionService, '_original_get_document_sections'):
        PredictionService._original_get_document_sections = PredictionService.get_document_sections
    
    # Apply the fixed method
    PredictionService.get_document_sections = fixed_get_document_sections
    
    logger.info("PredictionService.get_document_sections successfully patched")
    
    # Patch the LLMService.__init__ method
    logger.info("Applying patch to LLMService.__init__")
    
    # Store the original method for potential rollback
    if not hasattr(LLMService, '_original_init'):
        LLMService._original_init = LLMService.__init__
    
    # Apply the fixed initialization method
    LLMService.__init__ = fixed_init
    
    logger.info("LLMService.__init__ successfully patched")
    
def rollback_patch():
    """
    Roll back all applied patches and restore the original methods.
    """
    # Rollback PredictionService.get_document_sections
    if hasattr(PredictionService, '_original_get_document_sections'):
        logger.info("Rolling back patch to PredictionService.get_document_sections")
        PredictionService.get_document_sections = PredictionService._original_get_document_sections
        delattr(PredictionService, '_original_get_document_sections')
        logger.info("Original PredictionService.get_document_sections method restored")
    else:
        logger.warning("No original PredictionService.get_document_sections found, patch not rolled back")
        
    # Rollback LLMService.__init__
    if hasattr(LLMService, '_original_init'):
        logger.info("Rolling back patch to LLMService.__init__")
        LLMService.__init__ = LLMService._original_init
        delattr(LLMService, '_original_init')
        logger.info("Original LLMService.__init__ method restored")
    else:
        logger.warning("No original LLMService.__init__ found, patch not rolled back")
