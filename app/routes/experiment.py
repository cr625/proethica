"""
Routes for the ProEthica experiment interface.

This module provides routes for setting up experiments, generating predictions,
and evaluating results under different experimental conditions.
"""

import logging
import json
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired

from app import db
from app.models.document import Document
from app.models.document_section import DocumentSection
from app.models.experiment import ExperimentRun, Prediction, ExperimentEvaluation as Evaluation
from app.services.experiment.prediction_service import PredictionService

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create blueprint
experiment_bp = Blueprint('experiment', __name__, url_prefix='/experiment')

# Form for creating experiments
class ExperimentForm(FlaskForm):
    """Form for creating a new experiment."""
    name = StringField('Experiment Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    leave_out_conclusion = BooleanField('Leave Out Conclusion', default=True)
    submit = SubmitField('Create Experiment')

@experiment_bp.route('/')
def index():
    """Experiment dashboard."""
    # Get all experiments
    experiments = ExperimentRun.query.order_by(ExperimentRun.created_at.desc()).all()
    
    return render_template('experiment/index.html', 
                          experiments=experiments)

@experiment_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    """Setup a new experiment."""
    form = ExperimentForm()
    
    if form.validate_on_submit():
        try:
            # Create new experiment
            experiment = ExperimentRun(
                name=form.name.data,
                description=form.description.data,
                created_at=datetime.utcnow(),
                created_by=request.remote_addr,  # Simple user tracking
                config={
                    'leave_out_conclusion': form.leave_out_conclusion.data
                },
                status='created'
            )
            
            # Save to database
            db.session.add(experiment)
            db.session.commit()
            
            flash(f"Experiment '{experiment.name}' created successfully", "success")
            return redirect(url_for('experiment.cases', id=experiment.id))
            
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error creating experiment: {str(e)}")
            flash(f"Error creating experiment: {str(e)}", "danger")
    
    return render_template('experiment/setup.html', form=form)

@experiment_bp.route('/<int:id>/cases', methods=['GET', 'POST'])
def cases(id):
    """Select cases for an experiment."""
    # Get the experiment
    experiment = ExperimentRun.query.get_or_404(id)
    
    if request.method == 'POST':
        # Get selected case IDs
        case_ids = request.form.getlist('case_ids')
        
        if not case_ids:
            flash("No cases selected", "warning")
            return redirect(url_for('experiment.cases', id=id))
        
        # Update experiment config
        config = experiment.config or {}
        config['case_ids'] = case_ids
        experiment.config = config
        
        # Update status
        experiment.status = 'configured'
        experiment.updated_at = datetime.utcnow()
        
        # Save to database
        db.session.commit()
        
        flash(f"{len(case_ids)} cases selected for experiment", "success")
        return redirect(url_for('experiment.run', id=id))
    
    # Get all cases
    cases = Document.query.filter(Document.document_type.in_(['case', 'case_study'])).order_by(Document.title).all()
    
    # Check if cases already selected
    selected_cases = []
    if experiment.config and 'case_ids' in experiment.config:
        selected_case_ids = [int(case_id) for case_id in experiment.config['case_ids']]
        selected_cases = Document.query.filter(Document.id.in_(selected_case_ids)).all()
    
    return render_template('experiment/cases.html',
                          experiment=experiment,
                          cases=cases,
                          selected_cases=selected_cases)

@experiment_bp.route('/<int:id>/run')
def run(id):
    """Run an experiment."""
    # Get the experiment
    experiment = ExperimentRun.query.get_or_404(id)
    
    # Check if cases are selected
    if not experiment.config or 'case_ids' not in experiment.config:
        flash("No cases selected for experiment", "warning")
        return redirect(url_for('experiment.cases', id=id))
    
    return render_template('experiment/run.html',
                          experiment=experiment)

@experiment_bp.route('/<int:id>/predict', methods=['POST'])
def predict(id):
    """Generate baseline and ProEthica predictions for experiment cases."""
    # Get the experiment
    experiment = ExperimentRun.query.get_or_404(id)
    
    try:
        # Get prediction service
        prediction_service = PredictionService()
        
        # Get case IDs from config
        if not experiment.config or 'case_ids' not in experiment.config:
            return jsonify({
                'success': False,
                'error': 'No cases selected for experiment'
            })
        
        case_ids = experiment.config['case_ids']
        leave_out_conclusion = experiment.config.get('leave_out_conclusion', True)
        
        # Get total count for progress tracking
        total_cases = len(case_ids)
        case_processed = 0
        
        # Update experiment status
        experiment.status = 'running'
        db.session.commit()
        
        # Process each case
        for case_id in case_ids:
            # Convert to integer
            case_id = int(case_id)
            
            # Skip cases that already have predictions for this experiment
            existing_prediction = Prediction.query.filter_by(
                experiment_run_id=id,
                document_id=case_id
            ).first()
            
            if not existing_prediction:
                # Generate baseline prediction
                baseline_result = prediction_service.generate_baseline_prediction(
                    document_id=case_id,
                    leave_out_conclusion=leave_out_conclusion
                )
                
                if baseline_result.get('success'):
                    # Store baseline prediction
                    prediction = Prediction(
                        experiment_run_id=id,
                        document_id=case_id,
                        condition='baseline',
                        prediction_text=baseline_result.get('prediction', ''),
                        prompt=baseline_result.get('prompt', ''),
                        created_at=datetime.utcnow(),
                        metadata={
                            'sections_included': baseline_result.get('metadata', {}).get('sections_included', []),
                            'similar_cases': baseline_result.get('metadata', {}).get('similar_cases', []),
                            'leave_out_conclusion': leave_out_conclusion
                        }
                    )
                    
                    db.session.add(prediction)
                    db.session.commit()
                    
                # ProEthica prediction will be added in a future implementation
            
            case_processed += 1
        
        # Update experiment status
        experiment.status = 'completed'
        experiment.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f"Predictions generated for {case_processed} cases"
        })
        
    except Exception as e:
        # Update experiment status
        experiment.status = 'failed'
        db.session.commit()
        
        logger.exception(f"Error generating predictions: {str(e)}")
        
        return jsonify({
            'success': False,
            'error': f"Error generating predictions: {str(e)}"
        })

