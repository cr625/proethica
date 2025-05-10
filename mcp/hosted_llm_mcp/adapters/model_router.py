"""
Model Router

This module provides a router for directing ontology tasks to the most appropriate
LLM model (Anthropic Claude or OpenAI) based on task characteristics.
"""

import os
import json
import logging
import asyncio
import time
from typing import Dict, Any, List, Optional, Union, Callable

from mcp.hosted_llm_mcp.adapters.anthropic_adapter import AnthropicAdapter
from mcp.hosted_llm_mcp.adapters.openai_adapter import OpenAIAdapter

logger = logging.getLogger(__name__)

class ModelRouter:
    """
    Routes ontology tasks to the most appropriate LLM model based on task type.
    
    This class implements:
    1. Smart routing based on task characteristics
    2. Fallback mechanisms when a model is unavailable
    3. Result caching to reduce API costs
    4. Error handling and recovery
    """

    def __init__(self, 
                anthropic_adapter: AnthropicAdapter,
                openai_adapter: OpenAIAdapter,
                routing_config: Optional[Dict[str, str]] = None,
                cache_ttl: int = 3600):
        """
        Initialize the model router.
        
        Args:
            anthropic_adapter: The Anthropic Claude adapter
            openai_adapter: The OpenAI adapter
            routing_config: Configuration mapping tasks to preferred models
            cache_ttl: Time-to-live for cached results in seconds (default: 1 hour)
        """
        self.anthropic_adapter = anthropic_adapter
        self.openai_adapter = openai_adapter
        
        # Default routing configuration (can be overridden)
        self.routing_config = routing_config or {
            "analyze_concept": "anthropic",
            "suggest_relationships": "openai",
            "expand_hierarchy": "anthropic",
            "validate_ontology": "openai",
            "explain_concept": "anthropic",
            "classify_entity": "openai"
        }
        
        # Simple cache implementation
        self.cache = {}
        self.cache_ttl = cache_ttl
        
        logger.info("Model router initialized with routing config: %s", self.routing_config)

    def _get_cache_key(self, task: str, content: str, **kwargs) -> str:
        """Generate a cache key for a specific request."""
        # Create a unique key based on task + content + relevant kwargs
        key_elements = {
            "task": task,
            "content": content,
            # Only include kwargs that affect the output
            "temperature": kwargs.get("temperature", 0.2),
            "max_tokens": kwargs.get("max_tokens", 2000)
        }
        return json.dumps(key_elements, sort_keys=True)

    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get a cached result if it exists and hasn't expired."""
        if cache_key in self.cache:
            cached_item = self.cache[cache_key]
            # Check if cache entry is still valid
            if time.time() - cached_item["timestamp"] < self.cache_ttl:
                logger.info("Cache hit for key: %s", cache_key)
                return cached_item["result"]
            else:
                # Cache entry has expired
                logger.info("Cache expired for key: %s", cache_key)
                del self.cache[cache_key]
        return None

    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Cache a result with the current timestamp."""
        self.cache[cache_key] = {
            "result": result,
            "timestamp": time.time()
        }
        logger.debug("Cached result for key: %s", cache_key)

    def _get_primary_adapter(self, task: str) -> Union[AnthropicAdapter, OpenAIAdapter]:
        """Get the primary adapter for a specific task based on routing config."""
        model_name = self.routing_config.get(task, "anthropic")
        if model_name.lower() == "openai":
            return self.openai_adapter
        else:
            return self.anthropic_adapter

    def _get_fallback_adapter(self, task: str) -> Union[AnthropicAdapter, OpenAIAdapter]:
        """Get the fallback adapter for a specific task (opposite of primary)."""
        model_name = self.routing_config.get(task, "anthropic")
        if model_name.lower() == "openai":
            return self.anthropic_adapter
        else:
            return self.openai_adapter

    async def route(self, task: str, content: str, **kwargs) -> Dict[str, Any]:
        """
        Route a task to the appropriate model with fallback capability.
        
        Args:
            task: The ontology task to perform
            content: The content for the prompt
            **kwargs: Additional arguments to pass to the model adapter
            
        Returns:
            A dictionary containing the model's response and metadata
        """
        # Generate cache key and check cache
        cache_key = self._get_cache_key(task, content, **kwargs)
        cached_result = self._get_cached_result(cache_key)
        if cached_result and not kwargs.get("bypass_cache", False):
            return cached_result
        
        # Get the primary and fallback adapters for this task
        primary_adapter = self._get_primary_adapter(task)
        fallback_adapter = self._get_fallback_adapter(task)
        
        # Try the primary adapter first
        try:
            logger.info(f"Routing task '{task}' to primary adapter: {type(primary_adapter).__name__}")
            result = await primary_adapter.complete(task, content, **kwargs)
            
            # If successful, cache and return the result
            if result.get("success", False):
                self._cache_result(cache_key, result)
                return result
                
            # If primary adapter fails, log the error
            logger.warning(f"Primary adapter failed for task '{task}': {result.get('error', 'Unknown error')}")
            
        except Exception as e:
            logger.error(f"Error using primary adapter for task '{task}': {str(e)}")
            
        # Try the fallback adapter if the primary fails
        try:
            logger.info(f"Falling back to secondary adapter: {type(fallback_adapter).__name__}")
            result = await fallback_adapter.complete(task, content, **kwargs)
            
            # Cache and return the result if successful
            if result.get("success", False):
                # Include a note that this is from the fallback adapter
                result["note"] = "Result from fallback adapter"
                self._cache_result(cache_key, result)
                return result
                
            # If fallback also fails, log the error
            logger.error(f"Fallback adapter failed for task '{task}': {result.get('error', 'Unknown error')}")
            
        except Exception as e:
            logger.error(f"Error using fallback adapter for task '{task}': {str(e)}")
        
        # If both adapters fail, return an error
        error_result = {
            "success": False,
            "error": "Both primary and fallback adapters failed",
            "task": task
        }
        return error_result
