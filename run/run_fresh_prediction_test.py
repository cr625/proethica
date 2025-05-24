#!/usr/bin/env python3
"""
Fresh script to test conclusion predictions with the updated database schema.

This script creates a new context to ensure all SQLAlchemy models are loaded with
the correct column names after the metadata column migration.
"""

import os
import sys
import logging
from datetime import datetime
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv

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
    
    # Import after environment variables are set
    from app import create_app, db
    from app.models.document import Document
    from app.models.experiment import ExperimentRun, Prediction, PredictionTarget
    from app.services.experiment.prediction_service import PredictionService
    from app.services.experiment.patch_prediction_service import patch_prediction_service
    
    # Apply patch to PredictionService
    logger.info("Applying patch to PredictionService")
    patch_prediction_service()
    
    # Create and configure the app
    app = create_app('config')
    app.app_context().push()
    
    logger.info("App context set up successfully")
    
    return {
        'app': app,
        'db': db,
        'Document': Document,
        'ExperimentRun': ExperimentRun,
        'Prediction': Prediction,
        'PredictionTarget': PredictionTarget,
        'PredictionService': PredictionService
    }

def generate_test_prediction(context, document_id: int) -> Dict[str, Any]:
    """Generate a test prediction for the specified document."""
    logger.info(f"Generating test prediction for document {document_id}")
    
    try:
        db = context['db']
        Document = context['Document']
        ExperimentRun = context['ExperimentRun']
        Prediction = context['Prediction']
        PredictionTarget = context['PredictionTarget']
        PredictionService = context['PredictionService']
        
        # Verify document exists
        document = Document.query.get(document_id)
        if not document:
            logger.error(f"Document with ID {document_id} not found")
            return {'success': False, 'error': f"Document {document_id} not found"}
            
        # Create test experiment
        experiment = ExperimentRun(
            name=f"Test Conclusion Prediction {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            description="Test for fresh prediction after schema update",
            created_at=datetime.now(),
            created_by="script",
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
        
        # Generate conclusion prediction
        conclusion_result = prediction_service.generate_conclusion_prediction(
            document_id=document_id
        )
        
        if not conclusion_result.get('success'):
            logger.error(f"Failed to generate prediction: {conclusion_result.get('error')}")
            return conclusion_result
            
        # Store the prediction
        prediction = Prediction(
            experiment_run_id=experiment.id,
            document_id=document_id,
            condition='proethica',
            target='conclusion',
            prediction_text=conclusion_result.get('prediction', ''),
            prompt=conclusion_result.get('prompt', ''),
            reasoning=conclusion_result.get('full_response', ''),
            created_at=datetime.now(),
            meta_info={
                'sections_included': conclusion_result.get('metadata', {}).get('sections_included', []),
                'ontology_entities': conclusion_result.get('metadata', {}).get('ontology_entities', {}),
                'similar_cases': conclusion_result.get('metadata', {}).get('similar_cases', []),
                'validation_metrics': conclusion_result.get('metadata', {}).get('validation_metrics', {})
            }
        )
        
        db.session.add(prediction)
        db.session.commit()
        logger.info(f"Saved prediction with ID {prediction.id}")
        
        # Verify the prediction was saved correctly
        saved_prediction = Prediction.query.get(prediction.id)
        if not saved_prediction:
            logger.error("Failed to retrieve saved prediction")
            return {'success': False, 'error': "Failed to save prediction"}
            
        # Update experiment status
        experiment.status = 'completed'
        experiment.updated_at = datetime.now()
        db.session.commit()
        
        return {
            'success': True,
            'experiment_id': experiment.id,
            'prediction_id': prediction.id,
            'prediction': saved_prediction.prediction_text[:200] + "..." if len(saved_prediction.prediction_text) > 200 else saved_prediction.prediction_text
        }
        
    except Exception as e:
        logger.exception(f"Error generating prediction: {str(e)}")
        return {'success': False, 'error': str(e)}

def verify_schema(context):
    """Verify that the database schema matches the SQLAlchemy models."""
    logger.info("Verifying database schema against SQLAlchemy models")
    
    db = context['db']
    Prediction = context['Prediction']
    
    try:
        # Inspect the metadata table
        inspector = db.inspect(db.engine)
        columns = {col['name']: col for col in inspector.get_columns('experiment_predictions')}
        
        # Check that meta_info column exists
        if 'meta_info' not in columns:
            logger.error("Column 'meta_info' not found in experiment_predictions table")
            return False
            
        # Check SQLAlchemy model attributes
        model_attrs = dir(Prediction)
        if 'meta_info' in model_attrs:
            logger.info("SQLAlchemy model has 'meta_info' attribute")
        else:
            logger.warning(f"SQLAlchemy model attributes issue: 'meta_info' not found in attributes")
            
        # Try a simple query to check column references
        try:
            # This will raise an error if the column names don't match
            first_prediction = Prediction.query.first()
            if first_prediction:
                logger.info(f"Successfully queried first prediction (ID: {first_prediction.id})")
                return True
            else:
                logger.info("No predictions found in database")
                return True
        except Exception as e:
            logger.error(f"Error querying predictions: {str(e)}")
            return False
            
    except Exception as e:
        logger.exception(f"Error verifying schema: {str(e)}")
        return False

def main():
    """Main entry point for the script."""
    logger.info("Starting fresh prediction test")
    
    # Set up environment
    context = setup_environment()
    
    # Verify database schema matches SQLAlchemy models
    schema_ok = verify_schema(context)
    if not schema_ok:
        logger.error("Schema verification failed, exiting")
        sys.exit(1)
        
    # Document ID to test with
    document_id = 252  # Change this to a valid document ID
    
    # Generate test prediction
    result = generate_test_prediction(context, document_id)
    
    if result['success']:
        logger.info("Test prediction successful!")
        logger.info(f"Experiment ID: {result['experiment_id']}")
        logger.info(f"Prediction ID: {result['prediction_id']}")
        logger.info(f"Prediction preview: {result['prediction']}")
    else:
        logger.error(f"Test prediction failed: {result.get('error')}")
        
    logger.info("Fresh prediction test completed")

if __name__ == "__main__":
    main()
