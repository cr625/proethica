#!/usr/bin/env python3
"""
Script to check for and fix documents that might be stuck in processing state.
This script can be run periodically to ensure document statuses are accurate.

Usage:
    python fix_document_status.py [--dry-run] [--verbose]

Options:
    --dry-run   Show what would be fixed without making changes
    --verbose   Show detailed information about each document checked
"""

import argparse
import sys
import os
import logging
from datetime import datetime, timedelta

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('fix_document_status')

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Fix documents stuck in processing state')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be fixed without making changes')
    parser.add_argument('--verbose', action='store_true', help='Show detailed information about each document checked')
    return parser.parse_args()

def main():
    """Main function to check and fix document statuses."""
    args = parse_args()
    
    # Import app-specific modules here to avoid import errors when the script is run directly
    try:
        from app import create_app, db
        from app.models.document import Document, PROCESSING_STATUS, PROCESSING_PHASES
    except ImportError:
        logger.error("Failed to import required modules. Make sure you're running this script from the project root.")
        sys.exit(1)
    
    app = create_app()
    
    with app.app_context():
        # Get all documents that are in processing state
        processing_docs = Document.query.filter_by(processing_status=PROCESSING_STATUS['PROCESSING']).all()
        
        if not processing_docs:
            logger.info("No documents found in processing state.")
            return
        
        logger.info(f"Found {len(processing_docs)} documents in processing state.")
        
        fixed_count = 0
        stalled_count = 0
        
        # Current time for checking stalled documents
        now = datetime.utcnow()
        
        for doc in processing_docs:
            # Calculate how long the document has been processing
            processing_time = now - doc.updated_at if doc.updated_at else timedelta(hours=24)  # Default to 24h if no updated_at
            
            # Check if document has content but is still in processing state
            if doc.content:
                if args.verbose:
                    logger.info(f"Document {doc.id} ({doc.title}) has content but is still marked as processing.")
                
                if not args.dry_run:
                    doc.processing_status = PROCESSING_STATUS['COMPLETED']
                    doc.processing_progress = 100
                    doc.processing_phase = PROCESSING_PHASES['FINALIZING']
                    db.session.commit()
                    logger.info(f"Fixed document {doc.id} ({doc.title}) - marked as completed.")
                else:
                    logger.info(f"Would fix document {doc.id} ({doc.title}) - would mark as completed.")
                
                fixed_count += 1
            
            # Check if document has been processing for too long (more than 10 minutes)
            elif processing_time > timedelta(minutes=10):
                if args.verbose:
                    logger.info(f"Document {doc.id} ({doc.title}) has been processing for {processing_time} - likely stalled.")
                
                if not args.dry_run:
                    # If no content after 10 minutes, mark as failed
                    doc.processing_status = PROCESSING_STATUS['FAILED']
                    doc.processing_error = f"Processing stalled after {processing_time}"
                    db.session.commit()
                    logger.info(f"Fixed document {doc.id} ({doc.title}) - marked as failed due to stalled processing.")
                else:
                    logger.info(f"Would fix document {doc.id} ({doc.title}) - would mark as failed due to stalled processing.")
                
                stalled_count += 1
            
            elif args.verbose:
                logger.info(f"Document {doc.id} ({doc.title}) is still processing - no action needed.")
        
        # Summary
        if fixed_count > 0 or stalled_count > 0:
            action = "Would fix" if args.dry_run else "Fixed"
            logger.info(f"{action} {fixed_count} documents with content and {stalled_count} stalled documents.")
        else:
            logger.info("No documents needed fixing.")

if __name__ == "__main__":
    main()
