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
from wtforms import StringField, TextAreaField, SelectField, BooleanField, SubmitField, FloatField
from wtforms.validators import DataRequired, NumberRange

from app import db
from app.models.document import Document
from app.models.document_section import DocumentSection
from app.models.experiment import ExperimentRun, Prediction, ExperimentEvaluation as Evaluation, PredictionTarget
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

# Form for setting up conclusion predictions
class ConclusionPredictionForm(FlaskForm):
    """Form for setting up conclusion predictions."""
    name = StringField('Prediction Experiment Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    use_ontology = BooleanField('Use Ontology Enhancement', default=True)
    submit = SubmitField('Create Conclusion Prediction Experiment')

# Form for evaluating predictions
class EvaluationForm(FlaskForm):
    """Form for evaluating prediction quality."""
    reasoning_quality = FloatField('Reasoning Quality (0-10)', validators=[NumberRange(min=0, max=10)])
    persuasiveness = FloatField('Persuasiveness (0-10)', validators=[NumberRange(min=0, max=10)])
    coherence = FloatField('Coherence (0-10)', validators=[NumberRange(min=0, max=10)])
    accuracy = BooleanField('Matches Original Conclusion')
    agreement = BooleanField('Agrees with Original Conclusion')
    support_quality = FloatField('Support Quality (0-10)', validators=[NumberRange(min=0, max=10)])
    preference_score = FloatField('Overall Preference (0-10)', validators=[NumberRange(min=0, max=10)])
    alignment_score = FloatField('Ethical Alignment (0-10)', validators=[NumberRange(min=0, max=10)])
    comments = TextAreaField('Comments')
    submit = SubmitField('Submit Evaluation')

@experiment_bp.route('/')
def index():
    """Experiment dashboard."""
    # Get all experiments
    experiments = ExperimentRun.query.order_by(ExperimentRun.created_at.desc()).limit(10).all()
    
    # Get all cases for quick prediction
    cases = Document.query.filter(Document.document_type.in_(['case', 'case_study'])).order_by(Document.title).all()
    
    # Add prediction status to cases
    for case in cases:
        # Check if case has any conclusion predictions
        case.has_prediction = Prediction.query.filter_by(
            document_id=case.id,
            target='conclusion'
        ).first() is not None
    
    # Calculate statistics
    total_cases = Document.query.filter(Document.document_type.in_(['case', 'case_study'])).count()
    total_experiments = ExperimentRun.query.count()
    completed_predictions = Prediction.query.filter_by(target='conclusion').count()
    
    return render_template('experiment/index.html', 
                          experiments=experiments,
                          cases=cases,
                          total_cases=total_cases,
                          total_experiments=total_experiments,
                          completed_predictions=completed_predictions)

@experiment_bp.route('/quick_predict/<int:case_id>', methods=['POST'])
def quick_predict(case_id):
    """Generate a quick conclusion prediction for a single case."""
    try:
        # Get the document
        document = Document.query.get_or_404(case_id)
        
        # Get prediction service
        prediction_service = PredictionService()
        
        # Check if prediction already exists
        existing_prediction = Prediction.query.filter_by(
            document_id=case_id,
            target='conclusion'
        ).first()
        
        if not existing_prediction:
            # Generate conclusion prediction
            logger.info(f"Generating quick conclusion prediction for document {case_id}")
            conclusion_result = prediction_service.generate_conclusion_prediction(
                document_id=case_id
            )
            
            if conclusion_result.get('success'):
                # Store conclusion prediction (without experiment context)
                prediction = Prediction(
                    experiment_run_id=None,  # No experiment context for quick predictions
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
                
                return jsonify({
                    'success': True,
                    'message': f"Conclusion prediction generated for '{document.title}'"
                })
            else:
                return jsonify({
                    'success': False,
                    'error': conclusion_result.get('error', 'Unknown error occurred')
                })
        else:
            return jsonify({
                'success': True,
                'message': f"Prediction already exists for '{document.title}'"
            })
            
    except Exception as e:
        logger.exception(f"Error in quick prediction for case {case_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Error generating prediction: {str(e)}"
        })

@experiment_bp.route('/case_comparison/<int:case_id>')
def case_comparison(case_id):
    """Compare original conclusion with predicted conclusion for a case."""
    # Get the document
    document = Document.query.get_or_404(case_id)
    
    # Get the prediction (any conclusion prediction for this case)
    prediction = Prediction.query.filter_by(
        document_id=case_id,
        target='conclusion'
    ).first()
    
    if not prediction:
        flash(f"No prediction found for '{document.title}'. Please generate a prediction first.", "warning")
        return redirect(url_for('experiment.index'))
    
    # Get document sections to retrieve original conclusion
    prediction_service = PredictionService()
    sections = prediction_service.get_document_sections(case_id, leave_out_conclusion=False)
    
    original_conclusion = sections.get('conclusion', 'No conclusion section found')
    
    # Create a minimal case comparison template context
    return render_template('experiment/case_comparison.html',
                          document=document,
                          prediction=prediction,
                          original_conclusion=original_conclusion)

# NEW EVALUATION ROUTES

@experiment_bp.route('/evaluate_prediction/<int:prediction_id>', methods=['GET', 'POST'])
def evaluate_prediction(prediction_id):
    """Evaluate a specific prediction."""
    # Get the prediction
    prediction = Prediction.query.get_or_404(prediction_id)
    
    # Get the experiment
    experiment = prediction.experiment_run
    if not experiment:
        flash("This prediction is not associated with an experiment", "warning")
        return redirect(url_for('experiment.index'))
    
    # Create evaluation form
    form = EvaluationForm()
    
    # Check if evaluation already exists
    existing_evaluation = Evaluation.query.filter_by(
        prediction_id=prediction_id,
        evaluator_id=request.remote_addr  # Simple evaluator tracking
    ).first()
    
    if existing_evaluation and request.method == 'GET':
        # Pre-populate form with existing evaluation
        form.reasoning_quality.data = existing_evaluation.reasoning_quality
        form.persuasiveness.data = existing_evaluation.persuasiveness
        form.coherence.data = existing_evaluation.coherence
        form.accuracy.data = existing_evaluation.accuracy
        form.agreement.data = existing_evaluation.agreement
        form.support_quality.data = existing_evaluation.support_quality
        form.preference_score.data = existing_evaluation.preference_score
        form.alignment_score.data = existing_evaluation.alignment_score
        form.comments.data = existing_evaluation.comments
    
    if form.validate_on_submit():
        try:
            if existing_evaluation:
                # Update existing evaluation
                evaluation = existing_evaluation
                evaluation.updated_at = datetime.utcnow()
            else:
                # Create new evaluation
                evaluation = Evaluation(
                    experiment_run_id=experiment.id,
                    prediction_id=prediction_id,
                    evaluator_id=request.remote_addr,
                    created_at=datetime.utcnow()
                )
            
            # Update evaluation fields
            evaluation.reasoning_quality = form.reasoning_quality.data
            evaluation.persuasiveness = form.persuasiveness.data
            evaluation.coherence = form.coherence.data
            evaluation.accuracy = form.accuracy.data
            evaluation.agreement = form.agreement.data
            evaluation.support_quality = form.support_quality.data
            evaluation.preference_score = form.preference_score.data
            evaluation.alignment_score = form.alignment_score.data
            evaluation.comments = form.comments.data
            
            if not existing_evaluation:
                db.session.add(evaluation)
            
            db.session.commit()
            
            flash("Evaluation submitted successfully", "success")
            return redirect(url_for('experiment.results', id=experiment.id))
            
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error saving evaluation: {str(e)}")
            flash(f"Error saving evaluation: {str(e)}", "danger")
    
    # Get document sections to retrieve original conclusion for comparison
    prediction_service = PredictionService()
    sections = prediction_service.get_document_sections(prediction.document_id, leave_out_conclusion=False)
    original_conclusion = sections.get('conclusion', 'No conclusion section found')
    
    return render_template('experiment/evaluate_prediction.html',
                          prediction=prediction,
                          experiment=experiment,
                          form=form,
                          original_conclusion=original_conclusion,
                          existing_evaluation=existing_evaluation)

@experiment_bp.route('/conclusion_setup', methods=['GET', 'POST'])
def conclusion_prediction_setup():
    """Setup a new conclusion prediction experiment."""
    form = ConclusionPredictionForm()
    
    # Get all available cases
    cases = Document.query.filter(Document.document_type.in_(['case', 'case_study'])).order_by(Document.title).all()
    
    if form.validate_on_submit():
        try:
            # Create new experiment
            experiment = ExperimentRun(
                name=form.name.data,
                description=form.description.data,
                experiment_type='conclusion_prediction',
                status='created',
                created_at=datetime.utcnow(),
                config={
                    'use_ontology': form.use_ontology.data,
                    'target': 'conclusion'
                }
            )
            
            db.session.add(experiment)
            db.session.commit()
            
            flash(f"Experiment '{experiment.name}' created successfully", "success")
            return redirect(url_for('experiment.cases', id=experiment.id))
            
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error creating experiment: {str(e)}")
            flash(f"Error creating experiment: {str(e)}", "danger")
    
    return render_template('experiment/conclusion_setup.html', form=form, cases=cases)

@experiment_bp.route('/<int:id>/cases', methods=['GET', 'POST'])
def cases(id):
    """Select cases for the experiment."""
    experiment = ExperimentRun.query.get_or_404(id)
    
    if request.method == 'POST':
        selected_cases = request.form.getlist('selected_cases')
        
        if not selected_cases:
            flash("Please select at least one case", "warning")
            return redirect(url_for('experiment.cases', id=id))
        
        try:
            # Store selected cases in experiment config
            experiment.config = experiment.config or {}
            experiment.config['selected_cases'] = [int(case_id) for case_id in selected_cases]
            experiment.status = 'configured'
            
            db.session.commit()
            
            flash(f"Selected {len(selected_cases)} cases for experiment", "success")
            return redirect(url_for('experiment.run_conclusion_predictions', experiment_id=id))
            
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error updating experiment: {str(e)}")
            flash(f"Error updating experiment: {str(e)}", "danger")
    
    # Get all available cases
    cases = Document.query.filter(Document.document_type.in_(['case', 'case_study'])).order_by(Document.title).all()
    
    return render_template('experiment/cases.html', experiment=experiment, cases=cases)

@experiment_bp.route('/<int:experiment_id>/run_conclusion_predictions', methods=['GET', 'POST'])
def run_conclusion_predictions(experiment_id):
    """Run conclusion predictions for selected cases."""
    experiment = ExperimentRun.query.get_or_404(experiment_id)
    
    if request.method == 'POST':
        try:
            selected_cases = experiment.config.get('selected_cases', [])
            use_ontology = experiment.config.get('use_ontology', True)
            
            if not selected_cases:
                flash("No cases selected for this experiment", "warning")
                return redirect(url_for('experiment.cases', id=experiment_id))
            
            # Update experiment status
            experiment.status = 'running'
            db.session.commit()
            
            # Get prediction service
            prediction_service = PredictionService()
            
            # Generate predictions for each selected case
            for case_id in selected_cases:
                logger.info(f"Generating predictions for case {case_id} in experiment {experiment_id}")
                
                # Generate ProEthica prediction
                proethica_result = prediction_service.generate_conclusion_prediction(
                    document_id=case_id,
                    use_ontology=use_ontology
                )
                
                if proethica_result.get('success'):
                    # Store ProEthica prediction
                    proethica_prediction = Prediction(
                        experiment_run_id=experiment.id,
                        document_id=case_id,
                        condition='proethica',
                        target='conclusion',
                        prediction_text=proethica_result.get('prediction', ''),
                        prompt=proethica_result.get('prompt', ''),
                        reasoning=proethica_result.get('full_response', ''),
                        created_at=datetime.utcnow(),
                        meta_info={
                            'sections_included': proethica_result.get('metadata', {}).get('sections_included', []),
                            'ontology_entities': proethica_result.get('metadata', {}).get('ontology_entities', {}),
                            'similar_cases': proethica_result.get('metadata', {}).get('similar_cases', []),
                            'validation_metrics': proethica_result.get('metadata', {}).get('validation_metrics', {}),
                            'mentioned_entities': proethica_result.get('metadata', {}).get('mentioned_entities', [])
                        }
                    )
                    
                    db.session.add(proethica_prediction)
                
                # Generate baseline prediction (without ontology)
                baseline_result = prediction_service.generate_conclusion_prediction(
                    document_id=case_id,
                    use_ontology=False
                )
                
                if baseline_result.get('success'):
                    # Store baseline prediction
                    baseline_prediction = Prediction(
                        experiment_run_id=experiment.id,
                        document_id=case_id,
                        condition='baseline',
                        target='conclusion',
                        prediction_text=baseline_result.get('prediction', ''),
                        prompt=baseline_result.get('prompt', ''),
                        reasoning=baseline_result.get('full_response', ''),
                        created_at=datetime.utcnow(),
                        meta_info={
                            'sections_included': baseline_result.get('metadata', {}).get('sections_included', []),
                            'validation_metrics': baseline_result.get('metadata', {}).get('validation_metrics', {})
                        }
                    )
                    
                    db.session.add(baseline_prediction)
            
            # Update experiment status
            experiment.status = 'completed'
            db.session.commit()
            
            flash("Experiment completed successfully", "success")
            return redirect(url_for('experiment.results', id=experiment.id))
            
        except Exception as e:
            db.session.rollback()
            experiment.status = 'failed'
            db.session.commit()
            logger.exception(f"Error running experiment: {str(e)}")
            flash(f"Error running experiment: {str(e)}", "danger")
    
    return render_template('experiment/conclusion_run.html', experiment=experiment)

@experiment_bp.route('/<int:id>/results')
def results(id):
    """View experiment results."""
    experiment = ExperimentRun.query.get_or_404(id)
    
    # Get all predictions for this experiment
    predictions = Prediction.query.filter_by(experiment_run_id=id).all()
    
    # Group predictions by document
    predictions_by_case = {}
    documents = {}
    
    for prediction in predictions:
        if prediction.document_id not in predictions_by_case:
            predictions_by_case[prediction.document_id] = []
            documents[prediction.document_id] = prediction.document
        
        predictions_by_case[prediction.document_id].append(prediction)
    
    # Get evaluation count
    evaluation_count = Evaluation.query.filter_by(experiment_run_id=id).count()
    
    # Calculate completion percentage
    total_expected = len(experiment.config.get('selected_cases', [])) * 2  # 2 predictions per case
    completed_predictions = len(predictions)
    completed_percentage = int((completed_predictions / max(total_expected, 1)) * 100)
    
    # Pagination setup (simplified)
    current_page = 1
    total_pages = 1
    
    return render_template('experiment/conclusion_results.html',
                          experiment=experiment,
                          predictions=predictions_by_case,
                          documents=documents,
                          evaluation_count=evaluation_count,
                          completed_percentage=completed_percentage,
                          current_page=current_page,
                          total_pages=total_pages,
                          filtered_results=False)

@experiment_bp.route('/<int:experiment_id>/compare/<int:case_id>')
def compare_predictions(experiment_id, case_id):
    """Compare baseline vs ProEthica predictions for a specific case."""
    experiment = ExperimentRun.query.get_or_404(experiment_id)
    document = Document.query.get_or_404(case_id)
    
    # Get predictions for this case in this experiment
    baseline_prediction = Prediction.query.filter_by(
        experiment_run_id=experiment_id,
        document_id=case_id,
        condition='baseline'
    ).first()
    
    proethica_prediction = Prediction.query.filter_by(
        experiment_run_id=experiment_id,
        document_id=case_id,
        condition='proethica'
    ).first()
    
    # Get original conclusion
    prediction_service = PredictionService()
    sections = prediction_service.get_document_sections(case_id, leave_out_conclusion=False)
    original_conclusion = sections.get('conclusion', 'No conclusion section found')
    
    return render_template('experiment/conclusion_comparison.html',
                          experiment=experiment,
                          document=document,
                          baseline_prediction=baseline_prediction,
                          proethica_prediction=proethica_prediction,
                          original_conclusion=original_conclusion)

@experiment_bp.route('/<int:experiment_id>/export')
def export_results(experiment_id):
    """Export experiment results as JSON."""
    experiment = ExperimentRun.query.get_or_404(experiment_id)
    
    # Get all predictions and evaluations
    predictions = Prediction.query.filter_by(experiment_run_id=experiment_id).all()
    evaluations = Evaluation.query.filter_by(experiment_run_id=experiment_id).all()
    
    # Build export data
    export_data = {
        'experiment': {
            'id': experiment.id,
            'name': experiment.name,
            'description': experiment.description,
            'type': experiment.experiment_type,
            'status': experiment.status,
            'created_at': experiment.created_at.isoformat(),
            'config': experiment.config
        },
        'predictions': [],
        'evaluations': []
    }
    
    # Add predictions
    for prediction in predictions:
        export_data['predictions'].append({
            'id': prediction.id,
            'document_id': prediction.document_id,
            'document_title': prediction.document.title if prediction.document else None,
            'condition': prediction.condition,
            'target': prediction.target,
            'prediction_text': prediction.prediction_text,
            'prompt': prediction.prompt,
            'reasoning': prediction.reasoning,
            'created_at': prediction.created_at.isoformat(),
            'meta_info': prediction.meta_info
        })
    
    # Add evaluations
    for evaluation in evaluations:
        export_data['evaluations'].append({
            'id': evaluation.id,
            'prediction_id': evaluation.prediction_id,
            'evaluator_id': evaluation.evaluator_id,
            'reasoning_quality': evaluation.reasoning_quality,
            'persuasiveness': evaluation.persuasiveness,
            'coherence': evaluation.coherence,
            'accuracy': evaluation.accuracy,
            'agreement': evaluation.agreement,
            'support_quality': evaluation.support_quality,
            'preference_score': evaluation.preference_score,
            'alignment_score': evaluation.alignment_score,
            'comments': evaluation.comments,
            'created_at': evaluation.created_at.isoformat()
        })
    
    # Return as JSON download
    response = jsonify(export_data)
    response.headers['Content-Disposition'] = f'attachment; filename=experiment_{experiment_id}_results.json'
    response.headers['Content-Type'] = 'application/json'
    
    return response

@experiment_bp.route('/setup_conclusion_prediction')
def setup_conclusion_prediction():
    """Alternative route for conclusion prediction setup."""
    return redirect(url_for('experiment.conclusion_prediction_setup'))
