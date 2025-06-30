#!/usr/bin/env python3
"""
Script to scrape engineering ethics case studies from the NSPE website.

This script extracts case studies from the National Society of Professional Engineers (NSPE)
Board of Ethical Review Cases website and saves them to a JSON file for later processing.
"""

import os
import json
import re
import logging
import argparse
from typing import List, Dict, Any, Optional
from datetime import datetime
import time
import random

import requests
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
NSPE_BASE_URL = "https://www.nspe.org"
NSPE_CASES_URL = f"{NSPE_BASE_URL}/resources/ethics/ethics-resources/board-ethical-review-cases"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
DEFAULT_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "nspe_cases.json")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_page_content(url: str, retries: int = 3, delay: int = 2) -> Optional[str]:
    """
    Get the HTML content of a page with retries and delay to be respectful.
    
    Args:
        url: URL to fetch
        retries: Number of retries if the request fails
        delay: Delay between retries in seconds
        
    Returns:
        HTML content of the page or None if failed
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    }
    
    for attempt in range(retries):
        try:
            # Add a random delay to be respectful to the server
            if attempt > 0:
                sleep_time = delay + random.uniform(0, 2)
                time.sleep(sleep_time)
                
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.warning(f"Attempt {attempt + 1}/{retries} failed for {url}: {str(e)}")
    
    logger.error(f"Failed to retrieve {url} after {retries} attempts")
    return None

def extract_case_links(html_content: str) -> List[Dict[str, str]]:
    """
    Extract links to individual case studies from the main page.
    
    Args:
        html_content: HTML content of the main page
        
    Returns:
        List of dictionaries with case title and URL
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    case_links = []
    
    # The cases are typically in a list or table on the page
    # We'll need to find the appropriate container and extract links
    
    # Look for links that might be case studies
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        title = link.get_text(strip=True)
        
        # Filter for links that look like case studies
        # This pattern may need adjustment based on the actual website structure
        if '/resources/ethics/ethics-resources/board-ethical-review-cases/' in href and title:
            # Ensure we have the full URL
            if not href.startswith('http'):
                href = NSPE_BASE_URL + href
                
            case_links.append({
                'title': title,
                'url': href
            })
    
    logger.info(f"Found {len(case_links)} potential case links")
    return case_links

def extract_case_content(html_content: str, case_url: str) -> Dict[str, Any]:
    """
    Extract the content of an individual case study.
    
    Args:
        html_content: HTML content of the case page
        case_url: URL of the case page
        
    Returns:
        Dictionary with case details
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract the main content
    content_div = soup.find('div', class_='content')
    if not content_div:
        content_div = soup.find('div', id='content')
    if not content_div:
        content_div = soup.find('article')
    if not content_div:
        content_div = soup.body
    
    # Extract title
    title_elem = content_div.find(['h1', 'h2'])
    title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"
    
    # Extract full text content
    full_text = content_div.get_text(separator='\n', strip=True)
    
    # Try to extract case number and year
    case_number = None
    year = None
    
    # Look for case number pattern (e.g., "Case No. 15-10" or "Case 15-10")
    case_number_match = re.search(r'Case(?:\s+No\.?)?\s+(\d+-\d+|\d+)', full_text)
    if case_number_match:
        case_number = case_number_match.group(1)
    
    # Look for year pattern
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', full_text)
    if year_match:
        year = int(year_match.group(1))
    
    # Extract HTML content for preservation
    html_content = str(content_div)
    
    return {
        'title': title,
        'url': case_url,
        'case_number': case_number,
        'year': year,
        'full_text': full_text,
        'html_content': html_content,
        'scraped_at': datetime.now().isoformat()
    }

def scrape_nspe_cases(output_file: str = DEFAULT_OUTPUT_FILE, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Scrape engineering ethics case studies from the NSPE website.
    
    Args:
        output_file: Path to save the scraped cases
        limit: Maximum number of cases to scrape (None for all)
        
    Returns:
        List of dictionaries with case details
    """
    logger.info(f"Starting to scrape NSPE cases from {NSPE_CASES_URL}")
    
    # Get the main page content
    main_page_html = get_page_content(NSPE_CASES_URL)
    if not main_page_html:
        logger.error("Failed to retrieve the main page")
        return []
    
    # Extract links to individual cases
    case_links = extract_case_links(main_page_html)
    
    # Limit the number of cases if specified
    if limit and limit > 0:
        case_links = case_links[:limit]
        logger.info(f"Limited to {limit} cases")
    
    # Scrape each case
    cases = []
    for i, case_link in enumerate(case_links):
        logger.info(f"Scraping case {i+1}/{len(case_links)}: {case_link['title']}")
        
        # Get the case page content
        case_html = get_page_content(case_link['url'])
        if not case_html:
            logger.warning(f"Failed to retrieve case: {case_link['url']}")
            continue
        
        # Extract case content
        case_data = extract_case_content(case_html, case_link['url'])
        cases.append(case_data)
        
        # Add a delay to be respectful to the server
        time.sleep(random.uniform(1, 3))
    
    # Save the scraped cases to a file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Scraped {len(cases)} cases and saved to {output_file}")
    return cases

def main():
    """Main function to run the scraper."""
    parser = argparse.ArgumentParser(description='Scrape engineering ethics case studies from the NSPE website')
    parser.add_argument('--output', '-o', type=str, default=DEFAULT_OUTPUT_FILE,
                        help=f'Output JSON file (default: {DEFAULT_OUTPUT_FILE})')
    parser.add_argument('--limit', '-l', type=int, default=None,
                        help='Maximum number of cases to scrape (default: all)')
    
    args = parser.parse_args()
    
    scrape_nspe_cases(args.output, args.limit)

if __name__ == '__main__':
    main()
