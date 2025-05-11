"""
Material Service for REALM.

This module provides services for working with materials in the REALM application.
"""

import logging
from typing import Dict, List, Any, Optional, Union
import json
import os
from pathlib import Path
import time

# Import models
from realm.models import Material

# Import services
from realm.services.mseo_service import mseo_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MaterialService:
    """Service for managing materials."""
    
    def __init__(self, cache_dir: str = None):
        """Initialize the service.
        
        Args:
            cache_dir: Directory for caching material data
        """
        # Set cache directory
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            # Default to a cache directory in the current directory
            self.cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
        
        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize cache
        self.material_cache = {}
    
    def search_materials(self, query: str, use_cache: bool = True) -> List[Material]:
        """Search for materials.
        
        Args:
            query: Search query
            use_cache: Whether to use cached results
            
        Returns:
            List of materials
        """
        # Check cache first
        cache_key = f"search_{query.lower().replace(' ', '_')}"
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.json")
        
        if use_cache and os.path.exists(cache_path):
            try:
                with open(cache_path, "r") as f:
                    cache_data = json.load(f)
                
                # Check if cache is still valid (less than 1 day old)
                if time.time() - cache_data.get("timestamp", 0) < 86400:
                    logger.info(f"Using cached search results for '{query}'")
                    return [Material.from_dict(item) for item in cache_data.get("results", [])]
            except Exception as e:
                logger.warning(f"Error reading cache file: {e}")
        
        # Perform search via MCP service
        material_dicts = mseo_service.search_materials(query)
        
        # Convert to Material objects
        materials = []
        for material_dict in material_dicts:
            material = Material.from_dict(material_dict)
            
            # Add to cache
            self.material_cache[material.uri] = material
            
            # Add to results
            materials.append(material)
        
        # Save results to cache
        try:
            with open(cache_path, "w") as f:
                json.dump({
                    "timestamp": time.time(),
                    "results": [material.to_dict() for material in materials]
                }, f)
        except Exception as e:
            logger.warning(f"Error writing cache file: {e}")
        
        return materials
    
    def get_material(self, uri: str, use_cache: bool = True) -> Optional[Material]:
        """Get a material by URI.
        
        Args:
            uri: URI of the material
            use_cache: Whether to use cached data
            
        Returns:
            Material if found, None otherwise
        """
        # Check in-memory cache first
        if uri in self.material_cache and use_cache:
            return self.material_cache[uri]
        
        # Check file cache
        cache_key = f"material_{uri.split('/')[-1].split('#')[-1]}"
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.json")
        
        if use_cache and os.path.exists(cache_path):
            try:
                with open(cache_path, "r") as f:
                    material_data = json.load(f)
                
                # Check if cache is still valid (less than 1 day old)
                if time.time() - material_data.get("timestamp", 0) < 86400:
                    logger.info(f"Using cached material data for '{uri}'")
                    material = Material.from_dict(material_data.get("material", {}))
                    self.material_cache[uri] = material
                    return material
            except Exception as e:
                logger.warning(f"Error reading cache file: {e}")
        
        # Get material data from MCP service
        material_data = mseo_service.get_material_details(uri)
        if not material_data:
            return None
        
        # Get properties
        properties_data = mseo_service.get_material_properties(uri)
        if properties_data:
            material_data["properties"] = properties_data
        
        # Create Material object
        material = Material.from_dict(material_data)
        
        # Add to cache
        self.material_cache[uri] = material
        
        # Save to file cache
        try:
            with open(cache_path, "w") as f:
                json.dump({
                    "timestamp": time.time(),
                    "material": material.to_dict()
                }, f)
        except Exception as e:
            logger.warning(f"Error writing cache file: {e}")
        
        return material
    
    def get_categories(self) -> List[Dict[str, str]]:
        """Get a list of material categories.
        
        Returns:
            List of categories
        """
        return mseo_service.get_categories()
    
    def compare_materials(self, uri1: str, uri2: str) -> Dict[str, Any]:
        """Compare two materials.
        
        Args:
            uri1: URI of the first material
            uri2: URI of the second material
            
        Returns:
            Comparison results
        """
        return mseo_service.compare_materials(uri1, uri2)
    
    def clear_cache(self, uri: str = None) -> None:
        """Clear the material cache.
        
        Args:
            uri: URI of the material to clear, or None to clear all
        """
        if uri:
            # Clear specific material
            if uri in self.material_cache:
                del self.material_cache[uri]
            
            # Clear file cache
            cache_key = f"material_{uri.split('/')[-1].split('#')[-1]}"
            cache_path = os.path.join(self.cache_dir, f"{cache_key}.json")
            
            if os.path.exists(cache_path):
                try:
                    os.remove(cache_path)
                    logger.info(f"Cleared cache for material: {uri}")
                except Exception as e:
                    logger.warning(f"Error removing cache file: {e}")
        else:
            # Clear all
            self.material_cache = {}
            
            # Clear all file caches
            try:
                for cache_file in Path(self.cache_dir).glob("*.json"):
                    os.remove(cache_file)
                logger.info("Cleared all material caches")
            except Exception as e:
                logger.warning(f"Error clearing cache files: {e}")
    
    def chat_about_materials(self, message: str, conversation_history: List[Dict[str, str]] = None) -> str:
        """Generate a response about materials using the ontology.
        
        Args:
            message: User message
            conversation_history: Previous conversation messages
            
        Returns:
            Response text
        """
        return mseo_service.chat_with_context(message, conversation_history)

# Create a singleton instance
material_service = MaterialService()
