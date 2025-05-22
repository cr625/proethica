#!/usr/bin/env python3
"""
Script to test enhanced prediction with the patched LLM service.

This script:
1. Applies the fixes for prediction service and LLM service
2. Runs a conclusion prediction with the enhanced setup
3. Verifies the result contains engineering ethics terminology
"""

import os
import sys
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Any

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
    
    # Apply patches to PredictionService and LLMService
    logger.info("Applying patches to PredictionService and LLMService")
    try:
        from app.services.experiment.patch_prediction_service import patch_prediction_service
        patch_prediction_service()
        logger.info("Successfully applied patches")
    except Exception as e:
        logger.exception(f"Error applying patches: {str(e)}")
        sys.exit(1)
    
    # Import after environment variables are set and patches are applied
    try:
        from app import create_app, db
        from app.models.document import Document
        from app.models.experiment import ExperimentRun, Prediction, PredictionTarget
        from app.services.experiment.prediction_service import PredictionService
        from app.services.llm_service import LLMService
        from app.services.mcp_client import MCPClient
        
        # Create and configure the app
        app = create_app('config')
        app.app_context().push()
        
        logger.info("App context set up successfully")
        
        # Check if NLTK resources are available
        try:
            import nltk
            for resource in ['punkt', 'stopwords']:
                try:
                    nltk.data.find(f'tokenizers/{resource}')
                    logger.info(f"NLTK resource '{resource}' is available")
                except LookupError:
                    logger.warning(f"NLTK resource '{resource}' is not available, downloading...")
                    nltk.download(resource)
        except ImportError:
            logger.warning("NLTK not available")
        
        return {
            'app': app,
            'db': db,
            'Document': Document,
            'ExperimentRun': ExperimentRun,
            'Prediction': Prediction,
            'PredictionTarget': PredictionTarget,
            'PredictionService': PredictionService,
            'LLMService': LLMService,
            'MCPClient': MCPClient
        }
    except ImportError as e:
        logger.error(f"Failed to import required modules: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Error setting up environment: {str(e)}")
        sys.exit(1)

def verify_llm_configuration(context):
    """
    Verify that the LLM service is properly configured.
    
    Args:
        context: Application context
        
    Returns:
        True if LLM is properly configured, False otherwise
    """
    logger.info("Verifying LLM configuration")
    
    LLMService = context['LLMService']
    llm_service = LLMService()
    
    # Check LLM type
    llm_type = type(llm_service.llm).__name__
    logger.info(f"LLM type: {llm_type}")
    
    # Check if using mock LLM
    is_mock = 'FakeListLLM' in llm_type
    logger.info(f"Using mock LLM: {is_mock}")
    
    # Test a simple prompt
    test_prompt = "What are the core principles of engineering ethics?"
    
    try:
        response_obj = llm_service.llm.invoke(test_prompt)
        
        # Handle different response types
        if hasattr(response_obj, 'content'):
            response = response_obj.content
        elif isinstance(response_obj, dict) and 'content' in response_obj:
            response = response_obj['content']
        else:
            response = str(response_obj)
            
        logger.info(f"LLM test response: {response[:200]}...")
        
        # Check for engineering ethics terms
        has_engineering_terms = any(term in response.lower() for term in [
            'engineer', 'nspe', 'code of ethics', 'public safety', 'professional'
        ])
        
        # Check for medical terms (which shouldn't be there)
        has_medical_terms = any(term in response.lower() for term in [
            'triage', 'medical', 'patient', 'hospital', 'injuries'
        ])
        
        if has_medical_terms:
            logger.warning("Response contains medical terms - patch may not be working properly")
            return False
            
        if not has_engineering_terms:
            logger.warning("Response doesn't contain engineering terms - unexpected response content")
            return False
            
        return True
        
    except Exception as e:
        logger.exception(f"Error testing LLM: {str(e)}")
        return False

def find_test_document(context):
    """
    Find a suitable document for testing.
    
    Args:
        context: Application context
        
    Returns:
        Document ID or None if no suitable document is found
    """
    logger.info("Finding suitable test document")
    
    Document = context['Document']
    
    try:
        # Look for engineering ethics cases
        cases = Document.query.filter(Document.document_type.in_(['case', 'case_study'])).order_by(Document.id).limit(5).all()
        
        if not cases:
            logger.warning("No case documents found")
            return None
            
        logger.info(f"Found {len(cases)} case documents")
        
        # Return the first case ID
        return cases[0].id
        
    except Exception as e:
        logger.exception(f"Error finding test document: {str(e)}")
        return None

