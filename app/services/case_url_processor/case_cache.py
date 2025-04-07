"""
Caching mechanism for the Case URL Processor.

This module provides functionality for caching processed URL results
to avoid redundant processing of the same URLs.
"""

import logging
import os
import json
import time
from typing import Dict, Any, Optional

# Set up logging
logger = logging.getLogger(__name__)

class UrlProcessingCache:
    """
    Cache for storing processed URL results.
    """
    
    def __init__(self, cache_dir=None, cache_file=None, expiry_days=30):
        """
        Initialize the URL processing cache.
        
        Args:
            cache_dir: Directory for cache file (default: app/data/cache)
            cache_file: Cache file name (default: url_processing_cache.json)
            expiry_days: Number of days before cache entries expire
        """
        # Set cache directory
        if cache_dir is None:
            cache_dir = os.path.join('app', 'data', 'cache')
        
        # Create cache directory if it doesn't exist
        os.makedirs(cache_dir, exist_ok=True)
        
        # Set cache file path
        if cache_file is None:
            cache_file = 'url_processing_cache.json'
        
        self.cache_file_path = os.path.join(cache_dir, cache_file)
        self.expiry_seconds = expiry_days * 24 * 60 * 60
        self.cache = self._load_cache()
    
    def _load_cache(self):
        """
        Load cache from file.
        
        Returns:
            Dictionary of cached results
        """
        try:
            if os.path.exists(self.cache_file_path):
                with open(self.cache_file_path, 'r') as f:
                    cache = json.load(f)
                logger.info(f"Loaded cache with {len(cache)} entries from {self.cache_file_path}")
                
                # Clean expired entries during load
                self._clean_expired_entries(cache)
                
                return cache
            else:
                logger.info(f"No cache file found at {self.cache_file_path}, creating new cache")
                return {}
        except Exception as e:
            logger.error(f"Error loading cache: {str(e)}")
            return {}
    
    def _save_cache(self):
        """
        Save cache to file.
        """
        try:
            # Clean expired entries before saving
            self._clean_expired_entries(self.cache)
            
            with open(self.cache_file_path, 'w') as f:
                json.dump(self.cache, f, indent=2)
            logger.info(f"Saved cache with {len(self.cache)} entries to {self.cache_file_path}")
        except Exception as e:
            logger.error(f"Error saving cache: {str(e)}")
    
    def _clean_expired_entries(self, cache_dict):
        """
        Remove expired entries from cache.
        
        Args:
            cache_dict: Cache dictionary to clean
        """
        now = time.time()
        expired_keys = []
        
        for url, entry in cache_dict.items():
            if 'timestamp' in entry and now - entry['timestamp'] > self.expiry_seconds:
                expired_keys.append(url)
        
        # Remove expired entries
        for key in expired_keys:
            del cache_dict[key]
        
        if expired_keys:
            logger.info(f"Removed {len(expired_keys)} expired cache entries")
    
    def has_url(self, url):
        """
        Check if URL is in the cache.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL is in cache, False otherwise
        """
        # First clean the cache
        self._clean_expired_entries(self.cache)
        
        # Check if URL is in cache
        return url in self.cache
    
    def get_processed_result(self, url):
        """
        Get cached result for a URL.
        
        Args:
            url: URL to get result for
            
        Returns:
            Cached result dictionary or None if not in cache
        """
        if not self.has_url(url):
            return None
        
        # Get result from cache
        result = self.cache.get(url, {}).get('result')
        
        # Update access timestamp
        if url in self.cache:
            self.cache[url]['last_accessed'] = time.time()
            self._save_cache()
        
        return result
    
    def cache_result(self, url, result, user_id=None):
        """
        Cache result for a URL.
        
        Args:
            url: URL to cache result for
            result: Result to cache
            user_id: ID of user who processed the URL (optional)
        """
        # Add result to cache
        self.cache[url] = {
            'result': result,
            'timestamp': time.time(),
            'last_accessed': time.time(),
            'user_id': user_id
        }
        
        # Save cache
        self._save_cache()
    
    def clear_cache(self):
        """
        Clear the entire cache.
        """
        self.cache = {}
        self._save_cache()
        logger.info("Cache cleared")
    
    def remove_url(self, url):
        """
        Remove a specific URL from the cache.
        
        Args:
            url: URL to remove
            
        Returns:
            True if URL was in cache and was removed, False otherwise
        """
        if url in self.cache:
            del self.cache[url]
            self._save_cache()
            return True
        return False
