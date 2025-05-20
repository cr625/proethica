"""
Test integration of DocumentStructureAnnotationStep with PipelineManager.
"""
import logging
import sys
from app.services.case_processing.pipeline_steps.document_structure_annotation_step import DocumentStructureAnnotationStep
from app.services.case_processing.pipeline_steps.url_retrieval_step import URLRetrievalStep
from app.services.case_processing.pipeline_steps.nspe_extraction_step import NSPECaseExtractionStep
from app.services.case_processing.pipeline_manager import PipelineManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_mock_input():
    """Create mock input for the pipeline."""
    return {
        'url': 'https://www.nspe.org/resources/ethics/ethics-resources/board-ethical-review-cases/acknowledging-errors-design-case-23-4'
    }

def main():
    """Test integrating DocumentStructureAnnotationStep with PipelineManager."""
    # Create pipeline manager
    pipeline = PipelineManager()
    
    # Register steps
    pipeline.register_step('url_retrieval', URLRetrievalStep())
    pipeline.register_step('nspe_extraction', NSPECaseExtractionStep())
    pipeline.register_step('document_structure', DocumentStructureAnnotationStep())
    
    # Create input data
    input_data = create_mock_input()
    
    # Define steps to run
    steps_to_run = ['url_retrieval', 'nspe_extraction', 'document_structure']
    
    # Run pipeline
    logger.info(f"Running pipeline with steps: {', '.join(steps_to_run)}")
    result = pipeline.run_pipeline(input_data, steps_to_run)
    
    # Check if pipeline completed successfully
    if result['status'] == 'complete':
        logger.info("Pipeline execution completed successfully")
        
        # Get final result
        final_result = result['final_result']
        
        # Check for document structure information
        if 'document_structure' in final_result:
            document_uri = final_result['document_structure'].get('document_uri')
            logger.info(f"Document structure annotation successful: {document_uri}")
            
            # Get triple count
            graph = final_result['document_structure'].get('graph')
            if graph:
                logger.info(f"Generated {len(graph)} triples")
            
            # Get section embedding metadata
            section_metadata = final_result.get('section_embeddings_metadata', {})
            logger.info(f"Section Embedding Metadata: {len(section_metadata)} sections found")
        else:
            logger.error("Document structure annotation missing from result")
    else:
        logger.error(f"Pipeline execution failed: {result}")
        
        # Check which step failed
        for step_id, step_result in result.get('results', {}).items():
            if step_result.get('status') == 'error':
                logger.error(f"Step '{step_id}' failed: {step_result.get('message')}")
    
    logger.info("Pipeline integration test completed")

if __name__ == "__main__":
    main()