@experiment_bp.route('/<int:id>/results')
def results(id):
    """View experiment results."""
    # Get the experiment
    experiment = ExperimentRun.query.get_or_404(id)
    
    # Get predictions
    predictions = Prediction.query.filter_by(experiment_run_id=id).all()
    
    # Group predictions by document
    grouped_predictions = {}
    
    for prediction in predictions:
        if prediction.document_id not in grouped_predictions:
            grouped_predictions[prediction.document_id] = {
                'document': prediction.document,
                'predictions': {}
            }
        
        grouped_predictions[prediction.document_id]['predictions'][prediction.condition] = prediction
    
    return render_template('experiment/results.html',
                          experiment=experiment,
                          grouped_predictions=grouped_predictions)

@experiment_bp.route('/<int:id>/case/<int:doc_id>')
def case_results(id, doc_id):
    """View results for a specific case."""
    # Get the experiment
    experiment = ExperimentRun.query.get_or_404(id)
    
    # Get the document
    document = Document.query.get_or_404(doc_id)
    
    # Get predictions
    predictions = Prediction.query.filter_by(
        experiment_run_id=id,
        document_id=doc_id
    ).all()
    
    # Create dictionary of predictions by condition
    prediction_dict = {p.condition: p for p in predictions}
    
    # Get document sections
    prediction_service = PredictionService()
    sections = prediction_service.get_document_sections(doc_id, leave_out_conclusion=False)
    
    return render_template('experiment/case_results.html',
                          experiment=experiment,
                          document=document,
                          predictions=prediction_dict,
                          sections=sections)
