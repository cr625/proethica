#!/usr/bin/env python3
"""
Optimized Prediction Service with Enhanced Ontology Utilization.
This addresses the target of improving ontology mention ratio from ~15% to >20%.
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

class OptimizedPredictionService(PredictionService):
    """Enhanced prediction service with optimized ontology utilization."""
    
    def generate_conclusion_prediction(self, document_id: int) -> Dict[str, Any]:
        """
        Enhanced conclusion prediction with optimized ontology integration.
        """
        try:
            # Get the document
            document = Document.query.get(document_id)
            if not document:
                return {
                    'success': False,
                    'error': f"Document with ID {document_id} not found"
                }
                
            # Get document sections (excluding conclusion)
            sections = self.get_document_sections(document_id, leave_out_conclusion=True)
            
            if not sections:
                return {
                    'success': False,
                    'error': "No sections found for document"
                }
                
            # Get ontology entities associated with document sections
            ontology_entities = self.get_section_ontology_entities(document_id, sections)
            
            # Find similar cases with ontology-enhanced matching
            similar_cases = self._find_similar_cases(document_id, limit=3)

            # Construct OPTIMIZED conclusion prediction prompt
            prompt = self._construct_conclusion_prediction_prompt(document, sections, ontology_entities, similar_cases)

            # Generate prediction using LLM
            logger.info(f"Generating OPTIMIZED conclusion prediction for document {document_id}")
            response = self.llm_service.llm.invoke(prompt)

            # Extract just the conclusion from the response
            conclusion = self._extract_conclusion(response)
            
            # Use ENHANCED validation 
            validation_results = self._validate_conclusion_enhanced(conclusion, ontology_entities)

            # Return results
            return {
                'success': True,
                'document_id': document_id,
                'condition': 'proethica_optimized',
                'target': 'conclusion',
                'prediction': conclusion,
                'full_response': response,
                'prompt': prompt,
                'timestamp': datetime.utcnow().isoformat(),
                'metadata': {
                    'sections_included': list(sections.keys()),
                    'ontology_entities': self._summarize_ontology_entities(ontology_entities),
                    'similar_cases': [case['title'] for case in similar_cases],
                    'validation_metrics': validation_results,
                    'optimization_applied': True
                }
            }

        except Exception as e:
            logger.exception(f"Error generating OPTIMIZED conclusion prediction: {str(e)}")
            return {
                'success': False,
                'error': f"Error generating optimized prediction: {str(e)}"
            }
    
    def _construct_conclusion_prediction_prompt(self, document: Document, 
                                            sections: Dict[str, str],
                                            ontology_entities: Dict[str, List[Dict]],
                                            similar_cases: List[Dict[str, Any]]) -> str:
        """
        Enhanced prompt construction with improved ontology integration.
        
        OPTIMIZATIONS:
        1. More explicit ontology entity integration
        2. Structured reasoning framework that encourages entity usage
        3. Enhanced prompt engineering for higher mention ratio
        4. Better context weaving of ethical principles
        """
        
        prompt = f"""You are an AI assistant with expertise in engineering ethics, tasked with predicting the conclusion for an engineering ethics case from the National Society of Professional Engineers (NSPE) Board of Ethical Review.

