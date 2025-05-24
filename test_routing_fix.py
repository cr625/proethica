#!/usr/bin/env python3
"""
Test script to verify that the experiment routing fixes are working.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, url_for
from app.routes.experiment import experiment_bp

def test_url_generation():
    """Test that all the fixed URL routes can be generated correctly."""
    app = Flask(__name__)
    app.config['SERVER_NAME'] = 'localhost:5000'
    app.config['APPLICATION_ROOT'] = '/'
    app.config['PREFERRED_URL_SCHEME'] = 'http'
    app.register_blueprint(experiment_bp)
    
    with app.app_context():
        try:
            # Test the fixed routes
            cases_url = url_for('experiment.cases', id=1)
            results_url = url_for('experiment.results', id=1)
            index_url = url_for('experiment.index')
            setup_url = url_for('experiment.conclusion_prediction_setup')
            
            print("✅ URL generation test PASSED")
            print(f"   - experiment.cases: {cases_url}")
            print(f"   - experiment.results: {results_url}")
            print(f"   - experiment.index: {index_url}")
            print(f"   - experiment.conclusion_prediction_setup: {setup_url}")
            return True
            
        except Exception as e:
            print(f"❌ URL generation test FAILED: {str(e)}")
            return False

if __name__ == "__main__":
    print("Testing experiment route fixes...")
    success = test_url_generation()
    
    if success:
        print("\n🎉 All routing fixes verified successfully!")
        print("The experiment interface should now work without BuildError issues.")
    else:
        print("\n💥 Routing issues still exist!")
    
    sys.exit(0 if success else 1)
