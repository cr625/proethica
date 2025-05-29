#!/usr/bin/env python3
"""
Test script to check if case deletion works after creating experiment tables.
"""

import os
import sys
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_case_deletion():
    """Test if we can delete a case now that experiment tables exist."""
    
    # Set environment
    os.environ['ENVIRONMENT'] = 'development'
    os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
    
    # Create app
    app = create_app()
    
    with app.app_context():
        try:
            # Check if document/case 252 exists
            document = Document.query.get(252)
            if not document:
                logger.info("Document/Case 252 not found in database")
                return
            
            logger.info(f"Found document 252: {document.title or 'No title'}")
            
            # Try to delete the document
            db.session.delete(document)
            db.session.commit()
            
            logger.info("✓ Document/Case 252 deleted successfully!")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"✗ Error deleting case: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")

if __name__ == "__main__":
    test_case_deletion()