#!/usr/bin/env python
"""
Script to clear the URL processing cache.

This script clears the URL processing cache used by the case_url_processor module.
"""

import os
import sys
import json
import argparse

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.case_url_processor.case_cache import UrlProcessingCache


def clear_cache(url=None):
    """
    Clear the URL processing cache.
    
    Args:
        url: Specific URL to remove from cache (optional)
    """
    cache = UrlProcessingCache()
    
    if url:
        # Remove specific URL
        if cache.remove_url(url):
            print(f"Removed URL from cache: {url}")
        else:
            print(f"URL not found in cache: {url}")
    else:
        # Clear entire cache
        cache.clear_cache()
        print("Cache cleared successfully")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clear the URL processing cache")
    parser.add_argument("--url", help="Specific URL to remove from cache")
    
    args = parser.parse_args()
    clear_cache(args.url)
