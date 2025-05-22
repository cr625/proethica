#!/usr/bin/env python3
"""
Batch Process Section Triples

This script provides a command-line utility for batch processing document sections
and associating them with relevant ontology triples using the SectionTripleAssociationService.

Usage:
    python batch_process_section_triples.py --all  # Process all sections
    python batch_process_section_triples.py --case-id 123  # Process sections for a specific case
    python batch_process_section_triples.py --document-id 456  # Process sections for a specific document
    python batch_process_section_triples.py --section-ids 1,2,3  # Process specific sections
"""

import os
import sys
import logging
import argparse
import time
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import the SectionTripleAssociationService
from section_triple_association_service import SectionTripleAssociationService, create_section_triple_association_table

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("section_triple_processing.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def get_section_ids_for_case(case_id: int) -> List[int]:
    """Retrieve all section IDs for a specific case."""
    session = Session()
    try:
        query = text("""
            SELECT ds.id
            FROM document_sections ds
            JOIN documents d ON ds.document_id = d.id
            WHERE d.case_id = :case_id
        """)
        
        results = session.execute(query, {"case_id": case_id}).fetchall()
        section_ids = [row[0] for row in results]
        
        logger.info(f"Found {len(section_ids)} sections for case {case_id}")
        return section_ids
        
    except Exception as e:
        logger.error(f"Error retrieving section IDs for case {case_id}: {e}")
        return []
    finally:
        session.close()


def get_section_ids_for_document(document_id: int) -> List[int]:
    """Retrieve all section IDs for a specific document."""
    session = Session()
    try:
        query = text("""
            SELECT id
            FROM document_sections
            WHERE document_id = :document_id
        """)
        
        results = session.execute(query, {"document_id": document_id}).fetchall()
        section_ids = [row[0] for row in results]
        
        logger.info(f"Found {len(section_ids)} sections for document {document_id}")
        return section_ids
        
    except Exception as e:
        logger.error(f"Error retrieving section IDs for document {document_id}: {e}")
        return []
    finally:
        session.close()


def get_all_section_ids() -> List[int]:
    """Retrieve all section IDs in the system."""
    session = Session()
    try:
        query = text("""
            SELECT id
            FROM document_sections
            ORDER BY id
        """)
        
        results = session.execute(query).fetchall()
        section_ids = [row[0] for row in results]
        
        logger.info(f"Found {len(section_ids)} total sections in the system")
        return section_ids
        
    except Exception as e:
        logger.error(f"Error retrieving all section IDs: {e}")
        return []
    finally:
        session.close()


def get_section_ids_with_embeddings() -> List[int]:
    """Retrieve section IDs that have embeddings."""
    session = Session()
    try:
        query = text("""
            SELECT DISTINCT section_id
            FROM document_section_embeddings
            ORDER BY section_id
        """)
        
        results = session.execute(query).fetchall()
        section_ids = [row[0] for row in results]
        
        logger.info(f"Found {len(section_ids)} sections with embeddings")
        return section_ids
        
    except Exception as e:
        logger.error(f"Error retrieving section IDs with embeddings: {e}")
        return []
    finally:
        session.close()


def process_sections_in_batches(section_ids: List[int], batch_size: int = 50, 
                              similarity_threshold: float = 0.6) -> Dict[str, Any]:
    """
    Process sections in batches to associate them with triples.
    
    Args:
        section_ids: List of section IDs to process
        batch_size: Number of sections to process in each batch
        similarity_threshold: Minimum similarity score for triple matching
        
    Returns:
        Dictionary with processing statistics
    """
    start_time = time.time()
    service = SectionTripleAssociationService(similarity_threshold=similarity_threshold)
    
    total_sections = len(section_ids)
    processed_count = 0
    error_count = 0
    association_count = 0
    
    logger.info(f"Starting batch processing of {total_sections} sections")
    
    # Process in batches
    for i in range(0, total_sections, batch_size):
        batch = section_ids[i:i + batch_size]
        batch_start_time = time.time()
        
        logger.info(f"Processing batch {i//batch_size + 1}/{(total_sections + batch_size - 1)//batch_size} "
                   f"({len(batch)} sections)")
        
        try:
            # Process the batch
            results = service.batch_associate_sections(batch)
            
            # Count associations
            batch_association_count = sum(len(matches) for matches in results.values())
            association_count += batch_association_count
            processed_count += len(batch)
            
            batch_time = time.time() - batch_start_time
            logger.info(f"Batch completed in {batch_time:.2f} seconds. "
                       f"Created {batch_association_count} associations "
                       f"({batch_association_count/len(batch):.2f} avg per section)")
            
        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            error_count += len(batch)
    
    # Clean up
    service.close()
    
    # Calculate statistics
    total_time = time.time() - start_time
    success_rate = (processed_count - error_count) / total_sections if total_sections > 0 else 0
    
    stats = {
        "total_sections": total_sections,
        "processed_sections": processed_count,
        "error_sections": error_count,
        "success_rate": success_rate,
        "total_associations": association_count,
        "avg_associations_per_section": association_count / processed_count if processed_count > 0 else 0,
        "processing_time_seconds": total_time,
        "sections_per_second": processed_count / total_time if total_time > 0 else 0
    }
    
    logger.info(f"Processing completed in {total_time:.2f} seconds")
    logger.info(f"Processed {processed_count}/{total_sections} sections with {error_count} errors")
    logger.info(f"Created {association_count} triple associations "
               f"({stats['avg_associations_per_section']:.2f} avg per section)")
    
    return stats


def print_stats(stats: Dict[str, Any]) -> None:
    """Print processing statistics in a formatted way."""
    print("\n" + "="*60)
    print(" SECTION-TRIPLE ASSOCIATION PROCESSING STATISTICS ")
    print("="*60)
    
    print(f"Total sections processed:       {stats['total_sections']}")
    print(f"Successfully processed:         {stats['processed_sections'] - stats['error_sections']}")
    print(f"Errors encountered:             {stats['error_sections']}")
    print(f"Success rate:                   {stats['success_rate'] * 100:.2f}%")
    print(f"Total triple associations:      {stats['total_associations']}")
    print(f"Avg associations per section:   {stats['avg_associations_per_section']:.2f}")
    print(f"Total processing time:          {stats['processing_time_seconds']:.2f} seconds")
    print(f"Processing speed:               {stats['sections_per_second']:.2f} sections/second")
    print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Batch process document sections for triple association")
    
    # Define mutually exclusive group for section selection
    section_group = parser.add_mutually_exclusive_group(required=True)
    section_group.add_argument("--all", action="store_true", help="Process all sections in the system")
    section_group.add_argument("--with-embeddings", action="store_true", 
                              help="Process only sections that have embeddings")
    section_group.add_argument("--case-id", type=int, help="Process sections for a specific case ID")
    section_group.add_argument("--document-id", type=int, help="Process sections for a specific document ID")
    section_group.add_argument("--section-ids", type=str, help="Process specific section IDs (comma separated)")
    
    # Additional options
    parser.add_argument("--batch-size", type=int, default=50, help="Number of sections to process in each batch")
    parser.add_argument("--similarity-threshold", type=float, default=0.6, 
                      help="Minimum similarity score (0-1) for triple matching")
    parser.add_argument("--dry-run", action="store_true", 
                      help="Perform a dry run (list sections to process without actual processing)")
    
    args = parser.parse_args()
    
    # Make sure the table exists
    create_section_triple_association_table()
    
    # Get section IDs based on the selection criteria
    section_ids = []
    
    if args.all:
        section_ids = get_all_section_ids()
    elif args.with_embeddings:
        section_ids = get_section_ids_with_embeddings()
    elif args.case_id:
        section_ids = get_section_ids_for_case(args.case_id)
    elif args.document_id:
        section_ids = get_section_ids_for_document(args.document_id)
    elif args.section_ids:
        try:
            section_ids = [int(sid.strip()) for sid in args.section_ids.split(",")]
            logger.info(f"Processing {len(section_ids)} specified section IDs: {section_ids}")
        except ValueError:
            logger.error("Invalid section IDs. Please provide comma-separated integers.")
            sys.exit(1)
    
    if not section_ids:
        logger.error("No sections found to process.")
        sys.exit(1)
    
    # Dry run - just list the sections that would be processed
    if args.dry_run:
        print(f"DRY RUN: Would process {len(section_ids)} sections:")
        
        # For large numbers of sections, just show a sample
        if len(section_ids) > 20:
            print(f"  Sample: {section_ids[:10]} ... (and {len(section_ids) - 10} more)")
        else:
            print(f"  Sections: {section_ids}")
            
        sys.exit(0)
    
    # Process the sections
    stats = process_sections_in_batches(
        section_ids, 
        batch_size=args.batch_size, 
        similarity_threshold=args.similarity_threshold
    )
    
    # Print statistics
    print_stats(stats)


if __name__ == "__main__":
    main()
