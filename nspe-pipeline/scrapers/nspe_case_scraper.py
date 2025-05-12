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
        
        # Extract the title - usually in a heading tag
        title_elem = soup.find(['h1', 'h2'])
        if title_elem:
            case_data["title"] = title_elem.text.strip()
        
        # Try to extract the case number from the title
        if case_data["title"]:
            case_number_match = re.search(NSPE_CASE_PATTERN, case_data["title"])
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
        
        # If case number not found in title, look elsewhere
        if not case_data["case_number"]:
            # Look for case number in the body text
            body_text = soup.get_text()
            case_number_match = re.search(NSPE_CASE_PATTERN, body_text)
            if case_number_match:
                case_data["case_number"] = case_number_match.group(1)
        
        # Extract the main content
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
        
        # Extract the full text
        if content:
            # Remove unwanted elements like navigation, footers, etc.
            for unwanted in content.find_all(['nav', 'footer', 'script', 'style', 'meta']):
                unwanted.decompose()
                
            # Get the clean text
            case_data["full_text"] = self._clean_text(content.get_text())
            
            # Try to extract sections
            self._extract_sections(case_data)
        
        # If we couldn't find a title, try to generate one
        if not case_data["title"] and case_data["case_number"]:
            case_data["title"] = f"NSPE Case {case_data['case_number']}"
            
            # Try to extract a better title from the first paragraph
            if case_data["full_text"]:
                first_paragraph = case_data["full_text"].split('\n')[0]
                if len(first_paragraph) > 10 and len(first_paragraph) < 200:
                    case_data["title"] = first_paragraph.strip()
        
        # Make sure we have minimal required data
        if not case_data["title"] or not case_data["full_text"]:
            logger.warning(f"Missing critical case data: title={case_data['title'] is not None}, text={case_data['full_text'] is not None}")
            return None
            
        return case_data
    
    def _clean_text(self, text):
        """
        Clean up the extracted text.
        
        Args:
            text: The raw text
            
        Returns:
            str: The cleaned text
        """
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        
        # Rejoin with single newlines
        text = '\n'.join(paragraphs)
        
        # Remove common artifacts
        text = re.sub(r'© NSPE.*$', '', text, flags=re.MULTILINE)
        
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
