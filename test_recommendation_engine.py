#!/usr/bin/env python3
"""Test script for the recommendation engine functionality."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables for testing
os.environ['BYPASS_AUTH'] = 'true'
os.environ['ENVIRONMENT'] = 'development'

from app import create_app
from app.models import db
from app.models.document import Document


def test_recommendation_engine():
    """Test the recommendation engine functionality."""
    print("=" * 60)
    print("Recommendation Engine Test")
    print("=" * 60)
    
    # Create app context
    app = create_app('config')
    
    with app.app_context():
        print("\n1. Testing recommendation engine import:")
        try:
            from app.services.recommendation_engine import recommendation_engine, RecommendationEngine
            print("   ✓ Successfully imported recommendation engine")
            print(f"   ✓ Engine type: {type(recommendation_engine)}")
        except Exception as e:
            print(f"   ✗ Error importing recommendation engine: {e}")
            return
        
        print("\n2. Finding cases with potential for recommendations:")
        try:
            # Find cases that might have associations
            cases = Document.query.filter(
                Document.doc_metadata.op('->>')('case_number').isnot(None)
            ).limit(3).all()
            
            print(f"   ✓ Found {len(cases)} cases in database")
            
            for case in cases:
                case_number = case.doc_metadata.get('case_number', 'Unknown')
                print(f"     - Case {case.id}: {case.title} (Case #{case_number})")
        except Exception as e:
            print(f"   ✗ Error finding cases: {e}")
            cases = []
        
        print("\n3. Testing recommendation generation:")
        if cases:
            test_case = cases[0]
            print(f"   Testing with case {test_case.id}: {test_case.title}")
            
            try:
                # Test the recommendation engine
                recommendations = recommendation_engine.generate_recommendations(test_case.id)
                
                print("   ✓ Successfully generated recommendations!")
                print(f"   - Case: {recommendations.case_title}")
                print(f"   - Risk Assessment: {recommendations.overall_risk_assessment}")
                print(f"   - Key Themes: {', '.join(recommendations.key_ethical_themes)}")
                print(f"   - Number of Recommendations: {len(recommendations.recommendations)}")
                print(f"   - Average Confidence: {recommendations.confidence_overview.get('avg_recommendation_confidence', 0):.1%}")
                
                # Show first recommendation details
                if recommendations.recommendations:
                    first_rec = recommendations.recommendations[0]
                    print(f"\n   First Recommendation:")
                    print(f"   - Title: {first_rec.title}")
                    print(f"   - Type: {first_rec.recommendation_type}")
                    print(f"   - Priority: {first_rec.priority}")
                    print(f"   - Confidence: {first_rec.confidence:.1%}")
                    print(f"   - Summary: {first_rec.summary}")
                
            except Exception as e:
                print(f"   ✗ Error generating recommendations: {e}")
                print(f"      This might be normal if no associations exist yet")
        else:
            print("   ⚠ No cases found to test with")
            print("   💡 Try importing some NSPE cases first")
        
        print("\n4. Testing recommendation engine capabilities:")
        try:
            # Test engine components
            engine = RecommendationEngine()
            print("   ✓ Can create new engine instance")
            
            # Test confidence thresholds
            print(f"   ✓ Confidence thresholds configured: {list(engine.confidence_thresholds.keys())}")
            
            # Test risk patterns
            print(f"   ✓ Risk patterns configured: {len(engine.risk_patterns)} patterns")
            
        except Exception as e:
            print(f"   ✗ Error testing engine capabilities: {e}")
    
    print("\n" + "=" * 60)
    print("Recommendation Engine Test Complete")
    print("=" * 60)
    
    print("\n🎯 Next Steps:")
    print("1. Start the app: python run.py --port 3333")
    print("2. Visit: http://localhost:3333/dashboard")
    print("3. Click 'Test Recommendations' button")
    print("4. Generate recommendations for real cases!")


if __name__ == "__main__":
    test_recommendation_engine()