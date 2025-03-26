#!/usr/bin/env python3
"""
Script to retrieve engineering ethics case studies from the database.

This script provides functions to retrieve case studies from the database
based on various criteria, such as world ID, similarity to a query, etc.
It can be used by the agent-based system to access relevant cases.
"""

import os
import sys
import json
import logging
import argparse
from typing import List, Dict, Any, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import app modules
from app import db, create_app
from app.models.document import Document
from app.models.world import World
from app.services.embedding_service import EmbeddingService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_cases_by_world(world_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get case studies for a specific world.
    
    Args:
        world_id: ID of the world to get cases for
        limit: Maximum number of cases to return
        
    Returns:
        List of dictionaries with case details
    """
    try:
        # Query the database for documents of type 'case_study' for the specified world
        documents = Document.query.filter_by(
            world_id=world_id,
            document_type='case_study'
        ).limit(limit).all()
        
        # Convert documents to dictionaries
        cases = []
        for doc in documents:
            case = doc.to_dict()
            # Add the content field which is not included in to_dict()
            case['content'] = doc.content
            cases.append(case)
        
        logger.info(f"Retrieved {len(cases)} cases for world {world_id}")
        return cases
    
    except Exception as e:
        logger.error(f"Error retrieving cases for world {world_id}: {str(e)}")
        return []

def search_cases_by_query(query: str, world_id: Optional[int] = None, k: int = 5) -> List[Dict[str, Any]]:
    """
    Search for case studies similar to a query.
    
    Args:
        query: Query string to search for
        world_id: ID of the world to search in (optional)
        k: Maximum number of results to return
        
    Returns:
        List of dictionaries with case details
    """
    try:
        # Initialize embedding service
        embedding_service = EmbeddingService()
        
        # Search for similar chunks
        similar_chunks = embedding_service.search_similar_chunks(
            query=query,
            k=k,
            world_id=world_id,
            document_type='case_study'
        )
        
        # Get the full documents for each chunk
        cases = []
        seen_doc_ids = set()
        
        for chunk in similar_chunks:
            # Get the document ID from the chunk
            document_id = chunk.get('document_id')
            
            # Skip if we've already seen this document
            if document_id in seen_doc_ids:
                continue
            
            # Get the document
            document = Document.query.get(document_id)
            if document:
                # Convert document to dictionary
                case = document.to_dict()
                # Add the content field which is not included in to_dict()
                case['content'] = document.content
                # Add the chunk that matched
                case['matching_chunk'] = chunk.get('chunk_text')
                case['similarity_score'] = 1.0 - chunk.get('distance', 0.0)
                
                cases.append(case)
                seen_doc_ids.add(document_id)
        
        logger.info(f"Found {len(cases)} cases similar to query")
        return cases
    
    except Exception as e:
        logger.error(f"Error searching cases by query: {str(e)}")
        return []

def get_case_by_id(document_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific case study by ID.
    
    Args:
        document_id: ID of the document to get
        
    Returns:
        Dictionary with case details or None if not found
    """
    try:
        # Get the document
        document = Document.query.get(document_id)
        if not document:
            logger.warning(f"Document with ID {document_id} not found")
            return None
        
        # Convert document to dictionary
        case = document.to_dict()
        # Add the content field which is not included in to_dict()
        case['content'] = document.content
        
        logger.info(f"Retrieved case: {case['title']} (ID: {document_id})")
        return case
    
    except Exception as e:
        logger.error(f"Error retrieving case {document_id}: {str(e)}")
        return None

def get_cases_by_year(year: int, world_id: Optional[int] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get case studies for a specific year.
    
    Args:
        year: Year to filter by
        world_id: ID of the world to filter by (optional)
        limit: Maximum number of cases to return
        
    Returns:
        List of dictionaries with case details
    """
    try:
        # Build the query
        query = Document.query.filter(
            Document.document_type == 'case_study',
            Document.doc_metadata.contains({'year': year})
        )
        
        # Add world filter if provided
        if world_id is not None:
            query = query.filter(Document.world_id == world_id)
        
        # Execute the query
        documents = query.limit(limit).all()
        
        # Convert documents to dictionaries
        cases = []
        for doc in documents:
            case = doc.to_dict()
            # Add the content field which is not included in to_dict()
            case['content'] = doc.content
            cases.append(case)
        
        logger.info(f"Retrieved {len(cases)} cases for year {year}")
        return cases
    
    except Exception as e:
        logger.error(f"Error retrieving cases for year {year}: {str(e)}")
        return []

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description='Retrieve engineering ethics case studies from the database')
    parser.add_argument('--world-id', '-w', type=int,
                        help='ID of the world to get cases for')
    parser.add_argument('--query', '-q', type=str,
                        help='Query string to search for similar cases')
    parser.add_argument('--document-id', '-d', type=int,
                        help='ID of a specific document to retrieve')
    parser.add_argument('--year', '-y', type=int,
                        help='Year to filter cases by')
    parser.add_argument('--limit', '-l', type=int, default=10,
                        help='Maximum number of results to return (default: 10)')
    parser.add_argument('--output', '-o', type=str,
                        help='Output file to save results to (JSON format)')
    
    args = parser.parse_args()
    
    # Initialize Flask app
    app = create_app()
    
    with app.app_context():
        # Determine which function to call based on arguments
        results = None
        
        if args.document_id:
            # Get a specific case by ID
            results = get_case_by_id(args.document_id)
            if results:
                results = [results]  # Convert to list for consistent output
            else:
                results = []
        
        elif args.query:
            # Search for cases similar to a query
            results = search_cases_by_query(args.query, args.world_id, args.limit)
        
        elif args.year:
            # Get cases for a specific year
            results = get_cases_by_year(args.year, args.world_id, args.limit)
        
        elif args.world_id:
            # Get cases for a specific world
            results = get_cases_by_world(args.world_id, args.limit)
        
        else:
            logger.error("No retrieval criteria specified. Please provide at least one of: --world-id, --query, --document-id, --year")
            sys.exit(1)
        
        # Print results
        if results:
            print(f"Retrieved {len(results)} cases")
            
            # Save to file if requested
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                print(f"Results saved to {args.output}")
            else:
                # Print a summary of each case
                for i, case in enumerate(results):
                    print(f"\nCase {i+1}: {case['title']}")
                    print(f"ID: {case['id']}")
                    print(f"Source: {case['source']}")
                    if 'metadata' in case and case['metadata']:
                        if 'year' in case['metadata']:
                            print(f"Year: {case['metadata']['year']}")
                        if 'case_number' in case['metadata']:
                            print(f"Case Number: {case['metadata']['case_number']}")
                    if 'similarity_score' in case:
                        print(f"Similarity Score: {case['similarity_score']:.4f}")
                    if 'matching_chunk' in case:
                        print(f"Matching Chunk: {case['matching_chunk'][:100]}...")
                    print(f"Content: {case['content'][:100]}...")
        else:
            print("No cases found matching the criteria")

if __name__ == '__main__':
    main()
