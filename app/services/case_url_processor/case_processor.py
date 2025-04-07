"""
Main Case URL Processor orchestrator.

This module provides the main orchestrator class (CaseUrlProcessor)
which ties together all the components of the URL processing pipeline.
"""

import logging
import time
import re
from typing import Dict, Any, Optional
import os
import json

from flask_login import current_user

from .url_validator import UrlValidator
from .content_extractor import ContentExtractor
from .patterns.nspe_patterns import NSPEPatternMatcher
from .llm_extractor import LlmExtractor
from .triple_generator import TripleGenerator
from .case_cache import UrlProcessingCache
from .correction_handler import CorrectionHandler

# Set up logging
logger = logging.getLogger(__name__)

class CaseUrlProcessor:
    """
    Main orchestrator for processing case URLs.
    """
    
    def __init__(self, use_cache=True, llm_provider='claude'):
        """
        Initialize the case URL processor.
        
        Args:
            use_cache: Whether to use the URL processing cache
            llm_provider: LLM provider to use ('claude' or 'local')
        """
        self.validator = UrlValidator()
        self.extractor = ContentExtractor()
        self.pattern_matcher = NSPEPatternMatcher()
        self.llm_extractor = LlmExtractor(provider=llm_provider)
        self.triple_generator = TripleGenerator()
        self.cache = UrlProcessingCache() if use_cache else None
        self.correction_handler = CorrectionHandler()
        
        # Create cache directory
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """
        Ensure the cache directory exists.
        """
        cache_dir = os.path.join('app', 'data', 'cache')
        os.makedirs(cache_dir, exist_ok=True)
    
    def process_url(self, url, world_id=None, user_id=None):
        """
        Process a URL to extract case information.
        
        Args:
            url: URL to process
            world_id: ID of the world (optional)
            user_id: ID of the user processing the URL (optional)
            
        Returns:
            Dictionary with processing results
        """
        # Use Flask current_user if available and user_id not provided
        if user_id is None and current_user and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            user_id = current_user.id
            
        # Check cache first if enabled
        if self.cache and self.cache.has_url(url):
            logger.info(f"Using cached result for URL: {url}")
            result = self.cache.get_processed_result(url)
            
            # Add cached status to result
            if result:
                result['cached'] = True
                
            return result
        
        # Validate URL
        if not self.validator.validate(url):
            logger.warning(f"Invalid URL: {url}")
            return {
                "status": "error",
                "message": "Invalid URL format or URL not reachable",
                "url": url
            }
        
        # Process the URL using the extraction pipeline
        try:
            logger.info(f"Processing URL: {url}")
            
            # Extract content
            logger.info("Extracting HTML content")
            html_content = self.extractor.extract_html(url)
            
            # Clean content
            logger.info("Cleaning content")
            cleaned_content = self.extractor.clean_content(html_content)
            
            # Extract metadata using patterns
            logger.info("Extracting metadata using patterns")
            metadata = self.pattern_matcher.extract_metadata(
                cleaned_content,
                html_content,
                url
            )
            
            # Add related cases
            metadata['related_cases'] = self.pattern_matcher.extract_related_cases(cleaned_content)
            
            # Add outcome if not already extracted
            if 'outcome' not in metadata:
                metadata['outcome'] = self.pattern_matcher.extract_outcome(cleaned_content)
            
            # Add board decision analysis
            metadata['board_analysis'] = self.pattern_matcher.analyze_board_decision(cleaned_content)
            
            # Extract structured data using LLM
            logger.info("Extracting structured data using LLM")
            llm_structured_data = self.llm_extractor.extract_case_data(
                cleaned_content,
                metadata,
                world_id
            )
            
            # Generate triples
            logger.info("Generating RDF triples")
            triples = self.triple_generator.generate_triples(
                llm_structured_data,
                world_id
            )
            
            # Extract title from HTML
            html_title = self.extractor.extract_title(html_content, url)
            
            # Determine if this is a regular webpage or an NSPE case
            is_nspe_case = 'nspe.org' in url and ('/ethics/' in url or '/resources/ethics/' in url or '/board-ethical-review/' in url)
            
            # Title priority logic:
            # 1. For NSPE cases, prefer LLM title if it contains a case number
            # 2. Otherwise prefer HTML title
            # 3. Fall back to pattern metadata
            # 4. Last resort: URL-based title
            if is_nspe_case and llm_structured_data.get("title") and re.search(r'Case\s+\d+-\d+', llm_structured_data.get("title", ""), re.IGNORECASE):
                title = llm_structured_data.get("title")
            elif html_title and len(html_title) > 5:
                title = html_title
            elif metadata.get("title"):
                title = metadata.get("title")
            else:
                # Extract from URL
                url_path = url.rstrip('/').split('/')[-1]
                if url_path:
                    title = ' '.join(word.capitalize() for word in url_path.replace('-', ' ').split())
                else:
                    title = "Untitled Case"
            
            # Validate content isn't empty
            if not cleaned_content or len(cleaned_content.strip()) < 100:
                logger.warning(f"Extracted content too short: {len(cleaned_content) if cleaned_content else 0} chars")
                # Try to extract content again with less filtering
                cleaned_content = self.extractor.clean_content(html_content, aggressive=False)
                
                if not cleaned_content or len(cleaned_content.strip()) < 100:
                    logger.error("Content extraction failed completely")
                    cleaned_content = f"Content extraction failed. Please visit the original URL: {url}"
            
            # Prepare final result
            result = {
                "url": url,
                "title": title,
                "content": cleaned_content,
                "metadata": llm_structured_data,
                "pattern_metadata": metadata,  # Keep original pattern metadata for reference
                "triples": triples,
                "processing_time": time.time(),
                "processing_method": "automatic",
                "world_id": world_id,
                "cached": False
            }
            
            # Cache result if enabled
            if self.cache:
                logger.info(f"Caching result for URL: {url}")
                self.cache.cache_result(url, result, user_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing URL: {url}, {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error processing URL: {str(e)}",
                "url": url
            }
    
    def apply_correction(self, url, corrections, user_id=None):
        """
        Apply corrections to processed URL result.
        
        Args:
            url: URL to apply corrections to
            corrections: Corrections to apply
            user_id: ID of the user making corrections (optional)
            
        Returns:
            Corrected result
        """
        # Get original result
        original_result = None
        
        # Try to get from cache first
        if self.cache and self.cache.has_url(url):
            original_result = self.cache.get_processed_result(url)
        
        # If not in cache, process the URL
        if not original_result:
            original_result = self.process_url(url, original_result.get('world_id'), user_id)
        
        # Apply corrections
        corrected_result = self.correction_handler.apply_corrections(
            original_result,
            corrections,
            user_id
        )
        
        # Update cache if enabled
        if self.cache:
            self.cache.cache_result(url, corrected_result, user_id)
        
        return corrected_result
    
    def get_correction_fields(self, url, world_id=None, user_id=None):
        """
        Get fields available for correction for a URL.
        
        Args:
            url: URL to get correction fields for
            world_id: ID of the world (optional)
            user_id: ID of the user (optional)
            
        Returns:
            Dictionary of field types and current values
        """
        # Process URL if needed
        result = None
        
        # Try to get from cache first
        if self.cache and self.cache.has_url(url):
            result = self.cache.get_processed_result(url)
        
        # If not in cache, process the URL
        if not result:
            result = self.process_url(url, world_id, user_id)
        
        # Get correction fields
        return self.correction_handler.get_correction_fields(result)