def run_enhanced_prediction(context, document_id):
    """
    Run an enhanced prediction on the specified document.
    
    Args:
        context: Application context
        document_id: ID of the document to use for prediction
        
    Returns:
        Dictionary with prediction results
    """
    logger.info(f"Running enhanced prediction for document {document_id}")
    
    db = context['db']
    ExperimentRun = context['ExperimentRun']
    Prediction = context['Prediction']
    PredictionTarget = context['PredictionTarget']
    PredictionService = context['PredictionService']
    
    try:
        # Create experiment
        experiment = ExperimentRun(
            name=f"Enhanced Prediction Test {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            description="Test for enhanced prediction with patched LLM service",
            created_at=datetime.now(),
            created_by="test_script",
            config={
                'prediction_type': 'conclusion',
                'use_ontology': True,
                'document_id': document_id
            },
            status='created'
        )
        
        db.session.add(experiment)
        db.session.commit()
        logger.info(f"Created experiment with ID {experiment.id}")
        
        # Create prediction target
        target = PredictionTarget(
            experiment_run_id=experiment.id,
            name='conclusion',
            description='Conclusion prediction test'
        )
        
        db.session.add(target)
        db.session.commit()
        
        # Initialize prediction service
        prediction_service = PredictionService()
        
        # Test if get_document_sections works correctly
        logger.info(f"Testing get_document_sections for document {document_id}")
        sections = prediction_service.get_document_sections(document_id, leave_out_conclusion=True)
        logger.info(f"Retrieved sections: {list(sections.keys() if sections else [])}")
        
        # Generate conclusion prediction
        logger.info(f"Generating conclusion prediction for document {document_id}")
        conclusion_result = prediction_service.generate_conclusion_prediction(
            document_id=document_id
        )
        
        if not conclusion_result.get('success'):
            logger.error(f"Failed to generate prediction: {conclusion_result.get('error')}")
            return conclusion_result
        
        # Check for medical terms in the prediction
        prediction_text = conclusion_result.get('prediction', '')
        has_medical_terms = any(term in prediction_text.lower() for term in [
            'triage', 'medical', 'patient', 'hospital', 'injuries'
        ])
        
        if has_medical_terms:
            logger.warning("Prediction contains medical terms - patch may not be working properly")
            conclusion_result['has_medical_terms'] = True
        else:
            conclusion_result['has_medical_terms'] = False
            
            # Extract full response content if it's an AIMessage object
            full_response = conclusion_result.get('full_response', '')
            if hasattr(full_response, 'content'):
                full_response = full_response.content
            elif isinstance(full_response, dict) and 'content' in full_response:
                full_response = full_response['content']
            else:
                full_response = str(full_response)
                
            # Store the prediction
            prediction = Prediction(
                experiment_run_id=experiment.id,
                document_id=document_id,
                condition='proethica',
                target='conclusion',
                prediction_text=conclusion_result.get('prediction', ''),
                prompt=conclusion_result.get('prompt', ''),
                reasoning=full_response,
                created_at=datetime.now(),
                meta_info={
                    'sections_included': conclusion_result.get('metadata', {}).get('sections_included', []),
                    'ontology_entities': conclusion_result.get('metadata', {}).get('ontology_entities', {}),
                    'similar_cases': conclusion_result.get('metadata', {}).get('similar_cases', []),
                    'validation_metrics': conclusion_result.get('metadata', {}).get('validation_metrics', {}),
                    'has_medical_terms': has_medical_terms
                }
            )
        
        db.session.add(prediction)
        db.session.commit()
        logger.info(f"Saved prediction with ID {prediction.id}")
        
        # Update experiment status
        experiment.status = 'completed'
        experiment.updated_at = datetime.now()
        db.session.commit()
        
        # Add some results info
        conclusion_result['experiment_id'] = experiment.id
        conclusion_result['prediction_id'] = prediction.id
        
        return conclusion_result
        
    except Exception as e:
        logger.exception(f"Error running enhanced prediction: {str(e)}")
        return {'success': False, 'error': str(e)}

def main():
    """Main entry point for the script."""
    logger.info("Starting enhanced prediction test")
    
    # Set up environment
    context = setup_environment()
    
    # Verify LLM configuration
    if not verify_llm_configuration(context):
        logger.error("LLM configuration verification failed")
        sys.exit(1)
    
    # Find a suitable document
    document_id = find_test_document(context)
    if not document_id:
        logger.error("Failed to find a suitable test document")
        sys.exit(1)
    
    # Run enhanced prediction
    result = run_enhanced_prediction(context, document_id)
    
    # Check results
    if result.get('success'):
        logger.info("Enhanced prediction completed successfully")
        
        # Print preview of prediction
        prediction = result.get('prediction', '')
        preview = prediction[:200] + "..." if len(prediction) > 200 else prediction
        logger.info(f"Prediction preview: {preview}")
        
        # Check for medical terms
        if result.get('has_medical_terms', False):
            logger.warning("WARNING: Prediction contains medical terms - patch may not be fully effective")
        else:
            logger.info("Prediction does not contain medical terms - patch is working effectively")
            
        # Save detailed results
        result_file = f"enhanced_prediction_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_file, 'w') as f:
            # Convert any non-serializable objects to strings
            serializable_result = {}
            for key, value in result.items():
                try:
                    json.dumps(value)
                    serializable_result[key] = value
                except (TypeError, OverflowError):
                    serializable_result[key] = str(value)
            
            json.dump(serializable_result, f, indent=2)
            
        logger.info(f"Detailed results saved to {result_file}")
        
        print("\nEnhanced Prediction Test Results:")
        print(f"Document ID: {document_id}")
        print(f"Experiment ID: {result.get('experiment_id')}")
        print(f"Prediction ID: {result.get('prediction_id')}")
        print(f"Has medical terms: {'❌ Yes' if result.get('has_medical_terms', False) else '✅ No'}")
        print(f"Prediction preview: {preview}")
        
    else:
        logger.error(f"Enhanced prediction failed: {result.get('error')}")
        sys.exit(1)

if __name__ == "__main__":
    main()
