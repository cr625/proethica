#!/usr/bin/env python3
"""
Script to fetch modern NSPE Board of Ethical Review cases.

This script downloads recent case studies from the NSPE website, processes them,
and adds them to the database with the same enhanced metadata structure used for
McLaren cases, enabling analysis of current ethical dilemmas in engineering.
"""

import os
import sys
import re
import json
import logging
import argparse
import time
import random
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import app modules
from app import db, create_app
from app.models.document import Document, PROCESSING_STATUS
from app.models.world import World
from app.services.embedding_service import EmbeddingService

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
MODERN_CASES_FILE = os.path.join(OUTPUT_DIR, "modern_nspe_cases.json")
ENGINEERING_ETHICS_WORLD_ID = 2  # ID for the Engineering Ethics (US) world

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Predefined case with rich metadata as example
PREDEFINED_CASES = {
    "Case 23-4": {
        "title": "Acknowledging Errors in Design",
        "principles": ["professional responsibility", "public safety", "honesty", "disclosure"],
        "codes_cited": ["Code I.1", "Code II.1.a", "Code II.1.b", "Code II.4", "Code III.1.a"],
        "outcome": "mixed finding",
        "operationalization_techniques": ["Principle Instantiation", "Conflicting Principles Resolution"],
        "pdf_url": "23-4-Acknowledging-Errors-in-Design.pdf",
        "board_analysis": "The case addresses the tension between professional standards and ethical obligations when construction safety risks affect design. The Board found that while contractually the contractor is responsible for construction safety, engineers have ethical obligations to consider foreseeable risks. The Board referenced Case 97-13 where limited reporting of safety issues was appropriate restraint as over-reporting could jeopardize professional reputations."
    }
}

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

def download_pdf(url: str, save_path: str, retries: int = 3, delay: int = 2) -> bool:
    """
    Download a PDF file.
    
    Args:
        url: URL of the PDF to download
        save_path: Path to save the PDF
        retries: Number of retries if the download fails
        delay: Delay between retries in seconds
        
    Returns:
        True if download was successful, False otherwise
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    for attempt in range(retries):
        try:
            # Add a random delay to be respectful to the server
            if attempt > 0:
                sleep_time = delay + random.uniform(0, 2)
                time.sleep(sleep_time)
            
            response = requests.get(url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()
            
            # Save the PDF
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Successfully downloaded PDF: {url}")
            return True
            
        except requests.RequestException as e:
            logger.warning(f"Attempt {attempt + 1}/{retries} failed to download {url}: {str(e)}")
    
    logger.error(f"Failed to download PDF {url} after {retries} attempts")
    return False

def extract_year_from_case_number(case_number: str) -> Optional[int]:
    """
    Extract the year from a case number (e.g., 'Case 23-4' -> 2023).
    
    Args:
        case_number: Case number string
        
    Returns:
        Year as an integer or None if no match
    """
    # Format usually: "Case YY-N" where YY is the last two digits of the year
    match = re.search(r'Case\s+(\d{2})-\d+', case_number, re.IGNORECASE)
    if match:
        year_digits = match.group(1)
        current_year = datetime.now().year
        current_century = current_year // 100 * 100
        
        # Convert 2-digit year to 4-digit year
        year = int(year_digits)
        if year < 100:
            # If the 2-digit year is greater than the current 2-digit year,
            # it's likely from the previous century
            if year > current_year % 100:
                year = (current_century - 100) + year
            else:
                year = current_century + year
        
        return year
    
    return None

def scrape_modern_case_links(year: Optional[int] = None) -> List[Dict[str, str]]:
    """
    Scrape links to modern case studies from the NSPE website.
    
    Args:
        year: Optional year to filter cases by
        
    Returns:
        List of dictionaries with case title and URL
    """
    logger.info(f"Scraping modern case links from {NSPE_CASES_URL}")
    
    # Get the main page content
    main_page_html = get_page_content(NSPE_CASES_URL)
    if not main_page_html:
        logger.error("Failed to retrieve the main page")
        return []
    
    soup = BeautifulSoup(main_page_html, 'html.parser')
    case_links = []
    
    # Look for year navigation or filter elements
    if year:
        logger.info(f"Filtering cases for year {year}")
        # TODO: Implement year-specific filtering if needed
    
    # Look for links that might be case studies
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        title = link.get_text(strip=True)
        
        # Filter for links that look like case studies
        case_pattern = re.compile(r'case-\d+-\d+|case\d+-\d+', re.IGNORECASE)
        if case_pattern.search(href) or 'board-ethical-review-cases' in href:
            # Ensure we have the full URL
            if not href.startswith('http'):
                href = urljoin(NSPE_BASE_URL, href)
                
            case_links.append({
                'title': title,
                'url': href
            })
    
    logger.info(f"Found {len(case_links)} potential case links")
    return case_links

def extract_case_number_and_pdf_link(html_content: str, url: str) -> (Optional[str], Optional[str]):
    """
    Extract the case number and PDF link from the case page.
    
    Args:
        html_content: HTML content of the case page
        url: URL of the case page for reference
        
    Returns:
        Tuple of (case_number, pdf_link) or (None, None) if not found
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Try to find the case number
    case_number = None
    case_number_text = soup.find(string=re.compile(r'Case\s+\d+-\d+', re.IGNORECASE))
    if case_number_text:
        case_number_match = re.search(r'(Case\s+\d+-\d+)', case_number_text, re.IGNORECASE)
        if case_number_match:
            case_number = case_number_match.group(1)
    
    # Another way to find case number - look for it in a paragraph or heading
    if not case_number:
        for elem in soup.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'div']):
            text = elem.get_text(strip=True)
            case_number_match = re.search(r'(Case\s+\d+-\d+)', text, re.IGNORECASE)
            if case_number_match:
                case_number = case_number_match.group(1)
                break
    
    # Look for PDF link
    pdf_link = None
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if href.lower().endswith('.pdf'):
            # Ensure we have the full URL
            if not href.startswith('http'):
                pdf_link = urljoin(NSPE_BASE_URL, href)
            else:
                pdf_link = href
            break
    
    return case_number, pdf_link

