"""
Patching script for the PredictionService class.

This script applies fixes to the PredictionService class to handle edge cases
in document section metadata formats without modifying the original source code.
"""

import logging
from typing import Dict, Any
from app.services.experiment.prediction_service import PredictionService
from app.services.experiment.prediction_service_fix import fixed_get_document_sections

logger = logging.getLogger(__name__)

def patch_prediction_service():
    """
    Apply the fixed version of get_document_sections to the PredictionService class.
    
    This function monkey-patches the PredictionService class with the fixed implementation
    of get_document_sections that handles various metadata formats safely.
    """
    logger.info("Applying patch to PredictionService.get_document_sections")
    
    # Store the original method for potential rollback
    if not hasattr(PredictionService, '_original_get_document_sections'):
        PredictionService._original_get_document_sections = PredictionService.get_document_sections
    
    # Apply the fixed method
    PredictionService.get_document_sections = fixed_get_document_sections
    
    logger.info("PredictionService.get_document_sections successfully patched")
    
def rollback_patch():
    """
    Roll back the patch and restore the original method.
    """
    if hasattr(PredictionService, '_original_get_document_sections'):
        logger.info("Rolling back patch to PredictionService.get_document_sections")
        PredictionService.get_document_sections = PredictionService._original_get_document_sections
        delattr(PredictionService, '_original_get_document_sections')
        logger.info("Original method restored")
    else:
        logger.warning("No original method found, patch not rolled back")
