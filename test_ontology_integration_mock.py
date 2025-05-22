#!/usr/bin/env python3
"""
Test script for ontology entity integration in ProEthica prediction prompts
with mock ontology entities.

This script:
1. Sets up the environment and initializes necessary services
2. Uses a test case document from the database
3. Creates mock ontology entities for testing
4. Verifies entity integration into conclusion prediction prompts
5. Analyzes the resulting prediction for ontology concept usage
"""

import os
import sys
import json
import logging
from dotenv import load_dotenv
from typing import Dict, Any, List
from pprint import pprint
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def setup_environment():
    """Set up Flask application environment."""
    logger.info("Setting up environment")
    
    # Set up environment variables
    os.environ['ENVIRONMENT'] = 'codespace'
    os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
    os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
    os.environ['FLASK_DEBUG'] = '1'
    
    # Load environment variables from .env file if it exists
    if os.path.exists('.env'):
        load_dotenv()
        logger.info("Loaded environment variables from .env file")
    
    # Apply SQLAlchemy URL fix if available
    try:
        import patch_sqlalchemy_url
        patch_sqlalchemy_url.patch_create_app()
        logger.info("Applied SQLAlchemy URL patch")
    except Exception as e:
        logger.warning(f"Failed to apply SQLAlchemy URL patch: {str(e)}")
    
    # Apply patches to PredictionService and LLMService if needed
    try:
        from app.services.experiment.patch_prediction_service import patch_prediction_service
        patch_prediction_service()
        logger.info("Successfully applied PredictionService patches")
    except Exception as e:
        logger.warning(f"Failed to apply PredictionService patches: {str(e)}")
    
    # Import after environment variables are set
    try:
        from app import create_app, db
        from app.models.document import Document
        from app.models.document_section import DocumentSection
        from app.services.experiment.prediction_service import PredictionService
        from app.services.llm_service import LLMService
        from ttl_triple_association.section_triple_association_service import SectionTripleAssociationService
        
        # Create and configure the app
        app = create_app('config')
        app.app_context().push()
        
        logger.info("App context set up successfully")
        
        return {
            'app': app,
            'db': db,
            'Document': Document,
            'DocumentSection': DocumentSection,
            'PredictionService': PredictionService,
            'LLMService': LLMService,
            'SectionTripleAssociationService': SectionTripleAssociationService
        }
        
    except ImportError as e:
        logger.error(f"Failed to import required modules: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Error setting up environment: {str(e)}")
        sys.exit(1)

def find_test_document(context):
    """
    Find a suitable document for testing.
    
    Args:
        context: Application context
        
    Returns:
        Tuple of (document_id, document) or (None, None) if no suitable document is found
    """
    logger.info("Finding suitable test document")
    
    Document = context['Document']
    
    try:
        # Look for engineering ethics cases
        cases = Document.query.filter(Document.document_type.in_(['case', 'case_study'])).order_by(Document.id).all()
        
        if not cases:
            logger.warning("No case documents found")
            return None, None
            
        logger.info(f"Found {len(cases)} case documents")
        
        # For now, just use the first case
        first_case = cases[0]
        logger.info(f"Using document: {first_case.title} (ID: {first_case.id})")
        return first_case.id, first_case
        
    except Exception as e:
        logger.exception(f"Error finding test document: {str(e)}")
        return None, None

