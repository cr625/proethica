#!/usr/bin/env python3
"""
Script to add engineering ethics case studies to a specific world in the database.

This script takes the scraped case studies from the NSPE website and adds them
to the database as documents with proper metadata, then processes them with
the embedding service to generate vector embeddings for similarity search.
"""

import os
import sys
import json
import logging
import argparse
from typing import List, Dict, Any, Optional
from datetime import datetime

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
DEFAULT_INPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "nspe_cases.json")

def load_cases(input_file: str) -> List[Dict[str, Any]]:
    """
    Load case studies from a JSON file.
    
    Args:
        input_file: Path to the JSON file containing case studies
        
    Returns:
        List of dictionaries with case details
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            cases = json.load(f)
        logger.info(f"Loaded {len(cases)} cases from {input_file}")
        return cases
    except Exception as e:
        logger.error(f"Failed to load cases from {input_file}: {str(e)}")
        return []

def add_cases_to_world(cases: List[Dict[str, Any]], world_id: int, 
                      document_type: str = 'case_study', 
                      process_embeddings: bool = True) -> List[int]:
    """
    Add case studies to a specific world in the database.
    
    Args:
        cases: List of dictionaries with case details
        world_id: ID of the world to add cases to
        document_type: Type of document to create
        process_embeddings: Whether to process embeddings for the documents
        
    Returns:
        List of document IDs created
    """
    # Check if the world exists
    world = World.query.get(world_id)
    if not world:
        logger.error(f"World with ID {world_id} not found")
        return []
    
    logger.info(f"Adding {len(cases)} cases to world: {world.name} (ID: {world_id})")
    
    # Initialize embedding service if needed
    embedding_service = None
    if process_embeddings:
        try:
            embedding_service = EmbeddingService()
            logger.info("Initialized embedding service")
        except Exception as e:
            logger.error(f"Failed to initialize embedding service: {str(e)}")
            process_embeddings = False
    
    # Add cases to the database
    document_ids = []
    for i, case in enumerate(cases):
        try:
            # Create document record
            document = Document(
                title=case.get('title', f"Case {i+1}"),
                source=case.get('url', ''),
                document_type=document_type,
                world_id=world_id,
                content=case.get('full_text', ''),
                file_type='html',
                doc_metadata={
                    'case_number': case.get('case_number'),
                    'year': case.get('year'),
                    'scraped_at': case.get('scraped_at'),
                    'html_content': case.get('html_content')
                },
                processing_status=PROCESSING_STATUS['COMPLETED'] if not process_embeddings else PROCESSING_STATUS['PENDING']
            )
            
            # Add to database
            db.session.add(document)
            db.session.flush()  # Get document ID
            
            document_ids.append(document.id)
            logger.info(f"Added document: {document.title} (ID: {document.id})")
            
            # Process embeddings if requested
            if process_embeddings and embedding_service:
                try:
                    # Process the document with the embedding service
                    embedding_service.process_document(document.id)
                    logger.info(f"Processed embeddings for document: {document.title} (ID: {document.id})")
                except Exception as e:
                    logger.error(f"Failed to process embeddings for document {document.id}: {str(e)}")
            
            # Commit after each document to avoid losing all if one fails
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to add case {i+1}: {str(e)}")
    
    logger.info(f"Added {len(document_ids)} cases to world {world_id}")
    return document_ids

def process_url_directly(url: str, title: str, world_id: int, document_type: str = 'case_study') -> Optional[int]:
    """
    Process a URL directly using the embedding service.
    
    Args:
        url: URL to process
        title: Title for the document
        world_id: ID of the world to add the document to
        document_type: Type of document to create
        
    Returns:
        Document ID if successful, None otherwise
    """
    # Check if the world exists
    world = World.query.get(world_id)
    if not world:
        logger.error(f"World with ID {world_id} not found")
        return None
    
    logger.info(f"Processing URL directly: {url}")
    
    try:
        # Initialize embedding service
        embedding_service = EmbeddingService()
        
        # Process the URL
        document_id = embedding_service.process_url(
            url=url,
            title=title,
            document_type=document_type,
            world_id=world_id
        )
        
        logger.info(f"Processed URL: {url} (Document ID: {document_id})")
        return document_id
    
    except Exception as e:
        logger.error(f"Failed to process URL {url}: {str(e)}")
        return None

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description='Add engineering ethics case studies to a specific world')
    parser.add_argument('--input', '-i', type=str, default=DEFAULT_INPUT_FILE,
                        help=f'Input JSON file with case studies (default: {DEFAULT_INPUT_FILE})')
    parser.add_argument('--world-id', '-w', type=int, required=True,
                        help='ID of the world to add cases to')
    parser.add_argument('--document-type', '-t', type=str, default='case_study',
                        help='Type of document to create (default: case_study)')
    parser.add_argument('--no-embeddings', '-n', action='store_true',
                        help='Do not process embeddings for the documents')
    parser.add_argument('--url', '-u', type=str,
                        help='Process a single URL directly instead of loading from file')
    parser.add_argument('--title', type=str,
                        help='Title for the document when processing a single URL')
    
    args = parser.parse_args()
    
    # Initialize Flask app
    app = create_app()
    
    with app.app_context():
        if args.url:
            # Process a single URL directly
            if not args.title:
                args.title = f"Case from {args.url}"
            
            process_url_directly(args.url, args.title, args.world_id, args.document_type)
        else:
            # Load cases from file and add to world
            cases = load_cases(args.input)
            if cases:
                add_cases_to_world(
                    cases=cases,
                    world_id=args.world_id,
                    document_type=args.document_type,
                    process_embeddings=not args.no_embeddings
                )

if __name__ == '__main__':
    main()
