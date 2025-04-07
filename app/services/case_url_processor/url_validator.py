"""
URL validation and preprocessing for the Case URL Processor.

This module provides functionality for validating URLs and performing
basic preprocessing before content extraction.
"""

import re
import logging
from urllib.parse import urlparse
import requests

# Set up logging
logger = logging.getLogger(__name__)

class UrlValidator:
    """
    Validator for URLs to ensure they can be processed.
    """
    
    def __init__(self):
        """Initialize the URL validator."""
        # Regular expression for validating URLs
        self.url_regex = re.compile(
            r'^(?:http|https)://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IP
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        # Known domains for NSPE cases
        self.nspe_domains = [
            'nspe.org',
            'www.nspe.org'
        ]
    
    def validate(self, url, check_reachability=True):
        """
        Validate a URL format and optionally check if it's reachable.
        
        Args:
            url: The URL to validate
            check_reachability: Whether to check if the URL is reachable
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Basic format validation
            if not self.url_regex.match(url):
                logger.warning(f"Invalid URL format: {url}")
                return False
            
            # Check if it's a known NSPE URL
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            is_nspe = any(domain.endswith(nspe_domain) for nspe_domain in self.nspe_domains)
            
            # Check reachability if requested
            if check_reachability:
                try:
                    # Use a HEAD request to minimize data transfer
                    response = requests.head(
                        url, 
                        timeout=10,
                        headers={'User-Agent': 'ProEthica-URLProcessor/1.0'}
                    )
                    if response.status_code >= 400:
                        logger.warning(f"URL not reachable (status {response.status_code}): {url}")
                        return False
                except requests.RequestException as e:
                    logger.warning(f"Error checking URL reachability: {url}, {str(e)}")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"Error validating URL: {url}, {str(e)}")
            return False
    
    def get_domain_info(self, url):
        """
        Get information about the URL's domain.
        
        Args:
            url: The URL to analyze
            
        Returns:
            Dictionary with domain information
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        # Check if it's a known NSPE URL
        is_nspe = any(domain.endswith(nspe_domain) for nspe_domain in self.nspe_domains)
        
        return {
            'domain': domain,
            'is_nspe': is_nspe,
            'path': parsed_url.path,
            'scheme': parsed_url.scheme
        }
