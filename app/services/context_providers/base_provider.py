#!/usr/bin/env python
"""
Base class for application context providers.

Context providers are responsible for gathering specific types of
application context information to be provided to LLMs during inference.
"""

from typing import Dict, Any, Optional


class ContextProvider:
    """Base class for context providers."""
    
    def __init__(self, service):
        """
        Initialize with reference to parent service.
        
        Args:
            service: Reference to the parent ApplicationContextService
        """
        self.service = service
    
    def get_context(self, request_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get context from this provider.
        
        Args:
            request_context: Dictionary with context of the request
                May include world_id, scenario_id, query, etc.
            
        Returns:
            Dictionary with provider's context or None if not available
        """
        raise NotImplementedError("Subclasses must implement get_context")
    
    def format_context(self, context: Dict[str, Any]) -> str:
        """
        Format context for this provider.
        
        Args:
            context: Context from get_context
            
        Returns:
            Formatted string representation
        """
        raise NotImplementedError("Subclasses must implement format_context")
