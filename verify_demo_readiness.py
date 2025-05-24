#!/usr/bin/env python3
"""
Quick verification script to test ProEthica demo readiness
Tests database constraints, prediction generation, and system status
"""

import os
import sys
sys.path.append('/home/chris/ai-ethical-dm')

# Set up environment variables from launch.json
os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
os.environ['ENVIRONMENT'] = 'development'
os.environ['MCP_SERVER_PORT'] = '5001'
os.environ['MCP_SERVER_URL'] = 'http://localhost:5001'
os.environ['SQLALCHEMY_TRACK_MODIFICATIONS'] = 'false'
os.environ['USE_MOCK_GUIDELINE_RESPONSES'] = 'false'
os.environ['FORCE_MOCK_LLM'] = 'false'

import logging
from flask import Flask
from app import create_app, db
from app.models.experiment import Prediction, ExperimentRun
from app.services.experiment.prediction_service import PredictionService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_database_constraint():
    """Test that experiment_run_id can be NULL in predictions table"""
    try:
        app = create_app()
        with app.app_context():
            # Try to create a prediction with NULL experiment_run_id
            test_prediction = Prediction(
                experiment_run_id=None,  # This should work now
                document_id=252,
                condition='proethica',
                target='conclusion',
                prediction_text='Test prediction',
                reasoning='Test reasoning',
                prompt='Test prompt',
                meta_info={'test': True}
            )
            
            db.session.add(test_prediction)
            db.session.commit()
            
            # Clean up
            db.session.delete(test_prediction)
            db.session.commit()
            
            logger.info("✅ Database constraint fix verified - NULL experiment_run_id works")
            return True
            
    except Exception as e:
        logger.error(f"❌ Database constraint test failed: {e}")
        return False

def test_case_252_prediction():
    """Test Case 252 prediction generation"""
    try:
        app = create_app()
        with app.app_context():
            prediction_service = PredictionService()
            
            # Test prediction generation for Case 252
            result = prediction_service.generate_prediction(
                document_id=252,
                condition='proethica',
                target='conclusion'
            )
            
            if result and 'prediction' in result:
                logger.info("✅ Case 252 prediction generation successful")
                logger.info(f"   Prediction length: {len(result['prediction'])} characters")
                return True
            else:
                logger.error("❌ Case 252 prediction generation failed - no prediction returned")
                return False
                
    except Exception as e:
        logger.error(f"❌ Case 252 prediction test failed: {e}")
        return False

def check_template_attributes():
    """Check that templates use meta_info (not meta_data)"""
    template_path = "/home/chris/ai-ethical-dm/app/templates/experiment/case_comparison.html"
    try:
        with open(template_path, 'r') as f:
            content = f.read()
            
        if 'meta_data' in content:
            logger.error("❌ Template still contains meta_data references")
            return False
        
        if 'meta_info' in content:
            logger.info("✅ Template correctly uses meta_info")
            return True
        else:
            logger.warning("⚠️  Template doesn't contain meta_info references")
            return True
            
    except Exception as e:
        logger.error(f"❌ Template check failed: {e}")
        return False

def main():
    """Run all verification tests"""
    logger.info("🚀 Starting ProEthica Demo Readiness Verification")
    logger.info("=" * 60)
    
    tests = [
        ("Database Constraint Fix", test_database_constraint),
        ("Case 252 Prediction Generation", test_case_252_prediction),
        ("Template Attributes", check_template_attributes)
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n📋 Testing: {test_name}")
        result = test_func()
        results.append((test_name, result))
    
    logger.info("\n" + "=" * 60)
    logger.info("📊 VERIFICATION SUMMARY")
    logger.info("=" * 60)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"   {status} - {test_name}")
        if not result:
            all_passed = False
    
    if all_passed:
        logger.info("\n🎉 All tests passed! System ready for demo.")
        return 0
    else:
        logger.error("\n💥 Some tests failed. Check logs above.")
        return 1

if __name__ == "__main__":
    exit(main())
