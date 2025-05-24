#!/usr/bin/env python3
"""
Debug script for testing conclusion predictions with improved error handling.

This script tries to generate conclusion predictions with multiple document IDs,
providing better diagnostics about document data structure to help debug issues.
"""

import os
import sys
import logging
from datetime import datetime
import json
from typing import Dict, List, Any, Optional
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
    from app.models.document_section import DocumentSection
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
        'DocumentSection': DocumentSection,
        'ExperimentRun': ExperimentRun,
        'Prediction': Prediction,
        'PredictionTarget': PredictionTarget,
        'PredictionService': PredictionService
    }

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

def find_valid_document_ids(context, limit=5) -> List[int]:
    """
    Find valid document IDs for testing prediction.
    
    Args:
        context: Application context
        limit: Maximum number of document IDs to return
        
    Returns:
        List of valid document IDs
    """
    Document = context['Document']
    DocumentSection = context['DocumentSection']
    
    try:
        # Find documents that have sections
        documents_with_sections = (
            Document.query
            .join(DocumentSection, Document.id == DocumentSection.document_id)
            .group_by(Document.id)
            .order_by(Document.id)
            .limit(limit)
            .all()
        )
        
        if documents_with_sections:
            doc_ids = [doc.id for doc in documents_with_sections]
            logger.info(f"Found {len(doc_ids)} documents with sections: {doc_ids}")
            return doc_ids
            
        # Fallback: Get some documents by type
        case_documents = (
            Document.query
            .filter(Document.document_type.in_(['case', 'case_study']))
            .order_by(Document.id)
            .limit(limit)
            .all()
        )
        
        if case_documents:
            doc_ids = [doc.id for doc in case_documents]
            logger.info(f"Found {len(doc_ids)} case documents: {doc_ids}")
            return doc_ids
            
        # Last resort: Get any documents
        any_documents = Document.query.order_by(Document.id).limit(limit).all()
        doc_ids = [doc.id for doc in any_documents]
        logger.info(f"Found {len(doc_ids)} documents: {doc_ids}")
        return doc_ids
        
    except Exception as e:
        logger.exception(f"Error finding valid document IDs: {str(e)}")
        return []

def inspect_document(context, document_id: int) -> Dict[str, Any]:
    """
    Inspect document structure to help diagnose issues.
    
    Args:
        context: Application context
        document_id: Document ID to inspect
        
    Returns:
        Dictionary with document information
    """
    Document = context['Document']
    DocumentSection = context['DocumentSection']
    
    try:
        document = Document.query.get(document_id)
        if not document:
            return {
                'success': False,
                'error': f"Document with ID {document_id} not found"
            }
            
        # Get basic document info
        doc_info = {
            'id': document.id,
            'title': document.title,
            'document_type': document.document_type,
            'has_metadata': document.doc_metadata is not None,
            'metadata_type': type(document.doc_metadata).__name__ if document.doc_metadata else None,
            'attributes': [attr for attr in dir(document) if not attr.startswith('_') and not callable(getattr(document, attr))],
            'available_content_fields': []
        }
        
        # Check for various content fields
        for field in ['content', 'text', 'body', 'full_text']:
            if hasattr(document, field) and getattr(document, field):
                doc_info['available_content_fields'].append(field)
                
        # Check document sections
        sections = DocumentSection.query.filter_by(document_id=document_id).all()
        doc_info['has_sections'] = len(sections) > 0
        doc_info['section_count'] = len(sections)
        doc_info['section_types'] = [section.section_type for section in sections] if sections else []
        
        # Check for document structure in metadata
        if document.doc_metadata and isinstance(document.doc_metadata, dict):
            # Check for new format
            if 'document_structure' in document.doc_metadata:
                doc_info['has_document_structure'] = True
                if 'sections' in document.doc_metadata['document_structure']:
                    sections_data = document.doc_metadata['document_structure']['sections']
                    doc_info['document_structure_sections'] = list(sections_data.keys()) if isinstance(sections_data, dict) else 'not a dict'
                    doc_info['document_structure_sections_type'] = type(sections_data).__name__
            else:
                doc_info['has_document_structure'] = False
                
            # Check for legacy format
            if 'sections' in document.doc_metadata:
                legacy_sections = document.doc_metadata['sections']
                doc_info['has_legacy_sections'] = True
                doc_info['legacy_sections_type'] = type(legacy_sections).__name__
                if isinstance(legacy_sections, dict):
                    doc_info['legacy_section_keys'] = list(legacy_sections.keys())
                elif isinstance(legacy_sections, list):
                    doc_info['legacy_section_count'] = len(legacy_sections)
            else:
                doc_info['has_legacy_sections'] = False
        
        return {
            'success': True,
            'document': doc_info
        }
        
    except Exception as e:
        logger.exception(f"Error inspecting document {document_id}: {str(e)}")
        return {
            'success': False,
            'error': f"Error inspecting document: {str(e)}"
        }

