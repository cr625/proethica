"""
NSPE Case Scraper
----------------
Extracts engineering ethics case content from NSPE website URLs.

This module handles:
1. Scraping case content from NSPE website URLs
2. Parsing the HTML to extract structured case data
3. Handling different NSPE website formats over time
4. Extracting case metadata (number, title, year, etc.)
"""

import re
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import sys
import os
from datetime import datetime

# Add parent directory to path to import config
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from config import NSPE_BASE_URL, NSPE_CASE_PATTERN, NSPE_CASE_TIMEOUT, CASE_SECTION_MARKERS

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("nspe_case_scraper")

class NSPECaseScraper:
    """Scraper for NSPE ethics cases from their website."""
    
    def __init__(self):
        """Initialize the scraper."""
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def scrape_case_from_url(self, url):
        """
        Scrape a case from a given URL.
        
        Args:
            url: The URL of the NSPE case
            
        Returns:
            dict: A dictionary containing the case data
        """
        try:
            logger.info(f"Scraping case from URL: {url}")
            
            # Make the request with a timeout
            response = self.session.get(url, headers=self.headers, timeout=NSPE_CASE_TIMEOUT)
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract case data
            case_data = self._extract_case_data(soup, url)
            
            if not case_data:
                logger.error(f"Failed to extract case data from {url}")
                return None
                
            logger.info(f"Successfully scraped case: {case_data.get('title')} (Case #{case_data.get('case_number')})")
            return case_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error scraping {url}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            return None
    
    def _extract_case_data(self, soup, url):
        """
        Extract case data from the parsed HTML.
        
        Args:
            soup: BeautifulSoup object
            url: The original URL
            
        Returns:
            dict: A dictionary containing the case data
        """
        # Initialize case data
        case_data = {
            "title": None,
            "case_number": None,
            "year": None,
            "full_text": None,
            "sections": {},
            "url": url,
            "metadata": {
                "scraped_at": datetime.now().isoformat()
            }
        }
        
        # Extract the main content first
        # NSPE site has evolved over time, so we need to handle different formats
        content = None
        
        # Try the article content first (newer format)
        article = soup.find('article')
        if article:
            content = article
        
        # Try content div (common in many formats)
        if not content:
            content = soup.find('div', class_='content')
            
        # Try main content div (another common pattern)
        if not content:
            content = soup.find('div', id='main-content')
        
        # If still not found, try other common patterns
        if not content:
            content = soup.find('div', class_='node__content')
        
        if not content:
            # Last resort: get the body
            content = soup.find('body')
            
        # Remove unwanted elements like navigation, footers, etc.
        if content:
            for unwanted in content.find_all(['nav', 'footer', 'script', 'style', 'meta']):
                unwanted.decompose()
        
        # Extract title using a multi-strategy approach
        
        # First try: Extract from URL if it's descriptive (often the most reliable for NSPE)
        if url:
            url_parts = url.strip('/').split('/')
            if len(url_parts) > 0:
                last_part = url_parts[-1]
                # Convert hyphens to spaces and capitalize words
                if len(last_part) > 5 and '-' in last_part and 'nspe' not in last_part.lower():
                    url_title = ' '.join(word.capitalize() for word in last_part.split('-'))
                    case_data["title"] = url_title
        
        # Second try: Look for a title in the page metadata
        if not case_data["title"] or len(case_data["title"].split()) < 2:
            meta_title = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name': 'title'})
            if meta_title and meta_title.get('content'):
                potential_title = meta_title.get('content')
                if "NSPE" in potential_title and "utility" not in potential_title.lower():
                    case_data["title"] = potential_title.strip()
        
        # Third try: Look for heading with case number pattern
        if not case_data["title"] or len(case_data["title"].split()) < 2:
            for header in soup.find_all(['h1', 'h2', 'h3', 'h4']):
                header_text = header.text.strip()
                # Skip empty or very short headers
                if len(header_text) < 3:
                    continue
                
                # Skip utility headers
                parent_classes = ' '.join([str(p.get('class', '')) for p in header.parents if p.get('class')])
                if any(term in parent_classes.lower() for term in ['nav', 'menu', 'utility', 'header', 'footer', 'sidebar']):
                    continue
                
                # If header contains "case" or matches case number pattern, use it
                if re.search(NSPE_CASE_PATTERN, header_text) or "case" in header_text.lower():
                    case_data["title"] = header_text
                    break
        
        # Fourth try: Look for a main heading in the content
        if not case_data["title"] or len(case_data["title"].split()) < 2:
            if content:
                main_header = content.find(['h1', 'h2'])
                if main_header and len(main_header.text.strip()) > 3 and "utility" not in main_header.text.lower():
                    case_data["title"] = main_header.text.strip()
                
        # Fifth try: Look for the page title
        if not case_data["title"] or len(case_data["title"].split()) < 2:
            page_title = soup.find('title')
            if page_title and "NSPE" in page_title.text:
                title_text = page_title.text.strip()
                # Remove website name if present
                title_parts = title_text.split('|')
                if len(title_parts) > 1:
                    case_data["title"] = title_parts[0].strip()
                else:
                    case_data["title"] = title_text
        
        # Verify title quality
        if case_data["title"] and (len(case_data["title"].split()) < 2 or case_data["title"].startswith("I.")):
            # Title is likely not descriptive enough, try to extract a better one
            # Look for strong text in the first few paragraphs that might be a title
            if content:
                for p in content.find_all('p')[:3]:
                    strong = p.find('strong')
                    if strong and len(strong.text) > 10 and len(strong.text.split()) > 2:
                        case_data["title"] = strong.text.strip()
                        break
        
        # Look for NSPE Case number pattern in title or content
        case_number_match = None
        if case_data["title"]:
            case_number_match = re.search(NSPE_CASE_PATTERN, case_data["title"])
            
        # If not found in title, look in content
        if not case_number_match and content:
            case_number_text = content.get_text()
            case_number_match = re.search(NSPE_CASE_PATTERN, case_number_text)
        
        # Extract case number if found
        if case_number_match:
            case_data["case_number"] = case_number_match.group(1)
            
            # Try to extract year from case number (usually last part)
            year_parts = case_data["case_number"].split("-")
            if len(year_parts) > 0 and len(year_parts[-1]) == 2:
                # Convert 2-digit year to 4-digit
                year = int(year_parts[-1])
                if year < 50:  # Assume 2000+
                    case_data["year"] = f"20{year_parts[-1]}"
                else:  # Assume 1900+
                    case_data["year"] = f"19{year_parts[-1]}"
        
        # Extract the full text with preserved formatting
        if content:
            # Try extracting content with preserved formatting
            case_data["full_text"] = self._extract_formatted_text(content)
            
            # Try to extract sections
            self._extract_sections(case_data)
        
        # If we couldn't find a title, try to generate one
        if not case_data["title"]:
            if case_data["case_number"]:
                case_data["title"] = f"NSPE Case {case_data['case_number']}"
            elif case_data["full_text"]:
                # Try to extract a title from the first paragraph
                first_paragraph = case_data["full_text"].split('\n')[0]
                if len(first_paragraph) > 10 and len(first_paragraph) < 200:
                    case_data["title"] = first_paragraph.strip()
                else:
                    # Extract first sentence as title
                    first_sentence = re.split(r'[.!?]', case_data["full_text"])[0]
                    if len(first_sentence) > 10 and len(first_sentence) < 100:
                        case_data["title"] = first_sentence.strip()
                    else:
                        case_data["title"] = "NSPE Ethics Case"
        
        # Make sure we have minimal required data
        if not case_data["title"] or not case_data["full_text"]:
            logger.warning(f"Missing critical case data: title={case_data['title'] is not None}, text={case_data['full_text'] is not None}")
            return None
            
        return case_data
    
    def _extract_formatted_text(self, element):
        """
        Extract text with preserved formatting from an HTML element.
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            str: Formatted text
        """
        # Process the element to preserve formatting
        formatted_text = ""
        
        # Process element children to preserve structure
        for child in element.children:
            if child.name == 'p':
                # Paragraphs become text + double newline
                formatted_text += self._get_element_text(child) + "\n\n"
            elif child.name == 'br':
                # <br> tags become single newlines
                formatted_text += "\n"
            elif child.name in ['div', 'section', 'article']:
                # Container elements - process their content
                formatted_text += self._extract_formatted_text(child)
            elif child.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                # Headings get newlines before and after + uppercase
                heading_text = self._get_element_text(child).strip()
                formatted_text += f"\n{heading_text}\n\n"
            elif child.name == 'ul' or child.name == 'ol':
                # Lists - process each item
                formatted_text += "\n"
                for li in child.find_all('li', recursive=False):
                    formatted_text += f"• {self._get_element_text(li).strip()}\n"
                formatted_text += "\n"
            elif child.name is None:
                # Raw text nodes
                text = child.string
                if text and text.strip():
                    formatted_text += text
            else:
                # Other elements, just get text
                text = self._get_element_text(child)
                if text and text.strip():
                    formatted_text += text
                    
        # Clean up the formatted text
        return self._clean_text(formatted_text)
    
    def _get_element_text(self, element):
        """
        Get text from an element with basic formatting preservation.
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            str: Text with basic formatting
        """
        if element.name is None:
            return element.string or ""
            
        # Handle special elements
        if element.name == 'br':
            return "\n"
            
        # Get all text
        text = ""
        for content in element.contents:
            if content.name == 'br':
                text += "\n"
            elif content.string:
                text += content.string
            else:
                text += self._get_element_text(content)
                
        return text
        
    def _clean_text(self, text):
        """
        Clean up the extracted text while preserving important formatting.
        
        Args:
            text: The raw text
            
        Returns:
            str: The cleaned text
        """
        if not text:
            return ""
            
        # Replace multiple spaces with single space
        text = re.sub(r' {2,}', ' ', text)
        
        # Preserve paragraph breaks (double newlines)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Normalize single newlines that aren't paragraph breaks
        lines = text.split('\n')
        result_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                result_lines.append("")
                i += 1
                continue
                
            # Check if this line should continue the previous one
            if i > 0 and result_lines and result_lines[-1] and not result_lines[-1].endswith(('.', '!', '?', ':', '-', '•')):
                # If previous line doesn't end with sentence-ending punctuation or list marker,
                # it likely continues
                if not line.startswith('•') and not re.match(r'^[A-Z][a-z]', line):
                    # Append to previous line with space
                    result_lines[-1] += " " + line
                    i += 1
                    continue
            
            # Otherwise add as new line
            result_lines.append(line)
            i += 1
        
        # Rejoin with appropriate newlines
        text = '\n'.join(result_lines)
        
        # Remove common artifacts
        text = re.sub(r'© NSPE.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'National Society of Professional Engineers', '', text)
        
        return text.strip()
    
    def _extract_sections(self, case_data):
        """
        Extract structured sections from the case text.
        
        Args:
            case_data: Dict containing the case data with full_text
            
        Returns:
            None (modifies case_data in place)
        """
        if not case_data["full_text"]:
            return
            
        # Split the text by known section markers
        current_section = "preamble"
        sections = {current_section: []}
        
        for line in case_data["full_text"].split('\n'):
            found_marker = False
            
            for marker in CASE_SECTION_MARKERS:
                if marker in line or line.lower().startswith(marker.lower()):
                    current_section = marker.rstrip(':').lower()
                    sections[current_section] = [line]
                    found_marker = True
                    break
                    
            if not found_marker:
                sections[current_section].append(line)
        
        # Combine the lines in each section
        for section, lines in sections.items():
            if lines:
                sections[section] = '\n'.join(lines).strip()
            else:
                sections[section] = ""
        
        # Handle the description (usually the preamble section)
        if "preamble" in sections and sections["preamble"]:
            case_data["description"] = sections["preamble"]
            
        # Handle the decision (conclusion section)
        if "conclusion" in sections and sections["conclusion"]:
            case_data["decision"] = sections["conclusion"]
            
        # Store all structured sections in case metadata
        case_data["sections"] = sections


def scrape_case(url):
    """
    Scrape a case from a URL.
    
    Args:
        url: URL of the NSPE case
        
    Returns:
        dict: Case data
    """
    scraper = NSPECaseScraper()
    return scraper.scrape_case_from_url(url)


if __name__ == "__main__":
    # Simple command-line interface for testing
    if len(sys.argv) < 2:
        print("Usage: python nspe_case_scraper.py <case_url>")
        sys.exit(1)
        
    url = sys.argv[1]
    case = scrape_case(url)
    
    if case:
        print(f"Successfully scraped case: {case['title']} (Case #{case.get('case_number', 'N/A')})")
        print(f"Year: {case.get('year', 'Unknown')}")
        print(f"Sections found: {list(case['sections'].keys())}")
        print(f"Text length: {len(case['full_text'])} characters")
    else:
        print(f"Failed to scrape case from {url}")
        sys.exit(1)