def extract_case_content(html_content: str, case_url: str, pdf_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract the content of an individual case study.
    
    Args:
        html_content: HTML content of the case page
        case_url: URL of the case page
        pdf_url: Optional URL to the PDF version of the case
        
    Returns:
        Dictionary with case details
    """
    # Check if the URL is a PDF, handle differently
    if case_url.lower().endswith('.pdf'):
        return extract_pdf_case_content(case_url)
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract the main content
    content_div = soup.find('div', class_='content')
    if not content_div:
        content_div = soup.find('div', id='content')
    if not content_div:
        content_div = soup.find('article')
    if not content_div:
        content_div = soup.find('main')
    if not content_div:
        content_div = soup.body
    
    if not content_div:
        logger.warning(f"Could not find content div in {case_url}")
        return {
            'case_number': None,
            'title': "Failed to extract content",
            'year': None,
            'date': None,
            'full_text': "Could not extract content from the page.",
            'html_content': "<p>Content extraction failed.</p>",
            'url': case_url,
            'pdf_url': None,
            'scraped_at': datetime.now().isoformat(),
            'metadata': {
                'related_cases': [],
                'codes_cited': [],
                'principles': [],
                'outcome': "unknown",
                'operationalization_techniques': []
            }
        }
    
    # Extract title
    title_elem = soup.find(['h1', 'h2', 'h3'])
    title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"
    
    # Extract case number and date
    case_number, pdf_link = extract_case_number_and_pdf_link(html_content, case_url)
    if pdf_url and not pdf_link:
        pdf_link = pdf_url
    
    case_date = None
    content_text = content_div.get_text()
    date_match = re.search(r'(\w+\s+\d{1,2},\s+\d{4})', content_text)
    if date_match:
        case_date = date_match.group(1)
    
    # Extract year
    year = None
    if case_number:
        year = extract_year_from_case_number(case_number)
    if not year and case_date:
        year_match = re.search(r'(\d{4})', case_date)
        if year_match:
            year = int(year_match.group(1))
    
    # Extract full text content
    full_text = content_div.get_text(separator='\n', strip=True)
    
    # Extract HTML content for preservation
    html_content = str(content_div)
    
    # Try to extract codes mentioned in the text
    codes_cited = []
    code_patterns = [
        r'Code(?:\s+of\s+Ethics)?\s+(\w+(?:\.\w+)*)',  # Matches "Code I.1" or "Code of Ethics I.1"
        r'Section\s+(\w+(?:\.\w+)*)\s+of\s+the\s+Code',  # Matches "Section I.1 of the Code"
        r'Code\s+\w+,\s+Section\s+(\w+(?:\.\w+)*)'  # Matches "Code II, Section 1.a"
    ]
    
    for pattern in code_patterns:
        for match in re.finditer(pattern, full_text, re.IGNORECASE):
            code = f"Code {match.group(1)}"
            if code not in codes_cited:
                codes_cited.append(code)
    
    # Get predefined metadata if available
    predefined_metadata = PREDEFINED_CASES.get(case_number, {}) if case_number else {}
    
    # Create metadata structure
    metadata = {
        'related_cases': [],
        'codes_cited': codes_cited or predefined_metadata.get('codes_cited', []),
        'principles': predefined_metadata.get('principles', []),
        'outcome': predefined_metadata.get('outcome', "unknown"),
        'operationalization_techniques': predefined_metadata.get('operationalization_techniques', []),
        'board_analysis': predefined_metadata.get('board_analysis', '')
    }
    
    # Extract referenced cases
    referenced_cases = []
    if 'related_cases' in predefined_metadata:
        referenced_cases = predefined_metadata['related_cases']
    else:
        case_ref_pattern = r'Case(?:\s+No\.?)?\s+(\d+-\d+|\d+)'
        
        for match in re.finditer(case_ref_pattern, full_text):
            ref_case = match.group(1)
            if case_number and ref_case != case_number and ref_case not in referenced_cases:
                referenced_cases.append(f"Case {ref_case}")
        
        metadata['related_cases'] = referenced_cases
    
    # Try to identify the ethical question(s)
    questions = []
    question_section = soup.find(string=re.compile(r'Question[s]?:', re.IGNORECASE))
    
    if question_section:
        # If we found the Questions heading, look for the actual questions
        question_elem = question_section.parent
        next_elem = question_elem.find_next(['h1', 'h2', 'h3', 'h4', 'p', 'div'])
        if next_elem:
            # Check if it's a list of questions
            question_list = next_elem.find_all('li')
            if question_list:
                for q in question_list:
                    questions.append(q.get_text(strip=True))
            else:
                questions.append(next_elem.get_text(strip=True))
    
    # If we found ethical questions, add them to metadata
    if questions:
        metadata['ethical_questions'] = questions
    
    # Return the structured case data
    return {
        'case_number': case_number,
        'title': predefined_metadata.get('title', title),
        'year': year,
        'date': case_date,
        'full_text': full_text,
        'html_content': html_content,
        'url': case_url,
        'pdf_url': pdf_link,
        'scraped_at': datetime.now().isoformat(),
        'metadata': metadata
    }

def extract_pdf_case_content(pdf_url: str) -> Dict[str, Any]:
    """
    Extract information from a PDF case study URL.
    
    Args:
        pdf_url: URL of the PDF case study
        
    Returns:
        Dictionary with case details based on the PDF URL
    """
    # Try to extract case number from the PDF filename
    filename = os.path.basename(pdf_url)
    case_number = None
    
    # Look for patterns like NSPE-BER-Case-22-10.pdf or Case-22-10.pdf
    case_match = re.search(r'Case-(\d+-\d+)', filename, re.IGNORECASE)
    if case_match:
        case_number = f"Case {case_match.group(1)}"
    
    # Extract year if we have a case number
    year = None
    if case_number:
        year = extract_year_from_case_number(case_number)
    
    # Try to get a title from the filename
    title = filename.replace('-', ' ').replace('.pdf', '').strip()
    
    # Check if this is a predefined case
    predefined_metadata = PREDEFINED_CASES.get(case_number, {}) if case_number else {}
    
    return {
        'case_number': case_number,
        'title': predefined_metadata.get('title', title),
        'year': year,
        'date': None,
        'full_text': "PDF content - please refer to the PDF file for details",
        'html_content': f"<p>PDF content - please refer to <a href='{pdf_url}'>the PDF file</a> for details</p>",
        'url': pdf_url,
        'pdf_url': pdf_url,
        'scraped_at': datetime.now().isoformat(),
        'metadata': {
            'related_cases': predefined_metadata.get('related_cases', []),
            'codes_cited': predefined_metadata.get('codes_cited', []),
            'principles': predefined_metadata.get('principles', []),
            'outcome': predefined_metadata.get('outcome', "unknown"),
            'operationalization_techniques': predefined_metadata.get('operationalization_techniques', []),
            'board_analysis': predefined_metadata.get('board_analysis', '')
        }
    }

def process_case_page(case_url: str) -> Optional[Dict[str, Any]]:
    """
    Process a single case study page.
    
    Args:
        case_url: URL of the case page
        
    Returns:
        Dictionary with case details or None if failed
    """
    logger.info(f"Processing case at {case_url}")
    
    # Check if this is a PDF URL
    if case_url.lower().endswith('.pdf'):
        return extract_pdf_case_content(case_url)
    
    # Get the case page content
    case_html = get_page_content(case_url)
    if not case_html:
        logger.error(f"Failed to retrieve case content from {case_url}")
        return None
    
    try:
        # Extract case content
        case_data = extract_case_content(case_html, case_url)
        return case_data
    except Exception as e:
        logger.error(f"Error extracting content from {case_url}: {str(e)}")
        return None

def fetch_modern_cases(output_file: str = MODERN_CASES_FILE, year: Optional[int] = None,
                      max_cases: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Fetch modern case studies from the NSPE website.
    
    Args:
        output_file: Path to save the scraped cases
        year: Optional year to filter cases by
        max_cases: Maximum number of cases to scrape
        
    Returns:
        List of dictionaries with case details
    """
    logger.info(f"Starting to fetch modern cases from {NSPE_CASES_URL}")
    
    # Get case links
    case_links = scrape_modern_case_links(year)
    
    # Limit the number of cases if specified
    if max_cases:
        case_links = case_links[:max_cases]
    
    # Try to load existing cases if available
    existing_cases = []
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_cases = json.load(f)
                logger.info(f"Loaded {len(existing_cases)} existing cases from {output_file}")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load existing cases from {output_file}: {str(e)}")
    
    # Create a set of existing URLs
    existing_urls = {case.get('url') for case in existing_cases if case.get('url')}
    
    # Scrape each case
    cases = []
    for case_link in case_links:
        case_url = case_link['url']
        
        # Skip if we already have this case
        if case_url in existing_urls:
            logger.info(f"Case at {case_url} already exists, skipping")
            # Add the existing case to our list
            for case in existing_cases:
                if case.get('url') == case_url:
                    cases.append(case)
                    break
            continue
        
        # Process the case
        case_data = process_case_page(case_url)
        if case_data:
            cases.append(case_data)
            
            # Add a delay to be respectful to the server
            time.sleep(random.uniform(1, 3))
    
    # Merge with existing cases (except for the ones we just updated)
    updated_urls = {case.get('url') for case in cases if case.get('url')}
    for case in existing_cases:
        if case.get('url') not in updated_urls:
            cases.append(case)
    
    # Add predefined cases that weren't found by scraping
    if year is None or year >= 2023:
        # Check for missing predefined cases
        scraped_case_numbers = {case.get('case_number') for case in cases if case.get('case_number')}
        
        for case_number, predefined_case in PREDEFINED_CASES.items():
            if case_number not in scraped_case_numbers:
                logger.info(f"Adding predefined case {case_number} that wasn't found by scraping")
                
                # Create basic case data
                case_year = extract_year_from_case_number(case_number)
                case_data = {
                    'case_number': case_number,
                    'title': predefined_case.get('title', f"Case {case_number}"),
                    'year': case_year,
                    'full_text': "Predefined case data - full text not available.",
                    'html_content': f"<p>Predefined case data - HTML content not available.</p>",
                    'url': f"{NSPE_CASES_URL}/{case_number.lower().replace(' ', '-')}",
                    'pdf_url': predefined_case.get('pdf_url'),
                    'scraped_at': datetime.now().isoformat(),
                    'metadata': {
                        'related_cases': predefined_case.get('related_cases', []),
                        'codes_cited': predefined_case.get('codes_cited', []),
                        'principles': predefined_case.get('principles', []),
                        'outcome': predefined_case.get('outcome', "unknown"),
                        'operationalization_techniques': predefined_case.get('operationalization_techniques', []),
                        'board_analysis': predefined_case.get('board_analysis', '')
                    }
                }
                cases.append(case_data)
    
    # Save the scraped cases to a file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Fetched {len(cases)} cases and saved to {output_file}")
    return cases

def add_cases_to_database(cases: List[Dict[str, Any]], world_id: int = ENGINEERING_ETHICS_WORLD_ID,
                         process_embeddings: bool = True) -> List[int]:
    """
    Add the fetched cases to the database.
    
    Args:
        cases: List of case dictionaries
        world_id: ID of the world to add the cases to
        process_embeddings: Whether to process embeddings for the cases
        
    Returns:
        List of document IDs created
    """
    # Check if the world exists
    world = World.query.get(world_id)
    if not world:
        logger.error(f"World with ID {world_id} not found")
        return []
    
    logger.info(f"Adding {len(cases)} modern cases to world: {world.name} (ID: {world_id})")
    
    # Initialize embedding service if needed
    embedding_service = None
    if process_embeddings:
        try:
            embedding_service = EmbeddingService()
            logger.info("Initialized embedding service")
        except Exception as e:
            logger.error(f"Failed to initialize embedding service: {str(e)}")
            process_embeddings = False
    
    # Add each case to the database
    document_ids = []
    
    for case in cases:
        try:
            # Create document record
            metadata = {
                'case_number': case.get('case_number'),
                'year': case.get('year'),
                'date': case.get('date'),
                'scraped_at': case.get('scraped_at'),
                'html_content': case.get('html_content'),
                'pdf_url': case.get('pdf_url'),
                'related_cases': case.get('metadata', {}).get('related_cases', []),
                'codes_cited': case.get('metadata', {}).get('codes_cited', []),
                'principles': case.get('metadata', {}).get('principles', []),
                'outcome': case.get('metadata', {}).get('outcome', 'unknown'),
                'operationalization_techniques': case.get('metadata', {}).get('operationalization_techniques', []),
                'board_analysis': case.get('metadata', {}).get('board_analysis', ''),
                'ethical_questions': case.get('metadata', {}).get('ethical_questions', [])
            }
            
            document = Document(
                title=case.get('title', "NSPE Modern Case Study"),
                source=case.get('url', ""),
                document_type='case_study',
                world_id=world_id,
                content=case.get('full_text', ''),
                file_type='html',
                doc_metadata=metadata,
                processing_status=PROCESSING_STATUS['COMPLETED'] if not process_embeddings else PROCESSING_STATUS['PENDING']
            )
            
            # Add to database
            db.session.add(document)
            db.session.flush()  # Get document ID
            
            document_id = document.id
            logger.info(f"Added document: {document.title} (ID: {document_id})")
            document_ids.append(document_id)
            
            # Process embeddings if requested
            if process_embeddings and embedding_service:
                try:
                    # Process the document with the embedding service
                    embedding_service.process_document(document_id)
                    logger.info(f"Processed embeddings for document: {document.title} (ID: {document_id})")
                except Exception as e:
                    logger.error(f"Failed to process embeddings for document {document_id}: {str(e)}")
            
            # Commit after each document
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to add case {case.get('title')}: {str(e)}")
    
    return document_ids

def process_and_add_cases(year: Optional[int] = None, max_cases: Optional[int] = None,
                         world_id: int = ENGINEERING_ETHICS_WORLD_ID,
                         process_embeddings: bool = True) -> List[int]:
    """
    Process modern cases and add them to the database.
    
    Args:
        year: Optional year to filter cases by
        max_cases: Maximum number of cases to process
        world_id: ID of the world to add the cases to
        process_embeddings: Whether to process embeddings for the cases
        
    Returns:
        List of document IDs created
    """
    # Fetch modern cases
    cases = fetch_modern_cases(year=year, max_cases=max_cases)
    
    # Initialize Flask app
    app = create_app()
    
    document_ids = []
    with app.app_context():
        # Add cases to the database
        document_ids = add_cases_to_database(cases, world_id, process_embeddings)
    
    return document_ids

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description='Fetch modern NSPE case studies and add them to the database')
    parser.add_argument('--year', '-y', type=int, default=None,
                        help='Year to filter cases by (default: all years)')
    parser.add_argument('--max-cases', '-m', type=int, default=None,
                        help='Maximum number of cases to fetch (default: all)')
    parser.add_argument('--world-id', '-w', type=int, default=ENGINEERING_ETHICS_WORLD_ID,
                        help=f'ID of the world to add cases to (default: {ENGINEERING_ETHICS_WORLD_ID})')
    parser.add_argument('--no-embeddings', '-n', action='store_true',
                        help='Do not process embeddings for the cases')
    parser.add_argument('--fetch-only', '-f', action='store_true',
                        help='Only fetch cases, do not add to database')
    
    args = parser.parse_args()
    
    if args.fetch_only:
        # Just fetch cases, don't add to database
        cases = fetch_modern_cases(year=args.year, max_cases=args.max_cases)
        print(f"Fetched {len(cases)} cases and saved to {MODERN_CASES_FILE}")
    else:
        # Process cases and add to database
        document_ids = process_and_add_cases(
            year=args.year,
            max_cases=args.max_cases,
            world_id=args.world_id,
            process_embeddings=not args.no_embeddings
        )
        
        if document_ids:
            print(f"Successfully added {len(document_ids)} modern NSPE cases to the database")
            print("Document IDs:", document_ids)
        else:
            print("Failed to add modern NSPE cases to the database")
            sys.exit(1)

if __name__ == '__main__':
    main()