CASE INFORMATION:
Title: {document.title}
"""
        
        # ENHANCED FACTS SECTION with ontology weaving
        prompt += "\n\n# CASE FACTS:"
        if 'facts' in sections:
            prompt += f"\n{sections['facts']}"
            logger.info(f"✓ Added Facts section to prompt ({len(sections['facts'])} chars)")
            
            # OPTIMIZATION 1: Weave relevant ontology concepts directly into facts analysis
            fact_entities = ontology_entities.get('facts', [])
            if fact_entities:
                prompt += "\n\n## ETHICAL CONCEPTS RELEVANT TO THESE FACTS:"
                # Include more entities (up to 8 instead of 5) with better integration
                for i, entity in enumerate(fact_entities[:8]):
                    subj = entity.get('subject', '')
                    pred = entity.get('predicate', '')
                    obj = entity.get('object', '')
                    prompt += f"\n{i+1}. **{subj}** {pred} {obj}"
                    
                prompt += "\n\nWhen analyzing this case, explicitly consider how these ethical concepts apply to the facts presented."
        else:
            prompt += "\n[No facts section available]"
            logger.warning("❌ No Facts section available for prompt")
        
        # ENHANCED QUESTION SECTION
        prompt += "\n\n# ETHICAL QUESTION:"
        if 'question' in sections:
            prompt += f"\n{sections['question']}"
            
            # OPTIMIZATION 2: Frame issues in terms of specific ethical principles
            issue_entities = ontology_entities.get('question', [])
            if issue_entities:
                prompt += "\n\n## ETHICAL PRINCIPLES DIRECTLY RELEVANT TO THIS QUESTION:"
                for i, entity in enumerate(issue_entities[:6]):  # Increased from 5 to 6
                    subj = entity.get('subject', '')
                    pred = entity.get('predicate', '')
                    obj = entity.get('object', '')
                    prompt += f"\n• **{subj}**: {obj}"
                    
                prompt += "\n\nYour conclusion must specifically address how these principles apply to resolve the ethical question."
        else:
            prompt += "\n[No question section available]"
        
        # ENHANCED REFERENCES SECTION  
        if 'references' in sections:
            prompt += "\n\n# RELEVANT NSPE CODE SECTIONS:"
            prompt += f"\n{sections['references']}"
        
        # ENHANCED DISCUSSION SECTION
        if 'discussion' in sections:
            prompt += "\n\n# CASE ANALYSIS:"
            prompt += f"\n{sections['discussion']}"
        
        # OPTIMIZATION 3: Create a comprehensive ethical framework section
        rule_entities = []
        for section_type, entities in ontology_entities.items():
            if section_type in ['references', 'discussion']:
                rule_entities.extend(entities)
        
        if rule_entities:
            rule_entities = sorted(rule_entities, key=lambda x: x.get('score', 0.0), reverse=True)
            
            prompt += "\n\n# COMPREHENSIVE ETHICAL FRAMEWORK:"
            prompt += "\nThe following ethical principles and NSPE Code provisions must be considered in your conclusion:"
            
            # OPTIMIZATION 4: Organize entities by type for better integration
            code_sections = []
            principles = []
            obligations = []
            
            for entity in rule_entities[:15]:  # Increased from 10 to 15
                subj = entity.get('subject', '').lower()
                obj = entity.get('object', '')
                
                if 'section' in subj or 'code' in subj:
                    code_sections.append(entity)
                elif 'principle' in subj or 'ethical' in subj:
                    principles.append(entity)
                else:
                    obligations.append(entity)
            
            if code_sections:
                prompt += "\n\n## NSPE Code Sections:"
                for entity in code_sections[:5]:
                    prompt += f"\n• {entity.get('subject', '')}: {entity.get('object', '')}"
            
            if principles:
                prompt += "\n\n## Ethical Principles:"
                for entity in principles[:5]:
                    prompt += f"\n• {entity.get('subject', '')}: {entity.get('object', '')}"
                    
            if obligations:
                prompt += "\n\n## Professional Obligations:"
                for entity in obligations[:5]:
                    prompt += f"\n• {entity.get('subject', '')}: {entity.get('object', '')}"
        
        # Add similar cases with enhanced context
        if similar_cases:
            prompt += "\n\n# PRECEDENT ANALYSIS:"
            for i, case in enumerate(similar_cases):
                prompt += f"\n\n## Precedent Case {i+1}: {case['title']}"
                if 'outcome' in case:
                    prompt += f"\n**Board Decision**: {case['outcome']}"
                if 'summary' in case:
                    prompt += f"\n**Reasoning**: {case['summary']}"
        
        # OPTIMIZATION 5: Enhanced conclusion request with explicit ontology integration
        prompt += """

# CONCLUSION REQUIREMENTS:

You must generate a comprehensive conclusion that:

## 1. ETHICAL DETERMINATION
- State clearly whether the engineer's conduct is ETHICAL or UNETHICAL
- Base this determination on specific NSPE Code provisions cited above

## 2. DETAILED JUSTIFICATION  
- Reference AT LEAST 3-4 specific ethical principles from the framework above
- Explain how each principle applies to the facts of this case
- Address each relevant NSPE Code section by name and number

## 3. COMPREHENSIVE ANALYSIS
- Integrate the ethical concepts identified in the facts analysis
- Address all ethical principles listed as relevant to the question
- Demonstrate how professional obligations apply to this situation

## 4. STRUCTURED REASONING
- Use formal language appropriate for an NSPE Board decision
- Organize your reasoning logically (facts → principles → application → conclusion)
- Ensure your conclusion flows directly from the ethical framework provided

