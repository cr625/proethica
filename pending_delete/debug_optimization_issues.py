#!/usr/bin/env python3
"""
Debug the optimization issues - investigate why prediction length is 0.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up environment
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
os.environ.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', 'false')
os.environ.setdefault('ENVIRONMENT', 'development')

import logging
from typing import Dict, List, Any
from app import create_app, db
from app.models.document import Document
from app.models.document_section import DocumentSection
from app.services.experiment.prediction_service import PredictionService

logger = logging.getLogger(__name__)

def debug_prediction_extraction():
    """Debug the prediction extraction process."""
    app = create_app('config')
    
    with app.app_context():
        try:
            print("🔍 DEBUGGING PREDICTION EXTRACTION")
            print("="*60)
            
            # Create standard service first
            service = PredictionService()
            
            # Get document and sections for Case 252
            document = Document.query.get(252)
            sections = service.get_document_sections(252, leave_out_conclusion=True)
            ontology_entities = service.get_section_ontology_entities(252, sections)
            similar_cases = service._find_similar_cases(252, limit=3)
            
            print(f"✅ Document: {document.title}")
            print(f"✅ Sections: {list(sections.keys())}")
            print(f"✅ Ontology entities: {len(ontology_entities)} section types")
            print(f"✅ Similar cases: {len(similar_cases)}")
            
            # Test the standard prompt construction
            standard_prompt = service._construct_conclusion_prediction_prompt(
                document, sections, ontology_entities, similar_cases
            )
            
            print(f"\n📝 STANDARD PROMPT LENGTH: {len(standard_prompt)} characters")
            print(f"📝 STANDARD PROMPT SAMPLE (first 500 chars):")
            print(standard_prompt[:500] + "...")
            
            # Generate prediction with standard service
            print(f"\n🧠 TESTING STANDARD LLM RESPONSE...")
            response = service.llm_service.llm.invoke(standard_prompt)
            
            # Debug response type and content
            print(f"Response type: {type(response)}")
            if hasattr(response, 'content'):
                response_content = response.content
                print(f"Response content length: {len(response_content)}")
                print(f"Response content sample: {response_content[:300]}...")
            else:
                response_content = str(response)
                print(f"Response string length: {len(response_content)}")
                print(f"Response string sample: {response_content[:300]}...")
            
            # Test extraction method
            print(f"\n🔍 TESTING EXTRACTION METHOD...")
            extracted = service._extract_conclusion(response)
            print(f"Extracted conclusion length: {len(extracted)}")
            print(f"Extracted conclusion sample: {extracted[:300]}...")
            
            if len(extracted) == 0:
                print("❌ EXTRACTION FAILED - Response content but no extraction")
                print("Full response for debugging:")
                print(response_content)
            else:
                print("✅ EXTRACTION SUCCESSFUL")
            
        except Exception as e:
            print(f"❌ Error in debugging: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug_prediction_extraction()
