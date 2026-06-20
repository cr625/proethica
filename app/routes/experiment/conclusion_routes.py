"""Conclusion-prediction routes (setup, cases, run, results, compare, export)."""
import logging
import json
import hashlib
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField, SubmitField, FloatField, HiddenField
from wtforms.validators import DataRequired, NumberRange

from app import db
from app.models import Document
from app.models.document_section import DocumentSection
from app.models.experiment import ExperimentRun, Prediction, ExperimentEvaluation as Evaluation
from app.services.experiment.prediction_service import PredictionService

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
from app.routes.experiment.forms import (
    ConclusionPredictionForm,
)


def register_conclusion_routes(bp):
    @bp.route('/conclusion_setup', methods=['GET', 'POST'])
    def conclusion_prediction_setup():
        """Setup a new ethical determination study."""
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

    @bp.route('/<int:id>/cases', methods=['GET', 'POST'])
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

    @bp.route('/<int:experiment_id>/run_conclusion_predictions', methods=['GET', 'POST'])
    def run_conclusion_predictions(experiment_id):
        """Generate ethical determinations for selected cases in a validation study."""
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
            
                # Generate determinations for each selected case
                for case_id in selected_cases:
                    logger.info(f"Generating ethical determinations for case {case_id} in study {experiment_id}")
                
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

    @bp.route('/<int:id>/results')
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

    @bp.route('/<int:experiment_id>/compare/<int:case_id>')
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

    @bp.route('/<int:experiment_id>/export')
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

    @bp.route('/setup_conclusion_prediction')
    def setup_conclusion_prediction():
        """Alternative route for conclusion prediction setup."""
        return redirect(url_for('experiment.conclusion_prediction_setup'))
