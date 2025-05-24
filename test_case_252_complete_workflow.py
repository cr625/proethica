#!/usr/bin/env python3
"""
Test the complete end-to-end workflow for Case 252.

This script tests:
1. Experiment setup
2. Case 252 selection  
3. Prediction generation (baseline and ProEthica)
4. Results viewing
5. Evaluation workflow

This will serve as the example for the paper.
"""

import sys
import os
import requests
import json
import time
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

from app import create_app, db
from app.models.document import Document
from app.models.experiment import ExperimentRun, Prediction, ExperimentEvaluation
from app.services.experiment.prediction_service import PredictionService

def test_case_252_workflow():
    """Test the complete Case 252 workflow."""
    print("🚀 Testing Case 252 Complete Workflow")
    print("=" * 50)
    
    app = create_app()
    
    with app.app_context():
        try:
            # Step 1: Verify Case 252 exists
            print("\n📋 Step 1: Verify Case 252 exists")
            case_252 = Document.query.get(252)
            if not case_252:
                print("❌ Case 252 not found in database")
                return False
            
            print(f"✅ Found Case 252: '{case_252.title}'")
            print(f"   Type: {case_252.document_type}")
            
            # Step 2: Create a test experiment
            print("\n🧪 Step 2: Create test experiment")
            experiment_name = f"Case 252 Complete Test - {datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            experiment = ExperimentRun(
                name=experiment_name,
                description="Complete end-to-end test of Case 252 for paper documentation",
                experiment_type='conclusion_prediction',
                status='created',
                created_at=datetime.utcnow(),
                config={
                    'use_ontology': True,
                    'target': 'conclusion',
                    'selected_cases': [252]
                }
            )
            
            db.session.add(experiment)
            db.session.commit()
            
            print(f"✅ Created experiment: {experiment.name} (ID: {experiment.id})")
            
            # Step 3: Generate predictions
            print("\n🤖 Step 3: Generate predictions")
            prediction_service = PredictionService()
            
            # Update experiment status
            experiment.status = 'running'
            db.session.commit()
            
            # Generate ProEthica prediction
            print("   Generating ProEthica prediction...")
            proethica_result = prediction_service.generate_conclusion_prediction(
                document_id=252,
                use_ontology=True
            )
            
            if proethica_result.get('success'):
                proethica_prediction = Prediction(
                    experiment_run_id=experiment.id,
                    document_id=252,
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
                print("   ✅ ProEthica prediction generated")
                
                # Print first 200 chars of prediction for verification
                preview = proethica_prediction.prediction_text[:200] + "..." if len(proethica_prediction.prediction_text) > 200 else proethica_prediction.prediction_text
                print(f"   Preview: {preview}")
                
                # Show ontology entities if present
                if proethica_prediction.meta_info.get('mentioned_entities'):
                    entities = proethica_prediction.meta_info['mentioned_entities']
                    print(f"   Ontology entities mentioned: {entities[:5]}{'...' if len(entities) > 5 else ''}")
                
            else:
                print(f"   ❌ ProEthica prediction failed: {proethica_result.get('error')}")
                return False
            
            # Generate baseline prediction
            print("   Generating baseline prediction...")
            baseline_result = prediction_service.generate_conclusion_prediction(
                document_id=252,
                use_ontology=False
            )
            
            if baseline_result.get('success'):
                baseline_prediction = Prediction(
                    experiment_run_id=experiment.id,
                    document_id=252,
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
                print("   ✅ Baseline prediction generated")
                
                # Print first 200 chars of prediction for verification
                preview = baseline_prediction.prediction_text[:200] + "..." if len(baseline_prediction.prediction_text) > 200 else baseline_prediction.prediction_text
                print(f"   Preview: {preview}")
                
            else:
                print(f"   ❌ Baseline prediction failed: {baseline_result.get('error')}")
                return False
            
            # Complete experiment
            experiment.status = 'completed'
            db.session.commit()
            
            # Step 4: Verify predictions are stored
            print("\n📊 Step 4: Verify predictions")
            stored_predictions = Prediction.query.filter_by(experiment_run_id=experiment.id).all()
            
            if len(stored_predictions) == 2:
                print(f"✅ Both predictions stored successfully")
                for pred in stored_predictions:
                    print(f"   - {pred.condition}: {len(pred.prediction_text)} chars")
            else:
                print(f"❌ Expected 2 predictions, found {len(stored_predictions)}")
                return False
            
            # Step 5: Create sample evaluation
            print("\n⭐ Step 5: Create sample evaluation")
            
            # Evaluate the ProEthica prediction
            proethica_pred = next(p for p in stored_predictions if p.condition == 'proethica')
            
            sample_evaluation = ExperimentEvaluation(
                experiment_run_id=experiment.id,
                prediction_id=proethica_pred.id,
                evaluator_id="test_evaluator",
                reasoning_quality=8.5,
                persuasiveness=7.8,
                coherence=8.2,
                accuracy=True,
                agreement=True,
                support_quality=8.0,
                preference_score=8.3,
                alignment_score=9.1,
                comments="Strong ethical reasoning with good use of ontology entities. Clear logical flow and well-supported conclusions.",
                created_at=datetime.utcnow()
            )
            
            db.session.add(sample_evaluation)
            db.session.commit()
            
            print("✅ Sample evaluation created")
            print(f"   Reasoning Quality: {sample_evaluation.reasoning_quality}/10")
            print(f"   Ethical Alignment: {sample_evaluation.alignment_score}/10")
            print(f"   Overall Preference: {sample_evaluation.preference_score}/10")
            
            # Step 6: Generate summary report
            print("\n📈 Step 6: Generate summary report")
            
            # Get original conclusion for comparison
            sections = prediction_service.get_document_sections(252, leave_out_conclusion=False)
            original_conclusion = sections.get('conclusion', 'No conclusion found')
            
            report = {
                'experiment': {
                    'id': experiment.id,
                    'name': experiment.name,
                    'status': experiment.status,
                    'created_at': experiment.created_at.isoformat()
                },
                'case': {
                    'id': case_252.id,
                    'title': case_252.title,
                    'original_conclusion_length': len(original_conclusion)
                },
                'predictions': {
                    'proethica': {
                        'length': len(proethica_pred.prediction_text),
                        'entities_mentioned': len(proethica_pred.meta_info.get('mentioned_entities', [])),
                        'validation_status': proethica_pred.meta_info.get('validation_metrics', {}).get('validation_status', 'unknown')
                    },
                    'baseline': {
                        'length': len(baseline_prediction.prediction_text),
                        'entities_mentioned': 0  # Baseline doesn't use ontology
                    }
                },
                'evaluation': {
                    'reasoning_quality': sample_evaluation.reasoning_quality,
                    'persuasiveness': sample_evaluation.persuasiveness,
                    'coherence': sample_evaluation.coherence,
                    'accuracy': sample_evaluation.accuracy,
                    'alignment_score': sample_evaluation.alignment_score,
                    'preference_score': sample_evaluation.preference_score
                }
            }
            
            # Save report
            report_filename = f"case_252_complete_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_filename, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            print(f"✅ Report saved to: {report_filename}")
            
            # Step 7: Print URLs for manual verification
            print("\n🌐 Step 7: URLs for manual verification")
            print(f"   Experiment Results: http://127.0.0.1:3333/experiment/{experiment.id}/results")
            print(f"   ProEthica Evaluation: http://127.0.0.1:3333/experiment/evaluate_prediction/{proethica_pred.id}")
            print(f"   Comparison View: http://127.0.0.1:3333/experiment/{experiment.id}/compare/252")
            print(f"   Export Results: http://127.0.0.1:3333/experiment/{experiment.id}/export")
            
            print("\n🎉 SUCCESS: Complete workflow test passed!")
            print(f"Experiment ID {experiment.id} is ready for paper documentation.")
            
            return True
            
        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Run the test."""
    success = test_case_252_workflow()
    
    if success:
        print("\n✅ All tests passed - Case 252 workflow is complete and ready for paper!")
        sys.exit(0)
    else:
        print("\n❌ Tests failed - please check the errors above")
        sys.exit(1)

if __name__ == "__main__":
    main()
