#!/usr/bin/env python3
"""
Simple test of the Case 252 workflow components.
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.abspath('.'))

def test_basic_imports():
    """Test that we can import the necessary components."""
    try:
        from app import create_app, db
        from app.models.document import Document
        from app.models.experiment import ExperimentRun, Prediction, ExperimentEvaluation
        print("✅ Successfully imported all required modules")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_database_connection():
    """Test database connection and Case 252."""
    try:
        from app import create_app, db
        from app.models.document import Document
        
        app = create_app()
        
        with app.app_context():
            # Test database connection
            case_252 = Document.query.get(252)
            if case_252:
                print(f"✅ Found Case 252: '{case_252.title}'")
                return True
            else:
                print("❌ Case 252 not found in database")
                return False
                
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_prediction_service():
    """Test prediction service initialization."""
    try:
        from app.services.experiment.prediction_service import PredictionService
        
        service = PredictionService()
        print("✅ PredictionService initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ PredictionService test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Running Simple Workflow Tests")
    print("=" * 40)
    
    tests = [
        ("Import Test", test_basic_imports),
        ("Database Test", test_database_connection),
        ("Prediction Service Test", test_prediction_service)
    ]
    
    passed = 0
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        if test_func():
            passed += 1
        else:
            print(f"Failed: {test_name}")
    
    print(f"\n📊 Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("✅ All basic tests passed! System is ready.")
        return True
    else:
        print("❌ Some tests failed. Please check the system.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
