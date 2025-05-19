"""
NSPE Case Extraction Step - Extracts structured content from NSPE case HTML.
"""
import logging
import re
import requests
from bs4 import BeautifulSoup
from .base_step import BaseStep

# Set up logging
logger = logging.getLogger(__name__)

class NSPECaseExtractionStep(BaseStep):
    """Step for extracting structured content from NSPE case HTML."""
    
    def __init__(self):
        super().__init__()
        self.description = "Extracts structured content from NSPE case HTML"
        
    def validate_input(self, input_data):
        """Validate that the input contains HTML content."""
        if not input_data or not isinstance(input_data, dict):
            logger.error("Invalid input: Input must be a dictionary")
            return False
            
        if 'content' not in input_data:
            logger.error("Invalid input: 'content' key is required")
            return False
            
        content = input_data.get('content', '')
        if not content or not isinstance(content, str):
            logger.error("Invalid content: Empty or not a string")
            return False
            
        # Check if content appears to be HTML
        if '<html' not in content.lower() and '<body' not in content.lower() and '<div' not in content.lower():
            logger.warning("Content may not be HTML, but will try to process anyway")
            
        return True
        
    def get_error_result(self, message, details=None):
        """Return a standardized error result."""
        return {
            'status': 'error',
            'message': message,
            'details': details or {}
        }
        
    def extract_pdf_url(self, soup, url):
        """Extract PDF URL from the page."""
        # Try to find PDF links
        pdf_links = soup.find_all('a', href=lambda href: href and href.lower().endswith('.pdf'))
        
        if pdf_links:
            pdf_url = pdf_links[0]['href']
            # If it's a relative URL, convert to absolute
            if pdf_url.startswith('/'):
                # Extract the base URL
                parts = url.split('/')
                base_url = '/'.join(parts[:3])  # http(s)://domain.com
                pdf_url = base_url + pdf_url
            return pdf_url
        
        return None
        
    def extract_case_number(self, soup):
        """Extract case number from the page."""
        # Method 1: Look for the case number in the specific div structure
        case_number_div = soup.find('div', class_='field--name-field-case-number')
        if case_number_div:
            field_item = case_number_div.find('div', class_='field__item')
            if field_item:
                case_text = field_item.get_text().strip()
                case_number_match = re.search(r'Case\s+(\d{1,2}-\d{1,2})', case_text)
                if case_number_match:
                    return case_number_match.group(1)
                return case_text.replace('Case', '').strip()
        
        # Method 2: Look for "BER Case XX-X" pattern
        content_text = soup.get_text()
        case_number_match = re.search(r'BER\s+Case\s+(\d{1,2}-\d{1,2})', content_text)
        if case_number_match:
            return case_number_match.group(1)
        
        # Method 3: Look in the title
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text()
            case_number_match = re.search(r'Case\s+(\d{1,2}-\d{1,2})', title_text)
            if case_number_match:
                return case_number_match.group(1)
        
        # Method 4: Look in heading elements
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for heading in headings:
            heading_text = heading.get_text()
            case_number_match = re.search(r'Case\s+(\d{1,2}-\d{1,2})', heading_text)
            if case_number_match:
                return case_number_match.group(1)
        
        return None
        
    def extract_year(self, soup, case_number):
        """Extract year from the page or case number."""
        # If case number exists and has year format (e.g., 23-4 for 2023)
        if case_number:
            year_prefix = case_number.split('-')[0]
            if len(year_prefix) == 2:
                # Assume 20xx for modern cases, 19xx for older
                century = "20" if int(year_prefix) < 50 else "19"
                return century + year_prefix
                
        # Look for a year pattern in the text
        content_text = soup.get_text()
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', content_text)
        if year_match:
            return year_match.group(1)
            
        return None
        
    def extract_facts_section(self, soup):
        """Extract the facts section using specific HTML structure."""
        facts_div = soup.find('div', class_='field--name-field-case-facts')
        if facts_div:
            # Extract all text content from the facts div
            facts_content = facts_div.get_text(separator='\n', strip=True)
            # Remove the "Facts" label if it exists at the beginning
            facts_content = re.sub(r'^Facts\s*', '', facts_content)
            return facts_content.strip()
        return None
        
    def extract_section(self, soup, start_marker, end_markers=None):
        """
        Extract content between a start marker and any of the end markers.
        
        Args:
            soup: BeautifulSoup object
            start_marker: Text marking the beginning of the section
            end_markers: List of texts marking possible ends of the section
            
        Returns:
            str: Extracted section content or None if not found
        """
        # Convert to lowercase for case-insensitive comparison
        start_marker_lower = start_marker.lower()
        end_markers_lower = [marker.lower() for marker in end_markers] if end_markers else []
        
        # Get the full text
        content_text = soup.get_text()
        paragraphs = [p.get_text().strip() for p in soup.find_all('p')]
        
        # Try to find the section using paragraph markers
        start_idx = None
        for i, para in enumerate(paragraphs):
            if start_marker_lower in para.lower():
                start_idx = i
                break
                
        if start_idx is not None:
            # Find the end marker
            end_idx = None
            for i in range(start_idx+1, len(paragraphs)):
                if any(marker in paragraphs[i].lower() for marker in end_markers_lower):
                    end_idx = i
                    break
                    
            if end_idx:
                # Join paragraphs from start to end
                return '\n'.join(paragraphs[start_idx:end_idx])
            else:
                # If no end marker found, return from start to end
                return '\n'.join(paragraphs[start_idx:])
                
        # If paragraph approach fails, try using the raw text
        start_pos = -1
        for marker in [start_marker, start_marker.title(), start_marker.upper()]:
            start_pos = content_text.find(marker)
            if start_pos >= 0:
                start_pos += len(marker)
                break
                
        if start_pos >= 0:
            # Find the first end marker
            end_pos = len(content_text)
            if end_markers:
                for end_marker in end_markers:
                    for variant in [end_marker, end_marker.title(), end_marker.upper()]:
                        pos = content_text.find(variant, start_pos)
                        if pos >= 0 and pos < end_pos:
                            end_pos = pos
                            break
                            
            return content_text[start_pos:end_pos].strip()
            
        return None
        
    def clean_section_text(self, text):
        """Clean up extracted section text."""
        if not text:
            return ""
            
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove any HTML tags that might remain
        text = re.sub(r'<[^>]+>', '', text)
        
        # Clean up any remaining special characters
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        
        return text.strip()
        
    def process(self, input_data):
        """
        Extract structured content from NSPE case HTML.
        
        Args:
            input_data: Dict containing 'content' key with HTML
            
        Returns:
            dict: Results containing extracted case components
        """
        # Validate input
        if not self.validate_input(input_data):
            return self.get_error_result('Invalid input', input_data)
            
        # Get HTML content and URL
        html_content = input_data.get('content', '')
        url = input_data.get('url', '')
        
        try:
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract case metadata
            pdf_url = self.extract_pdf_url(soup, url)
            case_number = self.extract_case_number(soup)
            year = self.extract_year(soup, case_number)
            
            # Extract major sections
            facts = self.extract_facts_section(soup)
            if not facts:
                facts = self.extract_section(soup, "Facts:", ["Question:", "Questions:", "Reference:", "References:", "Discussion:", "Conclusion:", "Conclusions:"])
            question = self.extract_section(soup, "Question:", ["Reference:", "References:", "Discussion:", "Conclusion:", "Conclusions:"])
            if not question:
                question = self.extract_section(soup, "Questions:", ["Reference:", "References:", "Discussion:", "Conclusion:", "Conclusions:"])
                
            references = self.extract_section(soup, "Reference:", ["Discussion:", "Conclusion:", "Conclusions:"])
            if not references:
                references = self.extract_section(soup, "References:", ["Discussion:", "Conclusion:", "Conclusions:"])
                
            discussion = self.extract_section(soup, "Discussion:", ["Conclusion:", "Conclusions:"])
            conclusion = self.extract_section(soup, "Conclusion:", [])
            if not conclusion:
                conclusion = self.extract_section(soup, "Conclusions:", [])
                
            # Clean sections
            facts = self.clean_section_text(facts)
            question = self.clean_section_text(question)
            references = self.clean_section_text(references)
            discussion = self.clean_section_text(discussion)
            conclusion = self.clean_section_text(conclusion)
            
            # Extract title
            title = None
            # First try to find the specific title span
            title_span = soup.find('span', class_='single-node-title')
            if title_span:
                title = title_span.get_text().strip()
            
            if not title:
                # Try title tag, but remove "| National Society of Professional Engineers" part
                title_tag = soup.find('title')
                if title_tag:
                    title_text = title_tag.get_text().strip()
                    # Remove the organization suffix if present
                    if '|' in title_text:
                        title = title_text.split('|')[0].strip()
                    else:
                        title = title_text
            
            if not title:
                # Try to get from the first heading
                heading = soup.find(['h1', 'h2'])
                if heading:
                    title = heading.get_text().strip()
            
            # Return structured result
            return {
                'status': 'success',
                'url': url,
                'title': title,
                'case_number': case_number,
                'year': year,
                'pdf_url': pdf_url,
                'sections': {
                    'facts': facts,
                    'question': question,
                    'references': references,
                    'discussion': discussion,
                    'conclusion': conclusion
                },
                'raw_content': html_content  # Include the original content
            }
                
        except Exception as e:
            logger.error(f"Error extracting NSPE case content: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return self.get_error_result(f"Error extracting case content: {str(e)}")
