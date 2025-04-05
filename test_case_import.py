#!/usr/bin/env python3
"""
Script to import a small subset of NSPE engineering ethics cases.
This simplified script is for testing purposes.
"""

import sys
import os
import json
import datetime
import time
import requests
from bs4 import BeautifulSoup

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import the application and database
from app import create_app, db
from app.models.document import Document
from app.models.world import World

# Constants
ENGINEERING_WORLD_ID = 1  # Engineering Ethics world ID

# List of all NSPE case URLs to import
NSPE_CASE_URLS = [
    "https://www.nspe.org/career-resources/ethics/post-public-employment-city-engineer-transitioning-consultant",
    "https://www.nspe.org/career-resources/ethics/excess-stormwater-runoff",
    "https://www.nspe.org/career-resources/ethics/competence-design-services",
    "https://www.nspe.org/career-resources/ethics/providing-incomplete-self-serving-advice",
    "https://www.nspe.org/career-resources/ethics/independence-peer-reviewer",
    "https://www.nspe.org/career-resources/ethics/impaired-engineering",
    "https://www.nspe.org/career-resources/ethics/professional-responsibility-if-appropriate-authority-fails-act",
    "https://www.nspe.org/career-resources/ethics/review-other-engineer-s-work",
    "https://www.nspe.org/career-resources/ethics/sharing-built-drawings",
    "https://www.nspe.org/career-resources/ethics/unlicensed-practice-nonengineers-engineer-job-titles",
    "https://www.nspe.org/career-resources/ethics/public-welfare-what-cost",
    "https://www.nspe.org/career-resources/ethics/misrepresentation-qualifications",
    "https://www.nspe.org/career-resources/ethics/good-samaritan-laws",
    "https://www.nspe.org/career-resources/ethics/public-safety-health-welfare-avoiding-rolling-blackouts",
    "https://www.nspe.org/career-resources/ethics/internal-plan-reviews-vsthird-party-peer-reviews-duties",
    "https://www.nspe.org/career-resources/ethics/conflict-interest-designbuild-project",
    "https://www.nspe.org/career-resources/ethics/offer-free-or-reduced-fee-services",
    "https://www.nspe.org/career-resources/ethics/public-health-safety-welfare-climate-change-induced-conditions",
    "https://www.nspe.org/career-resources/ethics/equipment-design-certification-plan-stamping",
    "https://www.nspe.org/career-resources/ethics/gifts-mining-safety-boots",
    "https://www.nspe.org/career-resources/ethics/public-health-safety-welfare-drinking-water-quality",
    "https://www.nspe.org/career-resources/ethics/conflict-interest-pes-serving-state-licensure-boards"
]

def fetch_case_content(url):
    """
    Fetch case content from a URL with simple error handling.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        print(f"Fetching {url}")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        return None

def clean_content(soup):
    """Clean HTML content to remove scripts and other problematic elements."""
    if not soup:
        return None
    
    # Make a copy to avoid modifying the original
    cleaned_soup = BeautifulSoup(str(soup), 'html.parser')
    
    # Remove all script tags
    for script in cleaned_soup.find_all('script'):
        script.decompose()
    
    # Remove all link tags
    for link in cleaned_soup.find_all('link'):
        link.decompose()
    
    # Remove all style tags
    for style in cleaned_soup.find_all('style'):
        style.decompose()
    
    # Remove all iframe tags
    for iframe in cleaned_soup.find_all('iframe'):
        iframe.decompose()
    
    # Remove external references in img tags
    for img in cleaned_soup.find_all('img'):
        if 'src' in img.attrs:
            img['src'] = ''
            
    return cleaned_soup

def extract_case_info(soup, url):
    """
    Extract case information from BeautifulSoup object.
    """
    if not soup:
        return None
        
    # Clean the soup first
    cleaned_soup = clean_content(soup)
    
    # Initialize the case info structure
    case_info = {
        'title': '',
        'description': '',
        'source': url,
        'metadata': {
            'case_number': '',
            'year': '',
            'principles': [],
            'outcome': '',
            'decision': ''
        }
    }
    
    try:
        # Extract title
        title_element = cleaned_soup.find('h1', class_='page-title')
        if title_element:
            case_info['title'] = title_element.text.strip()
        else:
            # Fallback title creation from URL
            case_info['title'] = f"NSPE Ethics Case: {url.split('/')[-1].replace('-', ' ').title()}"
            
        # Extract content
        content_element = cleaned_soup.find('div', class_='node__content')
        if content_element:
            # Get just the paragraphs as plain text
            paragraphs = content_element.find_all('p')
            if paragraphs:
                content_text = '\n\n'.join([p.text.strip() for p in paragraphs])
                case_info['description'] = content_text
            else:
                # Fallback to getting all text from the content div
                case_info['description'] = content_element.get_text(separator='\n\n', strip=True)
        
        # If we still don't have content, use a fallback message
        if not case_info['description']:
            case_info['description'] = f"Case content unavailable. Please refer to the original source: {url}"
            
    except Exception as e:
        print(f"Error extracting case info: {str(e)}")
        case_info['description'] = f"Error extracting case. Please refer to the original source: {url}"
    
    return case_info

def create_case_document(case_info, world_id=ENGINEERING_WORLD_ID):
    """Create a case document in the database."""
    if not case_info:
        return None
        
    try:
        # Check if case already exists
        existing_case = Document.query.filter_by(
            title=case_info['title'],
            document_type='case_study',
            world_id=world_id
        ).first()
        
        if existing_case:
            print(f"Case '{case_info['title']}' already exists (ID: {existing_case.id})")
            return existing_case.id
        
        # Create document
        document = Document(
            title=case_info['title'],
            content=case_info['description'],
            document_type='case_study',
            world_id=world_id,
            source=case_info['source'],
            doc_metadata=case_info['metadata'],
            processing_status='completed',
            processing_phase='completed',
            processing_progress=100,
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now()
        )
        
        # Add to database
        db.session.add(document)
        db.session.commit()
        
        print(f"Created case: {case_info['title']} (ID: {document.id})")
        
        # Update world's cases array
        world = World.query.get(world_id)
        if world:
            if world.cases is None:
                world.cases = []
            
            if document.id not in world.cases:
                world.cases.append(document.id)
                db.session.add(world)
                db.session.commit()
                print(f"Added document ID {document.id} to world ID {world_id} cases")
        
        return document.id
        
    except Exception as e:
        print(f"Error creating case document: {str(e)}")
        db.session.rollback()
        return None

def main():
    """Import a small set of test cases."""
    print("Starting test import of NSPE cases...")
    
    # Create app context
    app = create_app()
    with app.app_context():
        total_imported = 0
        
        for url in NSPE_CASE_URLS:
            # Fetch content
            soup = fetch_case_content(url)
            if not soup:
                print(f"Skipping {url} - failed to fetch")
                continue
                
            # Extract case info
            case_info = extract_case_info(soup, url)
            if not case_info:
                print(f"Skipping {url} - failed to extract info")
                continue
                
            # Create case document
            document_id = create_case_document(case_info)
            if document_id:
                total_imported += 1
                print(f"Successfully imported case ID: {document_id}")
            
            # Add a delay between cases
            time.sleep(1)
        
        print(f"Test import completed. Imported {total_imported} cases.")

if __name__ == "__main__":
    main()