def generate_test_prediction(context, document_id: int) -> Dict[str, Any]:
    """Generate a test prediction for the specified document."""
    logger.info(f"Generating test prediction for document {document_id}")
    
    try:
        # First, inspect the document to make sure it has the necessary data
        inspect_result = inspect_document(context, document_id)
        if not inspect_result['success']:
            return inspect_result
            
        doc_info = inspect_result['document']
        logger.info(f"Document inspection: {json.dumps(doc_info, indent=2)}")
        
        # Check if document has enough structure for prediction
        if not doc_info['has_sections'] and not doc_info['available_content_fields'] and not doc_info.get('has_legacy_sections', False) and not doc_info.get('has_document_structure', False):
            logger.warning(f"Document {document_id} doesn't have recognizable content structure")
            return {
                'success': False, 
                'error': "Document has no recognizable content structure",
                'document': doc_info
            }
        
        db = context['db']
        ExperimentRun = context['ExperimentRun']
        Prediction = context['Prediction']
        PredictionTarget = context['PredictionTarget']
        PredictionService = context['PredictionService']
        
        # Create test experiment
        experiment = ExperimentRun(
            name=f"Test Conclusion Prediction {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            description="Test for prediction after schema and service fixes",
            created_at=datetime.now(),
            created_by="debug_script",
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
        
        # Initialize prediction service and generate conclusion prediction
        prediction_service = PredictionService()
        
        # Test if get_document_sections works correctly
        logger.info(f"Testing get_document_sections for document {document_id}")
        sections = prediction_service.get_document_sections(document_id, leave_out_conclusion=True)
        logger.info(f"Retrieved sections: {list(sections.keys())}")
        
        # Generate conclusion prediction
        logger.info(f"Generating conclusion prediction for document {document_id}")
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
        
        # Update experiment status
        experiment.status = 'completed'
        experiment.updated_at = datetime.now()
        db.session.commit()
        
        return {
            'success': True,
            'experiment_id': experiment.id,
            'prediction_id': prediction.id,
            'document_id': document_id,
            'prediction': conclusion_result.get('prediction', '')[:200] + "..." if len(conclusion_result.get('prediction', '')) > 200 else conclusion_result.get('prediction', '')
        }
        
    except Exception as e:
        logger.exception(f"Error generating prediction: {str(e)}")
        return {'success': False, 'error': str(e)}

def main():
    """Main entry point for the script."""
    logger.info("Starting prediction test debug")
    
    # Set up environment
    context = setup_environment()
    
    # Verify database schema matches SQLAlchemy models
    schema_ok = verify_schema(context)
    if not schema_ok:
        logger.error("Schema verification failed, exiting")
        sys.exit(1)
        
    # Find valid document IDs for testing
    document_ids = find_valid_document_ids(context, limit=5)
    
    if not document_ids:
        logger.error("No valid documents found, exiting")
        sys.exit(1)
    
    # Try each document until one succeeds
    success = False
    results = []
    
    for doc_id in document_ids:
        logger.info(f"Testing prediction with document ID {doc_id}")
        result = generate_test_prediction(context, doc_id)
        results.append(result)
        
        if result.get('success'):
            success = True
            logger.info(f"Successfully generated prediction for document {doc_id}")
            logger.info(f"Experiment ID: {result['experiment_id']}")
            logger.info(f"Prediction ID: {result['prediction_id']}")
            logger.info(f"Prediction preview: {result['prediction']}")
            break
        else:
            logger.warning(f"Failed to generate prediction for document {doc_id}: {result.get('error')}")
    
    # Print overall results
    if success:
        logger.info("At least one prediction test was successful")
    else:
        logger.error("All prediction tests failed")
        
    logger.info("Prediction test debug completed")
    
    # Write results to file
    result_file = f"prediction_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'success': success,
            'document_ids_tested': document_ids,
            'results': results
        }, f, indent=2)
    
    logger.info(f"Results written to {result_file}")

if __name__ == "__main__":
    main()
