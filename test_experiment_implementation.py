#!/usr/bin/env python3
"""
Test script for the ProEthica experiment implementation.

This script tests the basic functionality of the experiment interface,
including route registration, database models, and the prediction service.
"""

import os
import sys
import unittest
from flask import url_for
from app import create_app, db
from app.models.experiment import ExperimentRun, Prediction, Evaluation
from app.services.experiment.prediction_service import PredictionService

class ExperimentImplementationTestCase(unittest.TestCase):
    """Test case for experiment implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Create database tables for testing
        try:
            # Import models to ensure they're registered with SQLAlchemy
            from app.models.experiment import ExperimentRun, Prediction, Evaluation
            
            # Create tables
            db.create_all()
            print("Test database tables created.")
        except Exception as e:
            print(f"Error creating test tables: {str(e)}")
            sys.exit(1)
    
    def tearDown(self):
        """Clean up after tests."""
        # Drop experiment tables
        db.session.remove()
        try:
            db.drop_all()
            print("Test database tables dropped.")
        except Exception as e:
            print(f"Error dropping test tables: {str(e)}")
        
        self.app_context.pop()
    
    def test_experiment_routes_registered(self):
        """Test that experiment routes are properly registered."""
        with self.app.test_request_context():
            # Verify main experiment routes are registered
            experiment_index_url = url_for('experiment.index')
            experiment_setup_url = url_for('experiment.setup')
            
            self.assertEqual(experiment_index_url, '/experiment/')
            self.assertEqual(experiment_setup_url, '/experiment/setup')
            
            # Test route access
            response = self.client.get(experiment_index_url)
            self.assertEqual(response.status_code, 200)
    
    def test_experiment_models(self):
        """Test experiment models."""
        # Create test experiment
        experiment = ExperimentRun(
            name="Test Experiment",
            description="Test description",
            created_by="test_user",
            config={"leave_out_conclusion": True},
            status="created"
        )
        
        db.session.add(experiment)
        db.session.commit()
        
        # Verify experiment was created
        saved_experiment = ExperimentRun.query.filter_by(name="Test Experiment").first()
        self.assertIsNotNone(saved_experiment)
        self.assertEqual(saved_experiment.name, "Test Experiment")
        self.assertEqual(saved_experiment.status, "created")
    
    def test_prediction_service(self):
        """Test prediction service."""
        # Initialize prediction service
        prediction_service = PredictionService()
        
        # Verify service methods are available
        self.assertTrue(hasattr(prediction_service, 'generate_baseline_prediction'))
        
        # Test document section extraction (with mock data)
        # Note: This is a basic functionality test without actual data
        
        # More comprehensive tests would require test fixtures with actual documents
        # that would be set up in a full testing environment

def run_tests():
    """Run test suite."""
    unittest.main()

if __name__ == "__main__":
    run_tests()
