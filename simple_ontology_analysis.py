#!/usr/bin/env python3
"""
Simple analysis of Case 252 ontology usage.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up environment
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
os.environ.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', 'false')
os.environ.setdefault('ENVIRONMENT', 'development')

import json
from app import create_app, db
from app.models.experiment import Prediction

def analyze_prediction():
    """Analyze the latest Case 252 prediction."""
    app = create_app('config')
    
    with app.app_context():
        try:
            # Get the most recent prediction for Case 252
            prediction = Prediction.query.filter_by(
                document_id=252,
                target='conclusion'
            ).order_by(Prediction.created_at.desc()).first()
            
            if not prediction:
                print("❌ No prediction found for Case 252")
                return
            
            print("✅ Found Case 252 prediction:")
            print(f"Created: {prediction.created_at}")
            print(f"Condition: {prediction.condition}")
            print(f"Text length: {len(prediction.prediction_text)} characters")
            
            # Check ontology entities in metadata
            meta_info = prediction.meta_info or {}
            ontology_entities = meta_info.get('ontology_entities', {})
            
            print(f"\n📊 ONTOLOGY ENTITIES:")
            if ontology_entities:
                total_entities = sum(len(entities) for entities in ontology_entities.values())
                print(f"Total entities available: {total_entities}")
                
                for entity_type, entities in ontology_entities.items():
                    print(f"\n{entity_type} ({len(entities)} entities):")
                    for entity in entities[:3]:  # Show first 3
                        print(f"  - {entity}")
                    if len(entities) > 3:
                        print(f"  ... and {len(entities) - 3} more")
                
                # Simple mention analysis
                prediction_text = prediction.prediction_text.lower()
                mentioned_count = 0
                
                for entity_type, entities in ontology_entities.items():
                    for entity in entities:
                        entity_words = entity.lower().split()
                        if any(word in prediction_text for word in entity_words if len(word) > 3):
                            mentioned_count += 1
                
                mention_ratio = mentioned_count / total_entities if total_entities > 0 else 0
                print(f"\n📈 MENTION RATIO: {mention_ratio:.1%} ({mentioned_count}/{total_entities})")
                
                # Target is 20%
                if mention_ratio < 0.20:
                    print(f"🎯 NEEDS OPTIMIZATION: Target is 20%, current is {mention_ratio:.1%}")
                    improvement = 0.20 - mention_ratio
                    print(f"   Need to improve by {improvement:.1%}")
                else:
                    print(f"✅ MEETS TARGET: Above 20% threshold")
            else:
                print("❌ No ontology entities found in prediction metadata")
            
            # Show prediction sample
            print(f"\n📝 PREDICTION SAMPLE (first 300 chars):")
            print(prediction.prediction_text[:300] + "...")
            
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("CASE 252 ONTOLOGY ANALYSIS")
    print("=" * 60)
    analyze_prediction()
