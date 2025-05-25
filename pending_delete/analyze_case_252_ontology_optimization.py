#!/usr/bin/env python3
"""
Analyze Case 252 ontology integration for optimization.
This script examines the current prediction and ontology usage to identify improvement opportunities.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up environment
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
os.environ.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', 'false')
os.environ.setdefault('ENVIRONMENT', 'development')

import logging
import json
import re
from datetime import datetime
from app import create_app, db
from app.models.document import Document
from app.models.document_section import DocumentSection
from app.models.experiment import Prediction
from app.services.experiment.prediction_service import PredictionService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_current_prediction():
    """Analyze the current Case 252 prediction for ontology usage."""
    app = create_app('config')
    
    with app.app_context():
        try:
            # Get the most recent prediction for Case 252
            prediction = Prediction.query.filter_by(
                document_id=252,
                target='conclusion'
            ).order_by(Prediction.created_at.desc()).first()
            
            if not prediction:
                logger.error("No prediction found for Case 252")
                return None
            
            logger.info(f"Found prediction created at: {prediction.created_at}")
            logger.info(f"Condition: {prediction.condition}")
            logger.info(f"Prediction length: {len(prediction.prediction_text)} characters")
            
            # Analyze ontology entities in metadata
            meta_info = prediction.meta_info or {}
            ontology_entities = meta_info.get('ontology_entities', {})
            
            logger.info("\n" + "="*60)
            logger.info("ONTOLOGY ENTITIES ANALYSIS")
            logger.info("="*60)
            
            if ontology_entities:
                logger.info(f"Total ontology entities retrieved: {len(ontology_entities)}")
                
                for entity_type, entities in ontology_entities.items():
                    logger.info(f"\n{entity_type.upper()}:")
                    for entity in entities:
                        logger.info(f"  - {entity}")
                
                # Analyze mention ratio in prediction text
                prediction_text = prediction.prediction_text.lower()
                mentioned_entities = []
                total_entities = 0
                
                for entity_type, entities in ontology_entities.items():
                    for entity in entities:
                        total_entities += 1
                        entity_lower = entity.lower()
                        # Check for various forms of mention
                        if (entity_lower in prediction_text or 
                            any(word in prediction_text for word in entity_lower.split() if len(word) > 3)):
                            mentioned_entities.append(entity)
                
                mention_ratio = len(mentioned_entities) / total_entities if total_entities > 0 else 0
                
                logger.info(f"\n📊 MENTION ANALYSIS:")
                logger.info(f"Total entities available: {total_entities}")
                logger.info(f"Entities mentioned: {len(mentioned_entities)}")
                logger.info(f"Mention ratio: {mention_ratio:.1%}")
                
                if mentioned_entities:
                    logger.info("\nMentioned entities:")
                    for entity in mentioned_entities:
                        logger.info(f"  ✓ {entity}")
                
                # Show prediction text sample
                logger.info(f"\n📝 PREDICTION TEXT SAMPLE (first 500 chars):")
                logger.info(prediction.prediction_text[:500] + "...")
                
            else:
                logger.warning("No ontology entities found in prediction metadata")
            
            return {
                'prediction': prediction,
                'ontology_entities': ontology_entities,
                'mention_ratio': mention_ratio if 'mention_ratio' in locals() else 0,
                'mentioned_entities': mentioned_entities if 'mentioned_entities' in locals() else []
            }
            
        except Exception as e:
            logger.exception(f"Error analyzing prediction: {str(e)}")
            return None

def analyze_available_ontology_entities():
    """Analyze what ontology entities are available for Case 252."""
    app = create_app('config')
    
    with app.app_context():
        try:
            prediction_service = PredictionService()
            
            # Get section associations for Case 252
            from ttl_triple_association.section_triple_association_service import SectionTripleAssociationService
            association_service = SectionTripleAssociationService()
            
            # Get document sections
            sections = DocumentSection.query.filter_by(document_id=252).all()
            logger.info(f"\nFound {len(sections)} sections for Case 252")
            
            all_entities = {}
            
            for section in sections:
                logger.info(f"\nAnalyzing section: {section.section_type}")
                
                # Get associations for this section
                associations = association_service.storage.get_section_associations(section.id)
                
                if associations:
                    logger.info(f"  Found {len(associations)} associations")
                    
                    for assoc in associations:
                        entity_type = assoc.get('predicate', 'unknown')
                        entity_value = assoc.get('object', 'unknown')
                        
                        if entity_type not in all_entities:
                            all_entities[entity_type] = set()
                        all_entities[entity_type].add(entity_value)
                else:
                    logger.info("  No associations found")
            
            # Convert sets to lists for JSON serialization
            entities_summary = {k: list(v) for k, v in all_entities.items()}
            
            logger.info("\n" + "="*60)
            logger.info("AVAILABLE ONTOLOGY ENTITIES SUMMARY")
            logger.info("="*60)
            
            total_available = sum(len(entities) for entities in entities_summary.values())
            logger.info(f"Total available entities: {total_available}")
            
            for entity_type, entities in entities_summary.items():
                logger.info(f"\n{entity_type}: {len(entities)} entities")
                for entity in entities[:5]:  # Show first 5
                    logger.info(f"  - {entity}")
                if len(entities) > 5:
                    logger.info(f"  ... and {len(entities) - 5} more")
            
            return entities_summary
            
        except Exception as e:
            logger.exception(f"Error analyzing available entities: {str(e)}")
            return None

def main():
    """Run the ontology optimization analysis."""
    logger.info("=" * 80)
    logger.info("CASE 252 ONTOLOGY OPTIMIZATION ANALYSIS")
    logger.info("=" * 80)
    
    # Analyze current prediction
    logger.info("\n1. ANALYZING CURRENT PREDICTION")
    current_analysis = analyze_current_prediction()
    
    # Analyze available entities
    logger.info("\n2. ANALYZING AVAILABLE ONTOLOGY ENTITIES")
    available_entities = analyze_available_ontology_entities()
    
    # Generate optimization recommendations
    if current_analysis and available_entities:
        logger.info("\n" + "="*60)
        logger.info("OPTIMIZATION RECOMMENDATIONS")
        logger.info("="*60)
        
        current_ratio = current_analysis['mention_ratio']
        target_ratio = 0.20  # 20%
        
        logger.info(f"Current mention ratio: {current_ratio:.1%}")
        logger.info(f"Target mention ratio: {target_ratio:.1%}")
        
        if current_ratio < target_ratio:
            improvement_needed = target_ratio - current_ratio
            logger.info(f"Improvement needed: +{improvement_needed:.1%}")
            
            # Suggest specific improvements
            logger.info("\n🎯 RECOMMENDED OPTIMIZATIONS:")
            logger.info("1. Enhanced prompt engineering to explicitly reference ontology entities")
            logger.info("2. Better integration of NSPE Code sections into reasoning")
            logger.info("3. More direct connections between case facts and ethical principles")
            logger.info("4. Structured reasoning that maps case elements to ontological concepts")
        else:
            logger.info("✅ Current mention ratio meets or exceeds target!")
    
    # Save analysis results
    results = {
        'timestamp': datetime.now().isoformat(),
        'case_id': 252,
        'current_analysis': current_analysis,
        'available_entities': available_entities,
        'recommendations': {
            'current_ratio': current_analysis['mention_ratio'] if current_analysis else 0,
            'target_ratio': 0.20,
            'needs_optimization': (current_analysis['mention_ratio'] if current_analysis else 0) < 0.20
        }
    }
    
    results_file = f'case_252_ontology_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    try:
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"\n📊 Analysis results saved to: {results_file}")
    except Exception as e:
        logger.error(f"Error saving results: {e}")
    
    logger.info("\n✅ ANALYSIS COMPLETE")
    return results

if __name__ == "__main__":
    main()
