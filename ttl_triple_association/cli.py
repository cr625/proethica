#!/usr/bin/env python3
"""
Command-line interface for section-triple association.

This script provides a command-line interface for running the section-triple
association process, with various options for selecting sections and configuring
the process.
"""

import os
import sys
import argparse
import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add parent directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ttl_triple_association.section_triple_association_service import SectionTripleAssociationService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"section_triple_association_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Section-Triple Association CLI',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Database options
    parser.add_argument('--db-url', type=str, default=None,
                        help='Database connection URL (defaults to environment variable)')
    
    # Section selection options (must provide one)
    section_group = parser.add_argument_group('Section Selection')
    section_ex = section_group.add_mutually_exclusive_group(required=True)
    section_ex.add_argument('--document-id', type=int,
                          help='Process all sections from a specific document')
    section_ex.add_argument('--section-ids', type=int, nargs='+',
                          help='Process specific section IDs')
    section_ex.add_argument('--with-embeddings', action='store_true',
                          help='Process all sections that have embeddings')
    
    # Association options
    assoc_group = parser.add_argument_group('Association Options')
    assoc_group.add_argument('--similarity', type=float, default=0.6,
                           help='Minimum similarity threshold (0-1)')
    assoc_group.add_argument('--max-matches', type=int, default=10,
                           help='Maximum matches per section')
    assoc_group.add_argument('--batch-size', type=int, default=10,
                           help='Batch size for processing')
    assoc_group.add_argument('--use-llm', action='store_true',
                           help='Use LLM-based association instead of embeddings')
    
    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument('--output', type=str, default=None,
                            help='Save results to JSON file')
    output_group.add_argument('--format', choices=['json', 'pretty'], default='pretty',
                            help='Output format')
    
    return parser.parse_args()

def get_sections_with_embeddings(service) -> List[int]:
    """Get section IDs that have embeddings."""
    try:
        # First try with the document_section_embeddings table
        try:
            session = service.Session()
            query = """
                SELECT DISTINCT dse.section_id
                FROM document_section_embeddings dse
                JOIN document_sections ds ON dse.section_id = ds.id
                ORDER BY dse.section_id
            """
            result = session.execute(query)
            section_ids = [row[0] for row in result]
            session.close()
            
            if section_ids:
                logger.info(f"Found {len(section_ids)} sections with embeddings in document_section_embeddings")
                return section_ids
        except Exception as e:
            logger.info(f"No results from document_section_embeddings, trying document_sections: {e}")
            
        # Fall back to the document_sections table with embedding column
        try:
            session = service.Session()
            query = """
                SELECT id FROM document_sections 
                WHERE embedding IS NOT NULL
                ORDER BY id
            """
            result = session.execute(query)
            section_ids = [row[0] for row in result]
            session.close()
            
            logger.info(f"Found {len(section_ids)} sections with embeddings in document_sections")
            return section_ids
        except Exception as e:
            logger.error(f"Error getting sections with embeddings from document_sections: {e}")
            
        return []
    except Exception as e:
        logger.error(f"Error getting sections with embeddings: {e}")
        return []

def save_results(results: Dict[str, Any], output_file: str):
    """Save results to a JSON file."""
    try:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {output_file}")
    except Exception as e:
        logger.error(f"Error saving results: {e}")

def main():
    """Main entry point."""
    args = parse_args()
    
    try:
        # Initialize service
        logger.info("Initializing section-triple association service...")
        service = SectionTripleAssociationService(
            db_url=args.db_url,
            similarity_threshold=args.similarity,
            max_matches=args.max_matches,
            use_llm=args.use_llm
        )
        
        # Log which association method we're using
        if args.use_llm:
            logger.info("Using LLM-based association approach")
        else:
            logger.info("Using embedding-based association approach")
        
        # Determine sections to process
        section_ids = None
        document_id = None
        
        if args.section_ids:
            section_ids = args.section_ids
            logger.info(f"Processing specific sections: {section_ids}")
        elif args.document_id:
            document_id = args.document_id
            logger.info(f"Processing all sections from document {document_id}")
        elif args.with_embeddings:
            section_ids = get_sections_with_embeddings(service)
            if not section_ids:
                logger.error("No sections with embeddings found")
                return 1
        
        # Process sections
        logger.info(f"Starting section-triple association process...")
        if document_id:
            results = service.batch_associate_sections(
                document_id=document_id,
                batch_size=args.batch_size,
                use_llm=args.use_llm
            )
        else:
            results = service.batch_associate_sections(
                section_ids=section_ids,
                batch_size=args.batch_size,
                use_llm=args.use_llm
            )
        
        # Display results
        if args.format == 'json':
            print(json.dumps(results))
        else:
            # Pretty print summary
            print("\n===== Section-Triple Association Results =====")
            print(f"Method: {'LLM-based' if args.use_llm else 'Embedding-based'}")
            print(f"Total sections: {results.get('total_sections', 0)}")
            print(f"Processed: {results.get('processed', 0)}")
            print(f"Successful: {results.get('successful', 0)}")
            print(f"Failed: {results.get('failed', 0)}")
            print(f"Start time: {results.get('start_time', '')}")
            print(f"End time: {results.get('end_time', '')}")
            print("=============================================\n")
        
        # Save results if requested
        if args.output:
            save_results(results, args.output)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error in section-triple association process: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
