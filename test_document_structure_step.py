"""
Test script for the DocumentStructureAnnotationStep.
"""
import logging
import sys
from app.services.case_processing.pipeline_steps.document_structure_annotation_step import DocumentStructureAnnotationStep

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_mock_case_data():
    """Create mock case data for testing."""
    return {
        'status': 'success',
        'case_number': '23-4',
        'year': '2023',
        'title': 'Test Case: Engineering Ethics',
        'url': 'https://example.com/case-23-4',
        'questions_list': [
            'Was it ethical for Engineer A to approve the design?',
            'Was it ethical for Engineer B to report the issue?'
        ],
        'conclusion_items': [
            'It was not ethical for Engineer A to approve the design.',
            'It was ethical for Engineer B to report the issue.'
        ],
        'sections': {
            'facts': 'Engineer A was responsible for approving a bridge design. Despite concerns about safety, they approved the design to meet the deadline.',
            'question': 'Was it ethical for Engineer A to approve the design? Was it ethical for Engineer B to report the issue?',
            'references': 'Code of Ethics Section II.1.a - Engineers shall hold paramount the safety, health, and welfare of the public.',
            'discussion': 'The NSPE Code of Ethics requires engineers to hold paramount the safety of the public. When approving designs, engineers must ensure they meet all safety requirements.',
            'conclusion': 'It was not ethical for Engineer A to approve the design. It was ethical for Engineer B to report the issue.'
        }
    }

def main():
    """Test the DocumentStructureAnnotationStep."""
    # Create mock case data
    mock_data = create_mock_case_data()
    
    # Create an instance of the DocumentStructureAnnotationStep
    structure_step = DocumentStructureAnnotationStep()
    
    # Process the mock data
    logger.info("Processing mock case data...")
    result = structure_step.process(mock_data)
    
    # Check if processing was successful
    if result.get('status') == 'error':
        logger.error(f"Error processing document structure: {result.get('message')}")
        return
    
    # Print the document URI
    document_uri = result.get('document_structure', {}).get('document_uri')
    logger.info(f"Document URI: {document_uri}")
    
    # Print the structure triples
    structure_triples = result.get('document_structure', {}).get('structure_triples')
    logger.info("Document Structure Triples:")
    print(structure_triples)
    
    # Print section embedding metadata
    section_metadata = result.get('section_embeddings_metadata', {})
    logger.info(f"Section Embedding Metadata: {len(section_metadata)} sections found")
    for uri, metadata in section_metadata.items():
        logger.info(f"  - {uri}: Type={metadata.get('type')}")
    
    logger.info("Test completed successfully.")

if __name__ == "__main__":
    main()
