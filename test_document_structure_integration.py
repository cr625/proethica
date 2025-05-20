"""
Test script to validate integration of document structure annotation.
This script tests the complete pipeline integration with document structure annotation.
"""
import logging
import sys
import json
from flask import url_for
from app import create_app
from app.models.document import Document

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_test():
    """Run the integration test for document structure annotation pipeline."""
    try:
        # Create Flask app with test configuration
        app = create_app()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing

        with app.test_client() as client:
            with app.app_context():
                logger.info("Testing document structure annotation integration")
                
                # Test 1: Check if the enhanced route is registered and accessible
                response = client.get('/cases_enhanced/process/url')
                if response.status_code == 302:  # Expected redirect for GET request
                    logger.info("Enhanced route is registered and accessible ✓")
                else:
                    logger.error(f"Enhanced route is not properly registered: Status code {response.status_code}")
                    return False
                
                # Test 2: Process a URL with document structure annotation
                test_url = 'https://www.nspe.org/resources/ethics/ethics-resources/board-ethical-review-cases/acknowledging-errors-design-case-23-4'
                test_data = {
                    'url': test_url,
                    'world_id': 1,  # Engineering world
                    'process_extraction': 'true'
                }
                
                logger.info(f"Processing URL with document structure annotation: {test_url}")
                response = client.post('/cases_enhanced/process/url', data=test_data, follow_redirects=True)
                
                # Check if the request was successful
                if response.status_code != 200:
                    logger.error(f"Failed to process URL: Status code {response.status_code}")
                    return False
                
                # Test 3: Verify the document structure triples were stored
                # First, find the latest document created
                latest_document = Document.query.order_by(Document.id.desc()).first()
                
                if not latest_document:
                    logger.error("No document was created")
                    return False
                
                logger.info(f"Created document ID: {latest_document.id}, Title: {latest_document.title}")
                
                # Check for document structure metadata
                if not latest_document.doc_metadata:
                    logger.error("Document metadata is missing")
                    return False
                
                metadata = latest_document.doc_metadata
                
                # Check for document URI
                if 'document_uri' not in metadata:
                    logger.error("Document URI is missing from metadata")
                    return False
                
                logger.info(f"Document URI: {metadata['document_uri']} ✓")
                
                # Check for structure triples
                if 'structure_triples' not in metadata:
                    logger.error("Structure triples are missing from metadata")
                    return False
                
                # Parse the structure triples to verify their format
                structure_triples = metadata['structure_triples']
                try:
                    # If it's a string representation of JSON, parse it
                    if isinstance(structure_triples, str):
                        triple_data = json.loads(structure_triples)
                    else:
                        triple_data = structure_triples
                        
                    # Count triples for verification
                    triple_count = len(triple_data) if isinstance(triple_data, list) else 0
                    logger.info(f"Structure triples count: {triple_count} ✓")
                    
                    if triple_count < 10:  # We expect many more than 10 triples for a case
                        logger.warning(f"Unexpectedly low number of triples: {triple_count}")
                except Exception as e:
                    logger.error(f"Error parsing structure triples: {str(e)}")
                    return False
                
                # Check for section embeddings metadata
                if 'section_embeddings_metadata' not in metadata:
                    logger.error("Section embeddings metadata is missing")
                    return False
                
                section_count = len(metadata['section_embeddings_metadata'])
                logger.info(f"Section embeddings metadata count: {section_count} ✓")
                
                # If we reached here, all tests passed
                logger.info("All integration tests passed successfully!")
                return True
    except Exception as e:
        logger.exception(f"Error during integration test: {str(e)}")
        return False

if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