def create_mock_ontology_entities(document_id, sections):
    """
    Create mock ontology entities for testing.
    
    Args:
        document_id: ID of the document
        sections: Dictionary of section types to content
        
    Returns:
        Dictionary of mock ontology entities
    """
    logger.info(f"Creating mock ontology entities for document {document_id}")
    
    # Create sample entities for different section types
    mock_entities = {}
    
    # Basic facts-related entities
    if 'facts' in sections or 'text' in sections:
        mock_entities['facts'] = [
            {
                'subject': 'Engineer',
                'predicate': 'hasRole',
                'object': 'Professional',
                'score': 0.92,
                'source': 'mock'
            },
            {
                'subject': 'Design',
                'predicate': 'requiresAttribute',
                'object': 'Accuracy',
                'score': 0.88,
                'source': 'mock'
            },
            {
                'subject': 'Engineer',
                'predicate': 'hasResponsibility',
                'object': 'PublicSafety',
                'score': 0.95,
                'source': 'mock'
            }
        ]
    
    # Question/issues-related entities
    if 'question' in sections or 'text' in sections:
        mock_entities['question'] = [
            {
                'subject': 'Engineer',
                'predicate': 'mustDisclose',
                'object': 'Error',
                'score': 0.94,
                'source': 'mock'
            },
            {
                'subject': 'ProfessionalJudgment',
                'predicate': 'influences',
                'object': 'EthicalDecision',
                'score': 0.87,
                'source': 'mock'
            }
        ]
    
    # References/rules-related entities
    if 'references' in sections or 'text' in sections:
        mock_entities['references'] = [
            {
                'subject': 'NSPECode',
                'predicate': 'requiresPrinciple',
                'object': 'Honesty',
                'score': 0.96,
                'source': 'mock'
            },
            {
                'subject': 'NSPECode',
                'predicate': 'requiresPrinciple',
                'object': 'Integrity',
                'score': 0.95,
                'source': 'mock'
            },
            {
                'subject': 'Section_II_1',
                'predicate': 'states',
                'object': 'EngineersShallDiscloseAllKnownOrDiscoveredErrors',
                'score': 0.93,
                'source': 'mock'
            }
        ]
    
    # Discussion-related entities
    if 'discussion' in sections or 'text' in sections:
        mock_entities['discussion'] = [
            {
                'subject': 'ErrorDisclosure',
                'predicate': 'protects',
                'object': 'PublicSafety',
                'score': 0.91,
                'source': 'mock'
            },
            {
                'subject': 'EngineeringPractice',
                'predicate': 'requiresPrinciple',
                'object': 'Transparency',
                'score': 0.89,
                'source': 'mock'
            }
        ]
    
    # If we're using a generic 'text' section, make sure we have all entity types
    if 'text' in sections:
        for section_type in ['facts', 'question', 'references', 'discussion']:
            if section_type not in mock_entities:
                mock_entities[section_type] = []
        
    return mock_entities

def patch_prediction_service_for_testing(prediction_service, mock_entities):
    """
    Patch the prediction service to use mock ontology entities.
    
    Args:
        prediction_service: The PredictionService instance
        mock_entities: Dictionary of mock ontology entities
        
    Returns:
        Modified PredictionService instance
    """
    logger.info("Patching PredictionService to use mock ontology entities")
    
    # Store the original method
    original_method = prediction_service.get_section_ontology_entities
    
    # Define a replacement method that returns mock entities
    def mock_get_section_ontology_entities(document_id, sections):
        logger.info(f"Using mock ontology entities instead of querying database")
        return mock_entities
    
    # Apply the patch
    prediction_service.get_section_ontology_entities = mock_get_section_ontology_entities
    
    # Store the original method for restoration if needed
    prediction_service._original_get_section_ontology_entities = original_method
    
    return prediction_service

def test_prompt_integration(context, document_id, sections, mock_entities):
    """
    Test the integration of ontology entities into prediction prompts.
    
    Args:
        context: Application context
        document_id: ID of the document to test
        sections: Document sections
        mock_entities: Dictionary of mock ontology entities
        
    Returns:
        Tuple of (prompt, entities_in_prompt)
    """
    logger.info(f"Testing prompt integration for document {document_id}")
    
    Document = context['Document']
    PredictionService = context['PredictionService']
    
    try:
        # Get the document
        document = Document.query.get(document_id)
        if not document:
            logger.error(f"Document with ID {document_id} not found")
            return None, 0
        
        # Initialize prediction service
        prediction_service = PredictionService()
        
        # Patch the prediction service to use mock entities
        prediction_service = patch_prediction_service_for_testing(prediction_service, mock_entities)
        
        # Find similar cases (needed for prompt construction)
        similar_cases = prediction_service._find_similar_cases(document_id, limit=3)
        
        # Construct the prompt
        prompt = prediction_service._construct_conclusion_prediction_prompt(
            document=document,
            sections=sections,
            ontology_entities=mock_entities,
            similar_cases=similar_cases
        )
        
        # Count ontology entities in prompt
        entities_in_prompt = 0
        for section_type, entities in mock_entities.items():
            for entity in entities:
                # Check if subject and object are in prompt
                if entity.get('subject', '') in prompt:
                    entities_in_prompt += 1
                if entity.get('object', '') in prompt:
                    entities_in_prompt += 1
        
        logger.info(f"Found {entities_in_prompt} ontology entity mentions in prompt")
        
        # Sample the prompt (first 200 chars)
        prompt_preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
        logger.info(f"Prompt preview: {prompt_preview}")
        
        return prompt, entities_in_prompt
        
    except Exception as e:
        logger.exception(f"Error testing prompt integration: {str(e)}")
        return None, 0

