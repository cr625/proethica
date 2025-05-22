"""
Standalone script for running conclusion predictions on a set of ethics cases.

Usage:
    python run_conclusion_predictions_fixed.py --limit 5  # Process 5 cases
    python run_conclusion_predictions_fixed.py --case-id 123  # Process a specific case
    python run_conclusion_predictions_fixed.py --all  # Process all cases
"""

import os
import sys
import argparse
import logging
from datetime import datetime
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Set up path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/conclusion_predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Define globals to be set in setup_environment
Document = None
ExperimentRun = None
Prediction = None
PredictionTarget = None
PredictionService = None
db = None

def setup_environment() -> None:
    """Set up Flask application context."""
    # Declare the globals we'll set in this function
    global Document, ExperimentRun, Prediction, PredictionTarget, PredictionService, db
    
    logger.info("Setting up Flask application context")
    
    # Set up environment variables first (before importing app)
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
        logger.info("Applied SQLAlchemy URL fix")
    except Exception as e:
        logger.warning(f"Failed to apply SQLAlchemy URL fix: {str(e)}")
        
    # Now import the app
    try:
        from app import create_app, db
        from app.models.document import Document
        from app.models.experiment import ExperimentRun, Prediction, PredictionTarget
        from app.services.experiment.prediction_service import PredictionService
        
        # Create app with specific config module
        app = create_app('config')
        
        # Push the app context
        app.app_context().push()
        
        logger.info("Successfully set up Flask application context")
        
    except ImportError as e:
        logger.error(f"Failed to import required modules: {str(e)}")
        logger.error("Make sure you're running this script from the project root directory")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Error during setup: {str(e)}")
        sys.exit(1)
    
def create_experiment(name: str, description: str = None) -> ExperimentRun:
    """
    Create a new conclusion prediction experiment.
    
    Args:
        name: Name of the experiment
        description: Optional description
        
    Returns:
        The created experiment
    """
    try:
        # Create experiment
        experiment = ExperimentRun(
            name=name,
            description=description or f"Conclusion prediction experiment created on {datetime.now().strftime('%Y-%m-%d')}",
            created_at=datetime.utcnow(),
            created_by="script",
            config={
                'prediction_type': 'conclusion',
                'use_ontology': True
            },
            status='created'
        )
        
        db.session.add(experiment)
        db.session.commit()
        
        # Create prediction target
        target = PredictionTarget(
            experiment_run_id=experiment.id,
            name='conclusion',
            description='Predict the conclusion section of the case'
        )
        
        db.session.add(target)
        db.session.commit()
        
        logger.info(f"Created experiment with ID {experiment.id}")
        return experiment
        
    except Exception as e:
        logger.exception(f"Error creating experiment: {str(e)}")
        db.session.rollback()
        raise

def get_case_ids(limit: Optional[int] = None, case_id: Optional[int] = None) -> List[int]:
    """
    Get IDs of cases to process.
    
    Args:
        limit: Optional limit on number of cases
        case_id: Optional specific case ID to process
        
    Returns:
        List of case IDs
    """
    query = Document.query.filter(Document.document_type.in_(['case', 'case_study']))
    
    if case_id is not None:
        # Just get the specified case
        query = query.filter_by(id=case_id)
    else:
        # Order by ID to ensure consistent results
        query = query.order_by(Document.id)
        
    if limit is not None:
        query = query.limit(limit)
        
    cases = query.all()
    
    if not cases:
        if case_id is not None:
            logger.warning(f"No case found with ID {case_id}")
        else:
            logger.warning("No cases found")
        return []
    
    return [case.id for case in cases]

