#!/usr/bin/env python3
"""
Test script for ontology entity integration in ProEthica prediction prompts.

This script:
1. Sets up the environment and initializes necessary services
2. Selects a test case document from the database
3. Tests ontology entity retrieval for the document
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
    Find a suitable document for testing that has associated ontology entities.
    
    Args:
        context: Application context
        
    Returns:
        Tuple of (document_id, document) or (None, None) if no suitable document is found
    """
    logger.info("Finding suitable test document with ontology triples")
    
    Document = context['Document']
    DocumentSection = context['DocumentSection']
    SectionTripleAssociationService = context['SectionTripleAssociationService']
    
    try:
        # Look for engineering ethics cases
        cases = Document.query.filter(Document.document_type.in_(['case', 'case_study'])).order_by(Document.id).all()
        
        if not cases:
            logger.warning("No case documents found")
            return None, None
            
        logger.info(f"Found {len(cases)} case documents")
        
        # Initialize triple association service
        triple_service = SectionTripleAssociationService()
        
        # Find a case with associated triples
        for case in cases:
            # Get sections for this document
            sections = DocumentSection.query.filter_by(document_id=case.id).all()
            
            if not sections:
                continue
                
                # Check if any section has associated triples
                for section in sections:
                    # Use get_section_associations instead of get_section_triples
                    associations = triple_service.get_section_associations(section.id)
                    if associations and 'associations' in associations and associations['associations']:
                        logger.info(f"Found document {case.id} with {len(associations['associations'])} associated triples")
                        return case.id, case
        
        # If no case with triples found, return the first case
        logger.warning("No case with associated triples found, using first case")
        return cases[0].id, cases[0]
        
    except Exception as e:
        logger.exception(f"Error finding test document: {str(e)}")
        return None, None

def test_ontology_entity_retrieval(context, document_id):
    """
    Test the retrieval of ontology entities for a document.
    
    Args:
        context: Application context
        document_id: ID of the document to test
        
    Returns:
        Dictionary of ontology entities or None if retrieval failed
    """
    logger.info(f"Testing ontology entity retrieval for document {document_id}")
    
    PredictionService = context['PredictionService']
    
    try:
        # Initialize prediction service
        prediction_service = PredictionService()
        
        # Get document sections
        sections = prediction_service.get_document_sections(document_id, leave_out_conclusion=True)
        logger.info(f"Retrieved {len(sections)} sections for document {document_id}")
        
        # Get ontology entities
        ontology_entities = prediction_service.get_section_ontology_entities(document_id, sections)
        
        # Count total entities
        total_entities = sum(len(entities) for entities in ontology_entities.values())
        logger.info(f"Retrieved {total_entities} ontology entities for document {document_id}")
        
        # Log section entity counts
        for section_type, entities in ontology_entities.items():
            logger.info(f"Section '{section_type}': {len(entities)} entities")
            
            # Log some examples
            if entities:
                logger.info("Examples:")
                for entity in entities[:3]:  # Show up to 3 examples
                    logger.info(f"  {entity.get('subject', '')} {entity.get('predicate', '')} {entity.get('object', '')}")
        
        return ontology_entities
        
    except Exception as e:
        logger.exception(f"Error retrieving ontology entities: {str(e)}")
        return None

def test_prompt_integration(context, document_id, ontology_entities):
    """
    Test the integration of ontology entities into prediction prompts.
    
    Args:
        context: Application context
        document_id: ID of the document to test
        ontology_entities: Dictionary of ontology entities from previous test
        
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
        
        # Get document sections
        sections = prediction_service.get_document_sections(document_id, leave_out_conclusion=True)
        
        # Find similar cases (needed for prompt construction)
        similar_cases = prediction_service._find_similar_cases(document_id, limit=3)
        
        # Construct the prompt
        prompt = prediction_service._construct_conclusion_prediction_prompt(
            document=document,
            sections=sections,
            ontology_entities=ontology_entities,
            similar_cases=similar_cases
        )
        
        # Count ontology entities in prompt
        entities_in_prompt = 0
        for section_type, entities in ontology_entities.items():
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

def test_prediction_generation(context, document_id):
    """
    Test generating a prediction with ontology entity integration.
    
    Args:
        context: Application context
        document_id: ID of the document to test
        
    Returns:
        Prediction result dictionary or None if generation failed
    """
    logger.info(f"Testing prediction generation for document {document_id}")
    
    PredictionService = context['PredictionService']
    
    try:
        # Initialize prediction service
        prediction_service = PredictionService()
        
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

def analyze_ontology_usage(ontology_entities, prediction_result):
    """
    Analyze how well ontology entities were used in the prediction.
    
    Args:
        ontology_entities: Dictionary of ontology entities
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
        for section_type, entities in ontology_entities.items():
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

def save_results(document, ontology_entities, prompt, prediction_result, analysis):
    """
    Save test results to a file.
    
    Args:
        document: Document object
        ontology_entities: Dictionary of ontology entities
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
                for section_type, entities in ontology_entities.items()
            },
            'prompt_preview': prompt[:500] + "..." if len(prompt) > 500 else prompt,
            'prediction_preview': prediction_result.get('prediction', '')[:500] + "..."
            if len(prediction_result.get('prediction', '')) > 500
            else prediction_result.get('prediction', ''),
            'validation_metrics': prediction_result.get('metadata', {}).get('validation_metrics', {}),
            'analysis': analysis
        }
        
        filename = f"ontology_integration_test_{document.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
            
        logger.info(f"Results saved to {filename}")
        
    except Exception as e:
        logger.exception(f"Error saving results: {str(e)}")

def main():
    """Main entry point for the script."""
    logger.info("Starting ontology entity integration test")
    
    # Set up environment
    context = setup_environment()
    
    # Find a suitable test document
    document_id, document = find_test_document(context)
    if not document_id:
        logger.error("Failed to find a suitable test document")
        sys.exit(1)
    
    logger.info(f"Using document: {document.title} (ID: {document_id})")
    
    # Test steps
    ontology_entities = test_ontology_entity_retrieval(context, document_id)
    if not ontology_entities:
        logger.error("Failed to retrieve ontology entities")
        sys.exit(1)
    
    prompt, entities_in_prompt = test_prompt_integration(context, document_id, ontology_entities)
    if not prompt:
        logger.error("Failed to test prompt integration")
        sys.exit(1)
    
    prediction_result = test_prediction_generation(context, document_id)
    if not prediction_result:
        logger.error("Failed to generate prediction")
        sys.exit(1)
    
    analysis = analyze_ontology_usage(ontology_entities, prediction_result)
    
    # Save results
    save_results(document, ontology_entities, prompt, prediction_result, analysis)
    
    # Report success/failure
    if analysis.get('success') and analysis.get('mention_ratio') > 0.1:
        logger.info("TEST PASSED: Ontology entities successfully integrated into prediction")
    else:
        logger.warning("TEST WARNING: Low usage of ontology entities in prediction")
    
    logger.info("Ontology entity integration test completed")

if __name__ == "__main__":
    main()