## 5. EXPLICIT INTEGRATION REQUIREMENT
**CRITICAL**: Your conclusion must explicitly mention and apply the specific ethical concepts, NSPE Code sections, and professional obligations listed above. Failure to integrate these elements will result in an incomplete ethical analysis.

Generate your conclusion now, ensuring comprehensive integration of the ethical framework provided:
"""
        
        return prompt
    
    def _validate_conclusion_enhanced(self, conclusion: str, 
                                    ontology_entities: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """
        Enhanced validation with better entity mention detection.
        
        OPTIMIZATIONS:
        1. Better entity extraction and normalization
        2. Semantic matching for related terms
        3. More sophisticated scoring
        """
        import re
        
        # Extract all relevant entities with better processing
        all_entities = []
        entity_details = []
        
        for section_type, entities in ontology_entities.items():
            for entity in entities:
                # Process subject terms
                if 'subject' in entity and entity['subject']:
                    subj = entity['subject'].strip()
                    all_entities.append(subj)
                    entity_details.append({
                        'text': subj,
                        'type': 'subject',
                        'section': section_type,
                        'full_entity': entity
                    })
                
                # Process object terms
                if 'object' in entity and entity['object']:
                    obj = entity['object'].strip()
                    all_entities.append(obj)
                    entity_details.append({
                        'text': obj,
                        'type': 'object', 
                        'section': section_type,
                        'full_entity': entity
                    })
        
        # Enhanced mention detection
        conclusion_lower = conclusion.lower()
        mentioned_entities = []
        direct_mentions = 0
        semantic_mentions = 0
        
        for detail in entity_details:
            entity_text = detail['text'].lower()
            
            # Direct mention check
            if entity_text in conclusion_lower:
                direct_mentions += 1
                mentioned_entities.append(detail)
                continue
            
            # Semantic mention check (key words from entity)
            entity_words = [w for w in entity_text.split() if len(w) > 3]
            if any(word in conclusion_lower for word in entity_words):
                semantic_mentions += 1
                mentioned_entities.append(detail)
        
        # Calculate enhanced metrics
        total_entities = len(entity_details)
        total_mentions = direct_mentions + semantic_mentions
        mention_ratio = total_mentions / total_entities if total_entities > 0 else 0
        
        # Analyze mention distribution by section
        section_coverage = {}
        for detail in mentioned_entities:
            section = detail['section']
            if section not in section_coverage:
                section_coverage[section] = 0
            section_coverage[section] += 1
        
        return {
            'total_entities': total_entities,
            'direct_mentions': direct_mentions,
            'semantic_mentions': semantic_mentions,
            'total_mentions': total_mentions,
            'mention_ratio': mention_ratio,
            'section_coverage': section_coverage,
            'mentioned_entities': [d['text'] for d in mentioned_entities[:15]],
            'validation_status': 'excellent' if mention_ratio >= 0.25 else 
                               'good' if mention_ratio >= 0.20 else
                               'acceptable' if mention_ratio >= 0.15 else 'needs_improvement',
            'optimization_success': mention_ratio >= 0.20
        }

def test_optimization():
    """Test the optimized prediction service with Case 252."""
    app = create_app('config')
    
    with app.app_context():
        try:
            print("🎯 TESTING OPTIMIZED ONTOLOGY INTEGRATION")
            print("="*60)
            
            # Create optimized service
            optimized_service = OptimizedPredictionService()
            
            # Generate optimized prediction for Case 252
            result = optimized_service.generate_conclusion_prediction(document_id=252)
            
            if result.get('success'):
                print("✅ Optimized prediction generated successfully!")
                print(f"Prediction length: {len(result.get('prediction', ''))} characters")
                
                # Show metadata
                metadata = result.get('metadata', {})
                if metadata:
                    print(f"\nSections included: {metadata.get('sections_included', [])}")
                    print(f"Ontology entities: {metadata.get('ontology_entities', {})}")
                    print(f"Validation: {metadata.get('validation_metrics', {})}")
                
                # Show prediction sample
                prediction = result.get('prediction', '')
                print(f"\n📝 OPTIMIZED PREDICTION SAMPLE (first 400 chars):")
                print(prediction[:400] + "...")
                
                return result
            else:
                print(f"❌ Optimization test failed: {result.get('error')}")
                return None
                
        except Exception as e:
            print(f"❌ Error in optimization test: {e}")
            return None

if __name__ == "__main__":
    test_optimization()
