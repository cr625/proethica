#!/usr/bin/env python3
"""
Script to process a specific NSPE case study URL and add it to the database.

This script combines the functionality of scrape_nspe_cases.py and add_cases_to_world.py
to directly process a specific URL from the NSPE website and add it to the database.
"""

import os
import sys
import logging
import argparse
import re
from typing import Dict, Any, Optional
from datetime import datetime
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

def get_page_content(url: str) -> Optional[str]:
    """
    Get the HTML content of a page.
    
    Args:
        url: URL to fetch
        
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
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Failed to retrieve {url}: {str(e)}")
        return None

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

def process_nspe_url(url: str, world_id: int, document_type: str = 'case_study', 
                    process_embeddings: bool = True) -> Optional[int]:
    """
    Process a specific NSPE case study URL and add it to the database.
    
    Args:
        url: URL of the NSPE case study
        world_id: ID of the world to add the case to
        document_type: Type of document to create
        process_embeddings: Whether to process embeddings for the document
        
    Returns:
        Document ID if successful, None otherwise
    """
    # Check if the world exists
    world = World.query.get(world_id)
    if not world:
        logger.error(f"World with ID {world_id} not found")
        return None
    
    logger.info(f"Processing NSPE case study URL: {url}")
    
    # Get the page content
    html_content = get_page_content(url)
    if not html_content:
        logger.error(f"Failed to retrieve content from {url}")
        return None
    
    # Extract case content
    case_data = extract_case_content(html_content, url)
    
    # Initialize embedding service if needed
    embedding_service = None
    if process_embeddings:
        try:
            embedding_service = EmbeddingService()
            logger.info("Initialized embedding service")
        except Exception as e:
            logger.error(f"Failed to initialize embedding service: {str(e)}")
            process_embeddings = False
    
    try:
        # Create document record
        document = Document(
            title=case_data.get('title', "NSPE Case Study"),
            source=case_data.get('url', url),
            document_type=document_type,
            world_id=world_id,
            content=case_data.get('full_text', ''),
            file_type='html',
            doc_metadata={
                'case_number': case_data.get('case_number'),
                'year': case_data.get('year'),
                'scraped_at': case_data.get('scraped_at'),
                'html_content': case_data.get('html_content')
            },
            processing_status=PROCESSING_STATUS['COMPLETED'] if not process_embeddings else PROCESSING_STATUS['PENDING']
        )
        
        # Add to database
        db.session.add(document)
        db.session.flush()  # Get document ID
        
        document_id = document.id
        logger.info(f"Added document: {document.title} (ID: {document_id})")
        
        # Process embeddings if requested
        if process_embeddings and embedding_service:
            try:
                # Process the document with the embedding service
                embedding_service.process_document(document_id)
                logger.info(f"Processed embeddings for document: {document.title} (ID: {document_id})")
            except Exception as e:
                logger.error(f"Failed to process embeddings for document {document_id}: {str(e)}")
        
        # Commit changes
        db.session.commit()
        
        return document_id
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to add case: {str(e)}")
        return None

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description='Process a specific NSPE case study URL and add it to the database')
    parser.add_argument('--url', '-u', type=str, required=True,
                        help='URL of the NSPE case study')
    parser.add_argument('--world-id', '-w', type=int, required=True,
                        help='ID of the world to add the case to')
    parser.add_argument('--document-type', '-t', type=str, default='case_study',
                        help='Type of document to create (default: case_study)')
    parser.add_argument('--no-embeddings', '-n', action='store_true',
                        help='Do not process embeddings for the document')
    
    args = parser.parse_args()
    
    # Initialize Flask app
    app = create_app()
    
    with app.app_context():
        document_id = process_nspe_url(
            url=args.url,
            world_id=args.world_id,
            document_type=args.document_type,
            process_embeddings=not args.no_embeddings
        )
        
        if document_id:
            print(f"Successfully processed NSPE case study and added to database with ID: {document_id}")
        else:
            print("Failed to process NSPE case study")
            sys.exit(1)

if __name__ == '__main__':
    main()
