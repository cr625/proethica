#!/usr/bin/env python3
"""
Update pending concept type mappings with improved classifications
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
if os.path.exists('.env'):
    load_dotenv()

# Set environment for development
os.environ.setdefault('ENVIRONMENT', 'development')

# Set database URL if not already set
if not os.environ.get('SQLALCHEMY_DATABASE_URI'):
    db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    os.environ['SQLALCHEMY_DATABASE_URI'] = db_url

from app import create_app, db
from app.models.entity_triple import EntityTriple
from app.services.guideline_concept_type_mapper import GuidelineConceptTypeMapper
from sqlalchemy import text

def main():
    """Update pending concept mappings with improved type classifications."""
    app = create_app('config')
    
    with app.app_context():
        print("Updating pending concept mappings with improved classifications...")
        
        # Initialize the improved type mapper
        mapper = GuidelineConceptTypeMapper()
        
        # Manual mappings based on our analysis
        manual_updates = {
            # ID: (new_type, confidence, justification, concept_name)
            1759: ("principle", 0.85, "Honesty and integrity are fundamental ethical principles", "honesty and integrity"),
            1771: ("state", 0.80, "Professional reputation is a professional state/condition", "professional reputation"), 
            1774: ("principle", 0.85, "Truthful communication is an ethical principle", "truthful communication"),
            1777: ("action", 0.90, "Professional development is an action/activity", "professional development"),
            1783: ("principle", 0.85, "Sustainability is an environmental principle", "sustainability"),
            1789: ("principle", 0.90, "Intellectual property rights are legal principles", "intellectual property rights"),
            1792: ("principle", 0.85, "Fair treatment is an ethical principle", "fair treatment")
        }
        
        updated_count = 0
        
        for concept_id, (new_type, confidence, justification, concept_name) in manual_updates.items():
            try:
                # Get the concept
                concept = EntityTriple.query.get(concept_id)
                if not concept:
                    print(f"❌ Concept {concept_id} not found")
                    continue
                
                # Update the concept
                concept.object_literal = new_type
                concept.type_mapping_confidence = confidence
                concept.mapping_justification = justification
                concept.needs_type_review = False  # Mark as reviewed
                
                print(f"✅ Updated {concept_name}: {concept.original_llm_type} → {new_type} ({confidence*100:.0f}%)")
                updated_count += 1
                
            except Exception as e:
                print(f"❌ Error updating concept {concept_id}: {e}")
                continue
        
        # Commit all changes
        try:
            db.session.commit()
            print(f"\n🎉 Successfully updated {updated_count} concept mappings!")
            
            # Show remaining concepts needing review
            remaining = db.session.execute(text("""
                SELECT COUNT(*) FROM entity_triples WHERE needs_type_review = true
            """)).scalar()
            
            print(f"📊 Remaining concepts needing review: {remaining}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error committing changes: {e}")
            raise

if __name__ == '__main__':
    main()