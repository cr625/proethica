#!/usr/bin/env python3
"""
Debug the extraction issue specifically.
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
from datetime import datetime
from app import create_app, db
from app.models.document import Document
from app.models.document_section import DocumentSection
from optimize_ontology_prediction_service_fixed import OptimizedPredictionService

logger = logging.getLogger(__name__)

def debug_extraction():
    """Debug the extraction process step by step."""
    app = create_app('config')
    
    with app.app_context():
        try:
            print("🔍 DEBUGGING EXTRACTION PROCESS")
            print("="*60)
            
            # Create optimized service
            service = OptimizedPredictionService()
            
            # Get basic components
            document = Document.query.get(252)
            sections = service.get_document_sections(252, leave_out_conclusion=True)
            ontology_entities = service.get_section_ontology_entities(252, sections)
            similar_cases = service._find_similar_cases(252, limit=3)
            
            print(f"✅ Document: {document.title}")
            print(f"✅ Sections: {list(sections.keys())}")
            print(f"✅ Ontology entities count: {sum(len(entities) for entities in ontology_entities.values())}")
            
            # Create the optimized prompt
            prompt = service._construct_conclusion_prediction_prompt(
                document, sections, ontology_entities, similar_cases
            )
            
            print(f"✅ Prompt created: {len(prompt)} characters")
            
            # Generate response
            print(f"\n🧠 Generating LLM response...")
            response = service.llm_service.llm.invoke(prompt)
            
            # Debug response details
            print(f"Response type: {type(response)}")
            if hasattr(response, 'content'):
                response_content = response.content
                print(f"Response content type: {type(response_content)}")
                print(f"Response content length: {len(response_content)}")
                print(f"Response content preview: {response_content[:200]}...")
            else:
                response_content = str(response)
                print(f"Response string length: {len(response_content)}")
                print(f"Response string preview: {response_content[:200]}...")
            
            # Test extraction
            print(f"\n🔍 Testing extraction method...")
            extracted = service._extract_conclusion(response)
            print(f"Extracted type: {type(extracted)}")
            print(f"Extracted length: {len(extracted)}")
            
            if len(extracted) > 0:
                print(f"✅ EXTRACTION SUCCESS!")
                print(f"Extracted preview: {extracted[:300]}...")
            else:
                print(f"❌ EXTRACTION FAILED - Empty result")
                print(f"Full response content for analysis:")
                print(response_content)
            
        except Exception as e:
            print(f"❌ Error in debugging: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug_extraction()