def test_prediction_generation(context, document_id, mock_entities):
    """
    Test generating a prediction with ontology entity integration.
    
    Args:
        context: Application context
        document_id: ID of the document to test
        mock_entities: Dictionary of mock ontology entities
        
    Returns:
        Prediction result dictionary or None if generation failed
    """
    logger.info(f"Testing prediction generation for document {document_id}")
    
    PredictionService = context['PredictionService']
    
    try:
        # Initialize prediction service
        prediction_service = PredictionService()
        
        # Patch the prediction service to use mock entities
        prediction_service = patch_prediction_service_for_testing(prediction_service, mock_entities)
        
        # Generate conclusion prediction
        result = prediction_service.generate_conclusion_prediction(document_id=document_id)
        
        if not result.get('success'):
            logger.error(f"Failed to generate prediction: {result.get('error')}")
            return None
        
        # Log prediction preview
        prediction = result.get('prediction', '')
        preview = prediction[:200] + "..." if len(prediction) > 200 else prediction
        logger.info(f"Prediction preview: {preview}")
        
        # Check validation metrics
        validation_metrics = result.get('metadata', {}).get('validation_metrics', {})
        logger.info(f"Validation metrics: {json.dumps(validation_metrics, indent=2)}")
        
        return result
        
    except Exception as e:
        logger.exception(f"Error generating prediction: {str(e)}")
        return None

def analyze_ontology_usage(mock_entities, prediction_result):
    """
    Analyze how well ontology entities were used in the prediction.
    
    Args:
        mock_entities: Dictionary of mock ontology entities
        prediction_result: Prediction result dictionary
        
    Returns:
        Analysis results dictionary
    """
    logger.info("Analyzing ontology usage in prediction")
    
    try:
        if not prediction_result:
            return {
                'success': False,
                'message': 'No prediction result to analyze'
            }
        
        prediction_text = prediction_result.get('prediction', '')
        metadata = prediction_result.get('metadata', {})
        validation_metrics = metadata.get('validation_metrics', {})
        
        # Extract all subjects and objects from ontology entities
        all_entities = []
        for section_type, entities in mock_entities.items():
            for entity in entities:
                if 'subject' in entity:
                    all_entities.append(entity['subject'])
                if 'object' in entity:
                    all_entities.append(entity['object'])
        
        # Count entity mentions in prediction
        entity_mentions = 0
        mentioned_entities = []
        
        for entity in all_entities:
            if entity in prediction_text:
                entity_mentions += 1
                mentioned_entities.append(entity)
        
        # Calculate metrics
        total_entities = len(all_entities)
        mention_ratio = entity_mentions / total_entities if total_entities > 0 else 0
        
        # Compare with validation metrics
        validation_match = (
            validation_metrics.get('entity_mentions') == entity_mentions and
            validation_metrics.get('total_entities') == total_entities and
            abs(validation_metrics.get('mention_ratio', 0) - mention_ratio) < 0.01
        )
        
        analysis = {
            'success': True,
            'entity_mentions': entity_mentions,
            'total_entities': total_entities,
            'mention_ratio': mention_ratio,
            'mentioned_entities': mentioned_entities[:10],  # Limit to first 10
            'validation_metrics_match': validation_match,
            'message': 'Ontology entities successfully integrated into prediction'
            if mention_ratio > 0.1 else 'Low usage of ontology entities in prediction'
        }
        
        logger.info(f"Analysis: {json.dumps(analysis, indent=2)}")
        
        return analysis
        
    except Exception as e:
        logger.exception(f"Error analyzing ontology usage: {str(e)}")
        return {
            'success': False,
            'message': f"Error analyzing ontology usage: {str(e)}"
        }