def run_predictions(experiment_id: int, case_ids: List[int]) -> Dict[str, Any]:
    """
    Run conclusion predictions for specified cases.
    
    Args:
        experiment_id: ID of the experiment
        case_ids: List of case IDs to process
        
    Returns:
        Dictionary with results
    """
    # Get the experiment
    experiment = ExperimentRun.query.get(experiment_id)
    if not experiment:
        raise ValueError(f"Experiment with ID {experiment_id} not found")
    
    # Update experiment config
    experiment.config['case_ids'] = [str(case_id) for case_id in case_ids]
    experiment.status = 'running'
    experiment.updated_at = datetime.utcnow()
    db.session.commit()
    
    # Initialize prediction service
    prediction_service = PredictionService()
    
    # Track results
    results = {
        'success_count': 0,
        'failure_count': 0,
        'cases': {}
    }
    
    # Process each case
    for i, case_id in enumerate(case_ids):
        logger.info(f"Processing case {case_id} ({i+1}/{len(case_ids)})")
        
        # Skip cases that already have predictions for this experiment
        existing_prediction = Prediction.query.filter_by(
            experiment_run_id=experiment_id,
            document_id=case_id,
            target='conclusion'
        ).first()
        
        if existing_prediction:
            logger.info(f"Skipping case {case_id}, already has prediction")
            results['cases'][case_id] = {
                'status': 'skipped',
                'reason': 'already_exists',
                'prediction_id': existing_prediction.id
            }
            continue
            
        try:
            # Generate conclusion prediction
            conclusion_result = prediction_service.generate_conclusion_prediction(
                document_id=case_id
            )
            
            if conclusion_result.get('success'):
                # Store conclusion prediction
                prediction = Prediction(
                    experiment_run_id=experiment_id,
                    document_id=case_id,
                    condition='proethica',
                    target='conclusion',
                    prediction_text=conclusion_result.get('prediction', ''),
                    prompt=conclusion_result.get('prompt', ''),
                    reasoning=conclusion_result.get('full_response', ''),
                    created_at=datetime.utcnow(),
                    meta_info={
                        'sections_included': conclusion_result.get('metadata', {}).get('sections_included', []),
                        'ontology_entities': conclusion_result.get('metadata', {}).get('ontology_entities', {}),
                        'similar_cases': conclusion_result.get('metadata', {}).get('similar_cases', []),
                        'validation_metrics': conclusion_result.get('metadata', {}).get('validation_metrics', {})
                    }
                )
                
                db.session.add(prediction)
                db.session.commit()
                
                results['success_count'] += 1
                results['cases'][case_id] = {
                    'status': 'success',
                    'prediction_id': prediction.id,
                    'validation_status': conclusion_result.get('metadata', {}).get(
                        'validation_metrics', {}).get('validation_status', 'unknown')
                }
                
                logger.info(f"Successfully processed case {case_id}")
            else:
                results['failure_count'] += 1
                results['cases'][case_id] = {
                    'status': 'failure',
                    'error': conclusion_result.get('error', 'Unknown error')
                }
                
                logger.error(f"Failed to process case {case_id}: {conclusion_result.get('error')}")
        
        except Exception as e:
            results['failure_count'] += 1
            results['cases'][case_id] = {
                'status': 'failure',
                'error': str(e)
            }
            
            logger.exception(f"Error processing case {case_id}: {str(e)}")
    
    # Update experiment status
    experiment.status = 'completed'
    experiment.updated_at = datetime.utcnow()
    db.session.commit()
    
    return results

def save_results(results: Dict[str, Any], file_path: str = None) -> None:
    """
    Save prediction results to a file.
    
    Args:
        results: Results dictionary
        file_path: Optional path to save file
    """
    if file_path is None:
        file_path = f"conclusion_predictions_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
    with open(file_path, 'w') as f:
        json.dump(results, f, indent=2)
        
    logger.info(f"Saved results to {file_path}")

def main() -> None:
    """Main script entry point."""
    parser = argparse.ArgumentParser(description='Run conclusion predictions on ethics cases')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--all', action='store_true', help='Process all cases')
    group.add_argument('--limit', type=int, help='Limit number of cases to process')
    group.add_argument('--case-id', type=int, help='Process specific case by ID')
    
    parser.add_argument('--name', default=f"Conclusion Predictions {datetime.now().strftime('%Y-%m-%d')}",
                        help='Name for the experiment')
    parser.add_argument('--description', help='Description for the experiment')
    parser.add_argument('--output', help='Output file path for results')
    
    args = parser.parse_args()
    
    try:
        # Set up environment
        setup_environment()
        
        # Create experiment
        experiment = create_experiment(args.name, args.description)
        
        # Get case IDs
        if args.all:
            case_ids = get_case_ids()
        elif args.case_id is not None:
            case_ids = get_case_ids(case_id=args.case_id)
        else:
            case_ids = get_case_ids(limit=args.limit)
            
        if not case_ids:
            logger.error("No cases to process")
            return
            
        logger.info(f"Processing {len(case_ids)} cases")
        
        # Run predictions
        results = run_predictions(experiment.id, case_ids)
        
        # Save results
        save_results(results, args.output)
        
        # Print summary
        print(f"\nConclusion Prediction Results:")
        print(f"Experiment ID: {experiment.id}")
        print(f"Successful predictions: {results['success_count']}")
        print(f"Failed predictions: {results['failure_count']}")
        print(f"Total cases processed: {len(case_ids)}")
        if args.output:
            print(f"Detailed results saved to: {args.output}")
        
    except Exception as e:
        logger.exception(f"Error in main: {str(e)}")
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
