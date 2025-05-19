"""
URL Retrieval Step - Fetches content from URLs.
"""
import logging
import requests
from urllib.parse import urlparse
from .base_step import BaseStep

# Set up logging
logger = logging.getLogger(__name__)

class URLRetrievalStep(BaseStep):
    """Step for retrieving content from a URL."""
    
    def __init__(self):
        super().__init__()
        self.description = "Retrieves raw content from a URL"
        self.timeout = 30  # seconds
        self.max_content_size = 10 * 1024 * 1024  # 10MB limit by default
        
    def validate_input(self, input_data):
        """Validate URL input."""
        if not input_data or not isinstance(input_data, dict):
            logger.error("Invalid input: Input must be a dictionary")
            return False
            
        if 'url' not in input_data:
            logger.error("Invalid input: 'url' key is required")
            return False
            
        url = input_data['url']
        if not url or not isinstance(url, str):
            logger.error(f"Invalid URL: {url}")
            return False
            
        # Basic URL validation
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            logger.error(f"Invalid URL format: {url}")
            return False
            
        return True
        
    def process(self, input_data):
        """
        Retrieve content from the specified URL.
        
        Args:
            input_data: Dict containing 'url' key
            
        Returns:
            dict: Results containing status, content, and metadata
        """
        # Validate input
        if not self.validate_input(input_data):
            return self.get_error_result('Invalid URL input', input_data)
            
        url = input_data['url']
        logger.info(f"Retrieving content from URL: {url}")
        
        try:
            # Stream the response to handle large content
            with requests.get(
                url, 
                timeout=self.timeout,
                stream=True,
                headers={
                    'User-Agent': 'ProEthica Case Processor/1.0'
                }
            ) as response:
                # Check status code
                response.raise_for_status()
                
                # Check content type before downloading
                content_type = response.headers.get('Content-Type', '')
                
                # Initialize content as bytes
                content_bytes = b''
                content_size = 0
                
                # Stream content with size limit
                for chunk in response.iter_content(chunk_size=8192):
                    content_bytes += chunk
                    content_size += len(chunk)
                    
                    # Check size limit
                    if content_size > self.max_content_size:
                        return self.get_error_result(
                            f"Content exceeds maximum size limit of {self.max_content_size} bytes",
                            {'url': url, 'content_size': content_size}
                        )
                
                # Try to decode with detected encoding or utf-8
                encoding = response.encoding or 'utf-8'
                try:
                    content_text = content_bytes.decode(encoding)
                except UnicodeDecodeError:
                    # Fallback to utf-8 with error handling
                    content_text = content_bytes.decode('utf-8', errors='replace')
                
                # Successful result
                return {
                    'status': 'success',
                    'url': url,
                    'content': content_text,
                    'raw_content': content_bytes,
                    'content_type': content_type,
                    'content_length': content_size,
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'encoding': encoding
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout retrieving URL: {url}")
            return self.get_error_result(f"Request timed out after {self.timeout} seconds", {'url': url})
            
        except requests.exceptions.TooManyRedirects:
            logger.error(f"Too many redirects for URL: {url}")
            return self.get_error_result("Too many redirects", {'url': url})
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error retrieving URL {url}: {str(e)}")
            return self.get_error_result(
                f"HTTP Error: {response.status_code}", 
                {'url': url, 'status_code': response.status_code}
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving URL {url}: {str(e)}")
            return self.get_error_result(str(e), {'url': url})
