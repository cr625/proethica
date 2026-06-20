"""Experiment WTForms (conclusion / evaluation / double-blind)."""
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

# Form for double-blind evaluation
class DoubleBlindEvaluationForm(FlaskForm):
    """Simplified form for double-blind evaluation."""
    system_left = HiddenField()
    system_right = HiddenField()
    randomization_seed = HiddenField()
    
    reasoning_quality_left = HiddenField()
    reasoning_quality_right = HiddenField()
    ethical_grounding_left = HiddenField()
    ethical_grounding_right = HiddenField()
    practical_applicability_left = HiddenField()
    practical_applicability_right = HiddenField()
    coherence_left = HiddenField()
    coherence_right = HiddenField()
    
    overall_preference = HiddenField()
    comments = TextAreaField('Comments')
    submit = SubmitField('Submit Evaluation')