def save_results(document, mock_entities, prompt, prediction_result, analysis):
    """
    Save test results to a file.
    
    Args:
        document: Document object
        mock_entities: Dictionary of mock ontology entities
        prompt: Generated prompt
        prediction_result: Prediction result dictionary
        analysis: Analysis results dictionary
    """
    logger.info("Saving test results")
    
    try:
        results = {
            'timestamp': datetime.now().isoformat(),
            'document': {
                'id': document.id,
                'title': document.title,
                'document_type': document.document_type
            },
            'ontology_entities_summary': {
                section_type: len(entities)
                for section_type, entities in mock_entities.items()
            },
            'prompt_preview': prompt[:500] + "..." if len(prompt) > 500 else prompt,
            'prediction_preview': prediction_result.get('prediction', '')[:500] + "..."
            if len(prediction_result.get('prediction', '')) > 500
            else prediction_result.get('prediction', ''),
            'validation_metrics': prediction_result.get('metadata', {}).get('validation_metrics', {}),
            'analysis': analysis
        }
        
        filename = f"ontology_integration_test_mock_{document.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
            
        logger.info(f"Results saved to {filename}")
        
    except Exception as e:
        logger.exception(f"Error saving results: {str(e)}")

def main():
    """Main entry point for the script."""
    logger.info("Starting ontology entity integration test with mock data")
    
    # Set up environment
    context = setup_environment()
    
    # Find a suitable test document
    document_id, document = find_test_document(context)
    if not document_id:
        logger.error("Failed to find a suitable test document")
        sys.exit(1)
    
    # Initialize prediction service to get document sections
    prediction_service = context['PredictionService']()
    sections = prediction_service.get_document_sections(document_id, leave_out_conclusion=True)
    
    if not sections:
        logger.error("Failed to retrieve document sections")
        sys.exit(1)
    
    logger.info(f"Retrieved {len(sections)} sections for document {document_id}")
    
    # Create mock ontology entities
    mock_entities = create_mock_ontology_entities(document_id, sections)
    
    # Count total mock entities
    total_entities = sum(len(entities) for entities in mock_entities.values())
    logger.info(f"Created {total_entities} mock ontology entities for document {document_id}")
    
    # For each section type, log entity counts
    for section_type, entities in mock_entities.items():
        logger.info(f"Section '{section_type}': {len(entities)} mock entities")
        
        # Log some examples
        if entities:
            logger.info("Examples:")
            for entity in entities[:3]:  # Show up to 3 examples
                logger.info(f"  {entity.get('subject', '')} {entity.get('predicate', '')} {entity.get('object', '')}")
    
    # Test prompt integration
    prompt, entities_in_prompt = test_prompt_integration(context, document_id, sections, mock_entities)
    if not prompt:
        logger.error("Failed to test prompt integration")
        sys.exit(1)
    
    # Test prediction generation
    prediction_result = test_prediction_generation(context, document_id, mock_entities)
    if not prediction_result:
        logger.error("Failed to generate prediction")
        sys.exit(1)
    
    # Analyze ontology usage
    analysis = analyze_ontology_usage(mock_entities, prediction_result)
    
    # Save results
    save_results(document, mock_entities, prompt, prediction_result, analysis)
    
    # Report success/failure
    if analysis.get('success') and analysis.get('mention_ratio') > 0.1:
        logger.info("TEST PASSED: Ontology entities successfully integrated into prediction")
    else:
        logger.warning("TEST WARNING: Low usage of ontology entities in prediction")
    
    logger.info("Ontology entity integration test with mock data completed")

if __name__ == "__main__":
    main()
