"""Experiment blueprint package -- prediction + conclusion-prediction experiment routes."""
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

experiment_bp = Blueprint('experiment', __name__, url_prefix='/experiment')

from app.routes.experiment.prediction_routes import register_prediction_routes
from app.routes.experiment.conclusion_routes import register_conclusion_routes

register_prediction_routes(experiment_bp)
register_conclusion_routes(experiment_bp)


__all__ = ["experiment_bp"]
