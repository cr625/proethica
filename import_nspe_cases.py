#!/usr/bin/env python3
"""
Script to import NSPE engineering ethics cases from the provided URLs.
This script fetches case content from the NSPE website, extracts relevant information,
and adds the cases to the Engineering Ethics world.
"""

import sys
import os
import re
import json
import datetime
import time
import argparse
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

# List of NSPE case URLs to import
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


def fetch_case_content(url, max_retries=3, retry_delay=2):
    """
    Fetch case content from a URL with retry logic.
    
    Args:
        url (str): URL to fetch content from
        max_retries (int): Maximum number of retry attempts
        retry_delay (int): Delay between retries in seconds
        
    Returns:
        BeautifulSoup object if successful, None otherwise
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for attempt in range(max_retries):
        try:
            print(f"Fetching {url}")
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()  # Raise exception for 4XX/5XX responses
            
            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"Failed to fetch {url} after {max_retries} attempts")
                return None
    
    return None

def extract_case_info(soup, url):
    """
    Extract case information from BeautifulSoup object.
    
    Args:
        soup (BeautifulSoup): BeautifulSoup object of the case page
        url (str): URL of the case
        
    Returns:
        dict: Case information including title, content, metadata
    """
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
        title_element = soup.find('h1', class_='page-title')
        if title_element:
            case_info['title'] = title_element.text.strip()
        
        # Clean up the entire soup object
        # Remove all script tags to prevent JS requests
        for script in soup.find_all('script'):
            script.decompose()
            
        # Remove all link tags (stylesheets, etc.)
        for link in soup.find_all('link'):
            link.decompose()
            
        # Remove all style tags
        for style in soup.find_all('style'):
            style.decompose()
            
        # Remove all noscript tags
        for noscript in soup.find_all('noscript'):
            noscript.decompose()
            
        # Remove all iframe tags
        for iframe in soup.find_all('iframe'):
            iframe.decompose()
            
        # Remove all img tags with external sources
        for img in soup.find_all('img'):
            if 'src' in img.attrs and (img['src'].startswith('http') or img['src'].startswith('/')):
                img.decompose()
        
        # Extract main content
        content_element = soup.find('div', class_='node__content')
        if content_element:
            # Extract text-based content in a clean way
            # Option 1: Extract only paragraphs as plain text
            paragraphs = content_element.find_all('p')
            if paragraphs:
                content_text = '\n\n'.join([p.text.strip() for p in paragraphs])
                case_info['description'] = content_text
                
            # If no paragraphs were found, try to get the text from the content element
            elif not case_info['description']:
                case_info['description'] = content_element.get_text(separator='\n\n', strip=True)
        
        # Extract case number and year
        case_number_pattern = r'Case No. (\d+-\d+)'
        case_number_match = re.search(case_number_pattern, str(soup))
        if case_number_match:
            case_info['metadata']['case_number'] = case_number_match.group(1)
            
            # Try to extract year from case number
            if '-' in case_number_match.group(1):
                year_part = case_number_match.group(1).split('-')[0]
                if year_part.isdigit():
                    case_info['metadata']['year'] = int(year_part)
        
        # Try to extract date if available
        date_pattern = r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}'
        date_match = re.search(date_pattern, str(soup))
        if date_match and not case_info['metadata']['year']:
            date_str = date_match.group(0)
            year_match = re.search(r'\d{4}', date_str)
            if year_match:
                case_info['metadata']['year'] = int(year_match.group(0))
        
        # Extract principles based on typical keywords
        keywords = [
            'public safety', 'health', 'welfare', 'conflict of interest', 'competence',
            'professional', 'integrity', 'confidential', 'disclosure', 'whistleblowing',
            'ethics', 'responsibility', 'fair', 'objectivity', 'independence', 'qualified',
            'license', 'certification', 'duty', 'obligation', 'compliance', 'standard'
        ]
        
        content_text = str(soup).lower()
        found_principles = set()
        
        for keyword in keywords:
            if keyword in content_text:
                found_principles.add(keyword)
        
        case_info['metadata']['principles'] = list(found_principles)
        
        # Extract decision or outcome if available
        decision_patterns = [
            r'conclusion:?\s*(.*?)(?:\n\n|\Z)',
            r'therefore:?\s*(.*?)(?:\n\n|\Z)',
            r'decided:?\s*(.*?)(?:\n\n|\Z)',
            r'determined:?\s*(.*?)(?:\n\n|\Z)',
            r'board.*?concludes:?\s*(.*?)(?:\n\n|\Z)'
        ]
        
        for pattern in decision_patterns:
            match = re.search(pattern, content_text, re.IGNORECASE | re.DOTALL)
            if match:
                decision = match.group(1).strip()
                if decision and len(decision) > 20:  # Ensure it's not just a short phrase
                    case_info['metadata']['decision'] = decision
                    break
        
        # If we found a decision, try to determine the outcome
        if case_info['metadata']['decision']:
            outcome_keywords = {
                'unethical': ['unethical', 'not ethical', 'violation', 'misconduct', 'breach'],
                'ethical': ['ethical', 'acceptable', 'appropriate', 'proper', 'permissible'],
                'conditional': ['depends', 'conditional', 'depending', 'certain circumstances'],
                'obligation': ['obligation', 'responsibility', 'duty', 'must', 'should', 'required']
            }
            
            decision_text = case_info['metadata']['decision'].lower()
            
            for outcome, keywords in outcome_keywords.items():
                for keyword in keywords:
                    if keyword in decision_text:
                        case_info['metadata']['outcome'] = outcome
                        break
                if case_info['metadata']['outcome']:
                    break
        
    except Exception as e:
        print(f"Error extracting case info: {str(e)}")
    
    # Ensure we have a title even if extraction failed
    if not case_info['title']:
        case_info['title'] = f"NSPE Ethics Case: {url.split('/')[-1].replace('-', ' ').title()}"
    
    # Ensure we have description content
    if not case_info['description']:
        case_info['description'] = f"Case content unavailable. Please refer to the original source: {url}"
    
    return case_info

def create_case_document(case_info, world_id=ENGINEERING_WORLD_ID, verbose=False):
    """
    Create a case study document from case information.
    
    Args:
        case_info (dict): Case information
        world_id (int): World ID to associate the case with
        verbose (bool): Whether to print verbose information
        
    Returns:
        int: Document ID of the created case, or None if failed
    """
    try:
        # Check if case already exists with the same title
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
            processing_status='completed',  # Mark as completed to avoid processing message
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
                
                if verbose:
                    print(f"Added document ID {document.id} to world ID {world_id} cases")
        
        # Process embeddings
        try:
            from app.services.embedding_service import EmbeddingService
            embedding_service = EmbeddingService()
            
            if hasattr(embedding_service, 'process_document'):
                embedding_service.process_document(document.id)
                if verbose:
                    print(f"Generated embeddings for document ID {document.id}")
            else:
                print(f"Warning: EmbeddingService does not have process_document method")
                
        except Exception as e:
            print(f"Error processing embeddings: {str(e)}")
        
        # Create entity triples for Engineering Ethics categories
        try:
            from app.services.entity_triple_service import EntityTripleService
            triple_service = EntityTripleService()
            
            # Define common namespaces
            namespaces = {
                '': 'http://proethica.org/ontology/engineering-ethics#',
                'proeth': 'http://proethica.org/ontology/intermediate#',
                'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
                'case': f'http://proethica.org/case/{document.id}#'
            }
            
            # Create basic triples based on principles
            principles = case_info['metadata'].get('principles', [])
            outcome = case_info['metadata'].get('outcome', '')
            
            # Map principles to ontology concepts
            principle_mapping = {
                'public safety': 'NSPEPublicSafetyPrinciple',
                'health': 'PublicHealthPrinciple',
                'welfare': 'PublicWelfarePrinciple',
                'conflict of interest': 'ConflictOfInterestPrinciple',
                'competence': 'CompetencePrinciple',
                'professional': 'ProfessionalResponsibilityPrinciple',
                'integrity': 'IntegrityPrinciple',
                'confidential': 'ConfidentialityPrinciple',
                'disclosure': 'DisclosurePrinciple',
                'whistleblowing': 'WhistleblowingPrinciple',
                'duty': 'ProfessionalDutyPrinciple',
                'objectivity': 'ObjectivityPrinciple',
                'independence': 'IndependencePrinciple',
                'fair': 'FairnessPrinciple'
            }
            
            # Ensure triple service has the right methods
            if hasattr(triple_service, 'create_triple'):
                # Create the main case triple
                triple_service.create_triple(
                    entity_type='document',
                    entity_id=document.id,
                    subject=f"case:case",
                    predicate=f"rdf:type",
                    object_value=f":EngineeringEthicsCase",
                    is_literal=False,
                    graph=f"world:{world_id}/document:{document.id}"
                )
                
                # Create principle triples
                for principle in principles:
                    for key, concept in principle_mapping.items():
                        if key in principle.lower():
                            try:
                                triple_service.create_triple(
                                    entity_type='document',
                                    entity_id=document.id,
                                    subject=f"case:case",
                                    predicate=f"proeth:involves",
                                    object_value=f":{concept}",
                                    is_literal=False,
                                    graph=f"world:{world_id}/document:{document.id}"
                                )
                                if verbose:
                                    print(f"Created triple for principle: {concept}")
                                break
                            except Exception as e:
                                print(f"Error creating principle triple: {str(e)}")
                
                # Create outcome triple if available
                if outcome:
                    outcome_predicate = "proeth:violates" if outcome == "unethical" else "proeth:upholdsEthicalPrinciple"
                    try:
                        triple_service.create_triple(
                            entity_type='document',
                            entity_id=document.id,
                            subject=f"case:decision",
                            predicate=outcome_predicate,
                            object_value=f":NSPECodeOfEthics",
                            is_literal=False,
                            graph=f"world:{world_id}/document:{document.id}"
                        )
                        if verbose:
                            print(f"Created triple for outcome: {outcome}")
                    except Exception as e:
                        print(f"Error creating outcome triple: {str(e)}")
            else:
                print(f"Warning: EntityTripleService does not have create_triple method")
                
        except Exception as e:
            print(f"Error creating entity triples: {str(e)}")
        
        return document.id
    
    except Exception as e:
        print(f"Error creating case document: {str(e)}")
        db.session.rollback()
        return None

def import_nspe_cases(urls=None, world_id=ENGINEERING_WORLD_ID, verbose=False):
    """
    Import NSPE cases from the provided URLs.
    
    Args:
        urls (list): List of URLs to import cases from (defaults to NSPE_CASE_URLS)
        world_id (int): World ID to associate cases with
        verbose (bool): Whether to print verbose information
        
    Returns:
        list: List of document IDs of imported cases
    """
    if urls is None:
        urls = NSPE_CASE_URLS
    
    imported_cases = []
    
    for url in urls:
        try:
            # Fetch case content
            soup = fetch_case_content(url)
            if not soup:
                print(f"Skipping {url} - failed to fetch content")
                continue
            
            # Extract case information
            case_info = extract_case_info(soup, url)
            
            if verbose:
                print(f"Extracted case info: {json.dumps(case_info, indent=2)}")
            
            # Create case document
            document_id = create_case_document(case_info, world_id, verbose)
            
            if document_id:
                imported_cases.append(document_id)
            
            # Add a small delay to avoid overwhelming the server
            time.sleep(1)
            
        except Exception as e:
            print(f"Error processing URL {url}: {str(e)}")
    
    return imported_cases

def main():
    """
    Main function to import NSPE cases.
    """
    parser = argparse.ArgumentParser(description='Import NSPE engineering ethics cases')
    parser.add_argument('--world-id', type=int, default=ENGINEERING_WORLD_ID,
                        help=f'World ID to associate cases with (default: {ENGINEERING_WORLD_ID})')
    parser.add_argument('--verbose', action='store_true',
                        help='Print verbose information')
    parser.add_argument('--url-file', type=str,
                        help='File containing URLs to import (one per line)')
    args = parser.parse_args()
    
    # Get URLs from file if provided
    urls = NSPE_CASE_URLS
    if args.url_file:
        try:
            with open(args.url_file, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"Error reading URL file: {str(e)}")
            return
    
    print(f"Importing {len(urls)} NSPE engineering ethics cases...")
    
    # Create app context
    app = create_app()
    with app.app_context():
        # Import cases
        imported = import_nspe_cases(urls, args.world_id, args.verbose)
        
        print(f"Completed. Imported {len(imported)} cases.")

if __name__ == "__main__":
    main()
