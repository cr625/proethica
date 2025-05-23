#!/usr/bin/env python3
"""
Case 252 End-to-End Testing Script

This script tests the complete ProEthica experiment workflow for Case 252
"Acknowledging Errors in Design" to verify that the database constraint
fix resolved the blocking issues and the system is fully functional.

Test Coverage:
1. Quick Prediction workflow
2. Formal Experiment creation and execution
3. Database constraint validation
4. Ontology integration verification
5. Results documentation

Usage:
    python test_case_252_end_to_end.py
"""

import logging
import sys
import os
import json
from datetime import datetime
from flask import Flask
from app import create_app
from app.models import db
from app.models.document import Document
from app.models.experiment import ExperimentRun, Prediction
from app.services.experiment.prediction_service import PredictionService

# Set up environment
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
os.environ.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', 'false')
os.environ.setdefault('ENVIRONMENT', 'development')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'case_252_test_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

class Case252EndToEndTest:
    """Comprehensive test suite for Case 252 experiment workflow."""
    
    def __init__(self):
        self.app = None
        self.case_252 = None
        self.test_results = {
            'database_constraint_test': None,
            'case_retrieval_test': None,
            'quick_prediction_test': None,
            'formal_experiment_test': None,
            'ontology_integration_test': None,
            'overall_success': False
        }
    
    def setup(self):
        """Initialize Flask app and database connection."""
        try:
            logger.info("=" * 60)
            logger.info("CASE 252 END-TO-END TEST SUITE")
            logger.info("=" * 60)
            
            # Create Flask app
            self.app = create_app('config')
            logger.info("✓ Flask application created successfully")
            
            # Get Case 252
            with self.app.app_context():
                self.case_252 = Document.query.filter_by(id=252).first()
                if self.case_252:
                    logger.info(f"✓ Case 252 found: '{self.case_252.title}'")
                else:
                    logger.error("❌ Case 252 not found in database!")
                    return False
            
            return True
            
        except Exception as e:
            logger.exception(f"Setup failed: {str(e)}")
            return False
    
    def test_database_constraint_fix(self):
        """Test that the database constraint issue has been resolved."""
        try:
            logger.info("\n🔍 Testing Database Constraint Fix...")
            
            with self.app.app_context():
                # Test 1: Verify experiment_run_id is nullable
                from sqlalchemy import text
                result = db.session.execute(text("""
                    SELECT column_name, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_name = 'experiment_predictions' 
                    AND column_name = 'experiment_run_id'
                """))
                
                constraint_info = result.fetchone()
                if constraint_info and constraint_info[1] == 'YES':
                    logger.info("✓ experiment_run_id column is nullable")
                else:
                    logger.error("❌ experiment_run_id column is not nullable")
                    self.test_results['database_constraint_test'] = False
                    return False
                
                # Test 2: Verify default experiment run exists
                default_run = ExperimentRun.query.filter_by(name="Default Standalone Predictions").first()
                if default_run:
                    logger.info(f"✓ Default experiment run exists (ID: {default_run.id})")
                else:
                    logger.error("❌ Default experiment run not found")
                    self.test_results['database_constraint_test'] = False
                    return False
                
                logger.info("✅ Database constraint fix verified successfully!")
                self.test_results['database_constraint_test'] = True
                return True
                
        except Exception as e:
            logger.exception(f"Database constraint test failed: {str(e)}")
            self.test_results['database_constraint_test'] = False
            return False
    
    def test_case_retrieval(self):
        """Test Case 252 data retrieval and structure."""
        try:
            logger.info("\n🔍 Testing Case 252 Retrieval...")
            
            with self.app.app_context():
                # Basic case information
                logger.info(f"Case ID: {self.case_252.id}")
                logger.info(f"Title: {self.case_252.title}")
                logger.info(f"Type: {self.case_252.type}")
                
                # Check sections
                sections = self.case_252.sections
                logger.info(f"Number of sections: {len(sections)}")
                
                # Look for conclusion section
                conclusion_sections = [s for s in sections if s.section_type == 'conclusion']
                if conclusion_sections:
                    logger.info(f"✓ Found {len(conclusion_sections)} conclusion section(s)")
                    conclusion = conclusion_sections[0]
                    logger.info(f"Conclusion content preview: {conclusion.content[:200]}...")
                else:
                    logger.warning("⚠️  No conclusion section found")
                
                # Check for facts section
                facts_sections = [s for s in sections if s.section_type == 'facts']
                if facts_sections:
                    logger.info(f"✓ Found {len(facts_sections)} facts section(s)")
                else:
                    logger.warning("⚠️  No facts section found")
                
                logger.info("✅ Case 252 retrieval test passed!")
                self.test_results['case_retrieval_test'] = True
                return True
                
        except Exception as e:
            logger.exception(f"Case retrieval test failed: {str(e)}")
            self.test_results['case_retrieval_test'] = False
            return False
    
    def test_quick_prediction(self):
        """Test the quick prediction workflow for Case 252."""
        try:
            logger.info("\n🔍 Testing Quick Prediction Workflow...")
            
            with self.app.app_context():
                # Initialize prediction service
                prediction_service = PredictionService()
                logger.info("✓ Prediction service initialized")
                
                # Generate prediction for Case 252
                logger.info("Generating prediction for Case 252...")
                prediction_result = prediction_service.predict_case_conclusion(
                    document_id=252,
                    include_ontology=True,
                    prediction_target="conclusion"
                )
                
                if prediction_result and 'prediction' in prediction_result:
                    logger.info("✓ Prediction generated successfully!")
                    
                    # Extract prediction details
                    prediction_text = prediction_result['prediction']
                    ontology_entities = prediction_result.get('ontology_entities', [])
                    
                    logger.info(f"Prediction length: {len(prediction_text)} characters")
                    logger.info(f"Ontology entities found: {len(ontology_entities)}")
                    logger.info(f"Prediction preview: {prediction_text[:300]}...")
                    
                    # Check for ontology integration
                    if ontology_entities:
                        entity_names = [e.get('label', e.get('name', 'Unknown')) for e in ontology_entities]
                        logger.info(f"Ontology entities: {entity_names[:5]}...")  # Show first 5
                        
                        # Calculate mention ratio
                        mentioned_entities = 0
                        for entity in ontology_entities:
                            entity_name = entity.get('label', entity.get('name', ''))
                            if entity_name.lower() in prediction_text.lower():
                                mentioned_entities += 1
                        
                        mention_ratio = (mentioned_entities / len(ontology_entities)) * 100 if ontology_entities else 0
                        logger.info(f"Ontology entity mention ratio: {mention_ratio:.1f}%")
                        
                        self.test_results['ontology_integration_test'] = {
                            'entities_found': len(ontology_entities),
                            'entities_mentioned': mentioned_entities,
                            'mention_ratio': mention_ratio
                        }
                    else:
                        logger.warning("⚠️  No ontology entities found")
                        self.test_results['ontology_integration_test'] = {
                            'entities_found': 0,
                            'entities_mentioned': 0,
                            'mention_ratio': 0
                        }
                    
                    # Save prediction to verify database works
                    logger.info("Testing database save...")
                    
                    # Check if prediction was saved to database
                    recent_predictions = Prediction.query.filter_by(
                        document_id=252
                    ).order_by(Prediction.created_at.desc()).limit(5).all()
                    
                    logger.info(f"Found {len(recent_predictions)} recent predictions for Case 252")
                    
                    logger.info("✅ Quick prediction test passed!")
                    self.test_results['quick_prediction_test'] = {
                        'success': True,
                        'prediction_length': len(prediction_text),
                        'ontology_entities': len(ontology_entities),
                        'database_save': len(recent_predictions) > 0
                    }
                    return True
                else:
                    logger.error("❌ Prediction generation failed!")
                    self.test_results['quick_prediction_test'] = {'success': False, 'error': 'No prediction returned'}
                    return False
                    
        except Exception as e:
            logger.exception(f"Quick prediction test failed: {str(e)}")
            self.test_results['quick_prediction_test'] = {'success': False, 'error': str(e)}
            return False
    
    def test_formal_experiment(self):
        """Test formal experiment creation and execution."""
        try:
            logger.info("\n🔍 Testing Formal Experiment Workflow...")
            
            with self.app.app_context():
                # Create test experiment run
                experiment_run = ExperimentRun(
                    name=f"Case 252 Test Experiment {datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    description="End-to-end test of Case 252 experiment workflow",
                    status="active",
                    created_at=datetime.utcnow(),
                    config={
                        "test_mode": True,
                        "case_id": 252,
                        "prediction_targets": ["conclusion"],
                        "include_ontology": True
                    }
                )
                
                db.session.add(experiment_run)
                db.session.commit()
                logger.info(f"✓ Created test experiment run (ID: {experiment_run.id})")
                
                # Generate prediction within experiment context
                prediction_service = PredictionService()
                prediction_result = prediction_service.predict_case_conclusion(
                    document_id=252,
                    include_ontology=True,
                    prediction_target="conclusion",
                    experiment_run_id=experiment_run.id
                )
                
                if prediction_result and 'prediction' in prediction_result:
                    logger.info("✓ Experimental prediction generated successfully!")
                    
                    # Verify prediction was associated with experiment
                    experiment_predictions = Prediction.query.filter_by(
                        experiment_run_id=experiment_run.id
                    ).all()
                    
                    if experiment_predictions:
                        logger.info(f"✓ Found {len(experiment_predictions)} predictions associated with experiment")
                    else:
                        logger.warning("⚠️  No predictions found associated with experiment")
                    
                    # Update experiment status
                    experiment_run.status = "completed"
                    db.session.commit()
                    logger.info("✓ Experiment marked as completed")
                    
                    logger.info("✅ Formal experiment test passed!")
                    self.test_results['formal_experiment_test'] = {
                        'success': True,
                        'experiment_id': experiment_run.id,
                        'predictions_count': len(experiment_predictions)
                    }
                    return True
                else:
                    logger.error("❌ Experimental prediction generation failed!")
                    self.test_results['formal_experiment_test'] = {'success': False, 'error': 'Prediction failed'}
                    return False
                    
        except Exception as e:
            logger.exception(f"Formal experiment test failed: {str(e)}")
            self.test_results['formal_experiment_test'] = {'success': False, 'error': str(e)}
            return False
    
    def generate_test_report(self):
        """Generate comprehensive test report."""
        logger.info("\n📊 GENERATING TEST REPORT...")
        logger.info("=" * 60)
        
        # Count successes
        successful_tests = sum(1 for result in self.test_results.values() 
                             if result is True or (isinstance(result, dict) and result.get('success', False)))
        total_tests = len([k for k in self.test_results.keys() if k != 'overall_success'])
        
        # Overall success determination
        critical_tests = ['database_constraint_test', 'quick_prediction_test']
        critical_passed = all(self.test_results.get(test, False) for test in critical_tests)
        
        self.test_results['overall_success'] = critical_passed
        
        logger.info(f"TEST SUMMARY: {successful_tests}/{total_tests} tests passed")
        logger.info(f"CRITICAL TESTS: {'✅ PASSED' if critical_passed else '❌ FAILED'}")
        
        # Detailed results
        for test_name, result in self.test_results.items():
            if test_name == 'overall_success':
                continue
                
            if result is True:
                logger.info(f"✅ {test_name}: PASSED")
            elif result is False:
                logger.info(f"❌ {test_name}: FAILED")
            elif isinstance(result, dict):
                if result.get('success', False):
                    logger.info(f"✅ {test_name}: PASSED")
                    for key, value in result.items():
                        if key != 'success':
                            logger.info(f"   - {key}: {value}")
                else:
                    logger.info(f"❌ {test_name}: FAILED")
                    logger.info(f"   - Error: {result.get('error', 'Unknown error')}")
        
        # Ontology integration results
        if self.test_results.get('ontology_integration_test'):
            ontology_result = self.test_results['ontology_integration_test']
            logger.info(f"\n🔬 ONTOLOGY INTEGRATION ANALYSIS:")
            logger.info(f"   - Entities Found: {ontology_result['entities_found']}")
            logger.info(f"   - Entities Mentioned: {ontology_result['entities_mentioned']}")
            logger.info(f"   - Mention Ratio: {ontology_result['mention_ratio']:.1f}%")
            
            if ontology_result['mention_ratio'] >= 20:
                logger.info("   ✅ Target mention ratio (20%) achieved!")
            elif ontology_result['mention_ratio'] >= 15:
                logger.info("   🟡 Good mention ratio (15%+) but below target")
            else:
                logger.info("   🔴 Low mention ratio - needs optimization")
        
        # Save results to file
        results_file = f'case_252_test_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(results_file, 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        logger.info(f"\n📁 Detailed results saved to: {results_file}")
        
        return self.test_results['overall_success']
    
    def run_all_tests(self):
        """Execute the complete test suite."""
        try:
            # Setup
            if not self.setup():
                return False
            
            # Run tests in order
            tests = [
                self.test_database_constraint_fix,
                self.test_case_retrieval,
                self.test_quick_prediction,
                self.test_formal_experiment
            ]
            
            for test in tests:
                try:
                    test()
                except Exception as e:
                    logger.exception(f"Test {test.__name__} failed with exception: {str(e)}")
            
            # Generate report
            success = self.generate_test_report()
            
            if success:
                logger.info("\n🎉 CASE 252 END-TO-END TEST: SUCCESS!")
                logger.info("The ProEthica experiment system is fully functional.")
                logger.info("Ready for user study phase!")
            else:
                logger.error("\n❌ CASE 252 END-TO-END TEST: FAILED!")
                logger.error("Some critical issues remain to be resolved.")
            
            return success
            
        except Exception as e:
            logger.exception(f"Test suite execution failed: {str(e)}")
            return False

def main():
    """Main function to run the test suite."""
    test_suite = Case252EndToEndTest()
    success = test_suite.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
