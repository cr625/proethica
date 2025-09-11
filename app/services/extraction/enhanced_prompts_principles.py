"""
Enhanced Principles Extraction with Chapter 2 Literature Grounding
Based on Section 2.2.2: Principles (P) - Abstract Ethical Foundations

This module implements principle extraction grounded in the academic literature,
particularly addressing the challenge of transforming abstract ethical guidance
into concrete, operationalizable principles through extensional definition.
"""

from typing import List, Dict, Any, Optional
import logging
import json
from datetime import datetime

from .base import ConceptCandidate

# Optional provenance tracking - create stubs if not available
try:
    from .provenance_service import ProvenanceService, ExtractionActivity, EntityReference
except ImportError:
    # Create stub classes for when provenance service is not available
    class ProvenanceService:
        def start_activity(self, activity): return activity
        def record_entity(self, activity, entity): pass
        def complete_activity(self, activity, metadata): pass
        def record_error(self, activity, error): pass
        def add_metadata(self, activity, metadata): pass
    
    class ExtractionActivity:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
    
    class EntityReference:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

logger = logging.getLogger(__name__)


class EnhancedPrinciplesExtractor:
    """
    Enhanced extractor for ethical principles based on Chapter 2 literature.
    
    Key theoretical foundations:
    - McLaren (2003): Principles require extensional definition through precedents
    - Taddeo et al. (2024): Constitutional-like principles requiring interpretation
    - Anderson & Anderson (2018): Principles learned from expert examples
    - Hallamaa & Kalliokoski (2022): Principles mediate moral ideals into reality
    - Benzmüller et al. (2020): Distinction between abstract principles and concrete obligations
    """
    
    def __init__(self, llm_client=None, provenance_service: Optional[ProvenanceService] = None):
        self.llm_client = llm_client
        self.provenance_service = provenance_service or ProvenanceService()
        
    def extract(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[ConceptCandidate]:
        """
        Extract principles with enhanced prompt based on Chapter 2 literature.
        
        Args:
            text: The discussion/analysis text to extract principles from
            context: Optional context including case metadata
            
        Returns:
            List of ConceptCandidate objects representing extracted principles
        """
        if not text:
            return []
            
        # Start provenance tracking
        activity = self._start_provenance_tracking(text, context)
        
        try:
            # Generate enhanced prompt
            prompt = self._generate_enhanced_prompt(text)
            
            # Get LLM extraction if available
            if self.llm_client:
                candidates = self._extract_with_llm(text, prompt, activity)
            else:
                candidates = self._fallback_extraction(text)
                
            # Enhance with ontology grounding
            candidates = self._enhance_with_ontology(candidates)
            
            # Complete provenance tracking
            self._complete_provenance_tracking(activity, candidates)
            
            return candidates
            
        except Exception as e:
            logger.error(f"Error in enhanced principles extraction: {str(e)}")
            if activity:
                self.provenance_service.record_error(activity, str(e))
            return []
    
    def _generate_enhanced_prompt(self, text: str) -> str:
        """
        Generate an enhanced prompt based on Chapter 2 literature insights.
        
        Key aspects from literature:
        - Inherent vagueness requiring contextual interpretation (Prem 2023, Segun 2021)
        - Context-sensitivity and role in mediating moral ideals (Hallamaa & Kalliokoski 2022)
        - Three-step operationalization (Taddeo et al. 2024)
        - Learned from expert examples rather than explicit programming (Anderson & Anderson 2018)
        - Distinction from concrete obligations (Dennis et al. 2016, Benzmüller et al. 2020)
        """
        
        prompt = f"""You are an expert in professional ethics, particularly engineering ethics, with deep knowledge of 
how abstract ethical principles guide professional practice. Your analysis is grounded in scholarly literature
on computational ethics and professional codes like the NSPE Code of Ethics.

THEORETICAL FRAMEWORK (Based on Chapter 2 Literature):

1. PRINCIPLE CHARACTERISTICS (Hallamaa & Kalliokoski 2022, Taddeo et al. 2024):
   - Abstract ethical foundations that require contextual interpretation
   - Constitutional-like character: foundational rather than offering detailed guidelines
   - Open-textured and purpose-oriented nature
   - Function as mechanisms mediating moral ideals into professional reality
   - Too abstract for direct translation into concrete designs (Prem 2023)

2. DISTINCTION FROM OBLIGATIONS (Dennis et al. 2016, Benzmüller et al. 2020):
   - Principles provide general guidance; obligations specify exact requirements
   - Principles maintain consistent meaning across contexts
   - Obligations specify what, when, by whom, under what conditions
   - Example: "Do no harm" (principle) vs "Obtain informed consent" (obligation)

3. OPERATIONALIZATION APPROACH (Taddeo et al. 2024):
   - Step 1: Identify appropriate levels of abstraction
   - Step 2: Interpret principles to extract specific requirements
   - Step 3: Define criteria for context-specific balancing

4. EXTENSIONAL DEFINITION (McLaren 2003):
   - Principles gain meaning through accumulated precedents
   - Cannot be understood through logical definition alone
   - Require examination of application across actual cases
   - Example: "Hold paramount public safety" - meaning emerges from hundreds of cases

5. LEARNING FROM EXAMPLES (Anderson & Anderson 2018):
   - Principles can be discovered as generalizations from expert-agreed cases
   - Maintain traceability to originating cases
   - Provide justification through analogy rather than deduction

EXTRACTION TASK:
Analyze the following professional ethics discussion/analysis text to identify PRINCIPLES - abstract ethical 
foundations that guide professional conduct. Focus on statements that:

1. Express fundamental values or ethical foundations
2. Provide high-level guidance rather than specific requirements
3. Require interpretation for specific contexts
4. Serve as basis for deriving concrete obligations
5. Reflect constitutional-like professional values

IMPORTANT DISTINCTIONS:
- PRINCIPLES: Abstract values like integrity, public welfare, honesty
- NOT PRINCIPLES: Specific duties like "must report violations" (obligation)
- NOT PRINCIPLES: Limitations like "cannot exceed budget" (constraint)

TEXT TO ANALYZE:
{text[:3000]}

EXTRACTION REQUIREMENTS:
Return a JSON array of principle objects. Each principle should include:

{{
  "label": "Short name for the principle (e.g., 'Public Safety Paramount')",
  "description": "Full description of what this principle means",
  "principle_category": "fundamental|professional|domain_specific",
  "abstraction_level": "high|medium", 
  "requires_interpretation": true/false,
  "potential_conflicts": ["Other principles this might conflict with"],
  "extensional_examples": ["Brief examples showing how this principle is applied"],
  "derived_obligations": ["Examples of concrete obligations derived from this principle"],
  "scholarly_grounding": "Connection to professional codes or ethical theory",
  "confidence": 0.0-1.0
}}

Focus on extracting genuine PRINCIPLES that serve as abstract ethical foundations, not concrete obligations
or constraints. Each principle should represent a fundamental value that requires interpretation and can
generate multiple specific obligations in different contexts.

Return ONLY the JSON array, no additional text."""

        return prompt
    
    def _extract_with_llm(self, text: str, prompt: str, activity: Any) -> List[ConceptCandidate]:
        """
        Extract principles using LLM with enhanced prompt.
        """
        try:
            # Record LLM call in provenance
            if activity:
                self.provenance_service.add_metadata(activity, {
                    'extraction_method': 'enhanced_llm',
                    'prompt_type': 'chapter2_grounded',
                    'model': getattr(self.llm_client, 'model', 'unknown')
                })
            
            # Get LLM response
            response = self.llm_client.generate(prompt)
            
            # Parse JSON response
            principles = json.loads(response)
            
            # Convert to ConceptCandidates
            candidates = []
            for p in principles:
                candidate = ConceptCandidate(
                    label=p.get('label', ''),
                    description=p.get('description', ''),
                    primary_type='principle',
                    category='principle',
                    confidence=float(p.get('confidence', 0.75)),
                    debug={
                        'principle_category': p.get('principle_category'),
                        'abstraction_level': p.get('abstraction_level'),
                        'requires_interpretation': p.get('requires_interpretation'),
                        'potential_conflicts': p.get('potential_conflicts', []),
                        'extensional_examples': p.get('extensional_examples', []),
                        'derived_obligations': p.get('derived_obligations', []),
                        'scholarly_grounding': p.get('scholarly_grounding'),
                        'extraction_method': 'enhanced_chapter2',
                        'extracted_at': datetime.now().isoformat()
                    }
                )
                candidates.append(candidate)
                
            return candidates
            
        except Exception as e:
            logger.error(f"LLM extraction failed: {str(e)}")
            return self._fallback_extraction(text)
    
    def _fallback_extraction(self, text: str) -> List[ConceptCandidate]:
        """
        Fallback heuristic extraction when LLM is unavailable.
        Based on common principle keywords from professional codes.
        """
        import re
        
        # Keywords from NSPE and other professional codes
        principle_patterns = [
            (r"hold\s+paramount\s+(?:the\s+)?(?:public\s+)?(?:safety|health|welfare)", 
             "Public Safety Paramount", "fundamental"),
            (r"professional\s+integrity|honesty\s+and\s+truthfulness", 
             "Professional Integrity", "professional"),
            (r"competent\s+practice|areas?\s+of\s+competence", 
             "Competence", "professional"),
            (r"confidentiality|client\s+confidences", 
             "Confidentiality", "professional"),
            (r"avoid\s+conflicts?\s+of\s+interest|disclose\s+conflicts?", 
             "Avoiding Conflicts of Interest", "professional"),
            (r"professional\s+development|continuing\s+education", 
             "Continuous Learning", "professional"),
            (r"environmental\s+protection|sustainability", 
             "Environmental Stewardship", "domain_specific"),
            (r"fairness|justice|equity", 
             "Fairness and Justice", "fundamental"),
            (r"respect\s+for\s+persons?|human\s+dignity", 
             "Respect for Persons", "fundamental"),
            (r"transparency|accountability", 
             "Transparency and Accountability", "professional")
        ]
        
        candidates = []
        text_lower = text.lower()
        
        for pattern, label, category in principle_patterns:
            if re.search(pattern, text_lower):
                candidate = ConceptCandidate(
                    label=label,
                    description=f"Principle of {label.lower()} identified in text",
                    primary_type='principle',
                    category='principle',
                    confidence=0.65,
                    debug={
                        'principle_category': category,
                        'extraction_method': 'fallback_heuristic',
                        'requires_interpretation': True,
                        'abstraction_level': 'high' if category == 'fundamental' else 'medium'
                    }
                )
                candidates.append(candidate)
        
        return candidates
    
    def _enhance_with_ontology(self, candidates: List[ConceptCandidate]) -> List[ConceptCandidate]:
        """
        Enhance extracted principles with ontology definitions.
        Links to proethica-intermediate ontology classes.
        """
        # Ontology mappings based on our enhanced definitions
        ontology_mappings = {
            'Public Safety Paramount': {
                'uri': 'http://proethica.org/ontology/intermediate#PublicSafetyPrinciple',
                'scholarly_grounding': 'McLaren 2003 - Exemplifies challenge of operationalizing abstract guidance',
                'extensional_note': 'Meaning of "hold paramount" emerges through NSPE case applications'
            },
            'Professional Integrity': {
                'uri': 'http://proethica.org/ontology/intermediate#IntegrityPrinciple',  
                'scholarly_grounding': 'Kong et al. 2020 - Requires contextual interpretation through cases',
                'extensional_note': 'Manifests differently across professional contexts'
            },
            'Transparency and Accountability': {
                'uri': 'http://proethica.org/ontology/intermediate#AccountabilityPrinciple',
                'scholarly_grounding': 'Professional responsibility for decisions and actions'
            }
        }
        
        for candidate in candidates:
            if candidate.label in ontology_mappings:
                mapping = ontology_mappings[candidate.label]
                candidate.debug = candidate.debug or {}
                candidate.debug.update({
                    'ontology_uri': mapping['uri'],
                    'scholarly_grounding': mapping.get('scholarly_grounding', ''),
                    'extensional_note': mapping.get('extensional_note', '')
                })
                # Boost confidence if matched to ontology
                candidate.confidence = min(1.0, candidate.confidence + 0.1)
        
        return candidates
    
    def _start_provenance_tracking(self, text: str, context: Optional[Dict[str, Any]]) -> Any:
        """
        Start PROV-O compliant provenance tracking for the extraction activity.
        """
        if not self.provenance_service:
            return None
            
        activity = ExtractionActivity(
            extraction_type='principle',
            source_text=text[:500],  # Store sample for provenance
            timestamp=datetime.now(),
            extractor_class=self.__class__.__name__,
            configuration={
                'enhanced_prompts': True,
                'chapter2_grounded': True,
                'ontology_enhanced': True
            }
        )
        
        # Add context if provided
        if context:
            activity.context = context
            
        # Create activity in provenance service
        return self.provenance_service.start_activity(activity)
    
    def _complete_provenance_tracking(self, activity: Any, candidates: List[ConceptCandidate]) -> None:
        """
        Complete provenance tracking with extraction results.
        """
        if not activity or not self.provenance_service:
            return
            
        # Record extracted entities
        for candidate in candidates:
            entity = EntityReference(
                label=candidate.label,
                entity_type='principle',
                confidence=candidate.confidence,
                metadata=candidate.debug
            )
            self.provenance_service.record_entity(activity, entity)
        
        # Complete activity
        self.provenance_service.complete_activity(activity, {
            'total_extracted': len(candidates),
            'extraction_completed': datetime.now().isoformat()
        })


def create_enhanced_principles_prompt(text: str, include_ontology_context: bool = True) -> str:
    """
    Standalone function to generate enhanced principles prompt.
    Can be used independently of the extractor class.
    """
    extractor = EnhancedPrinciplesExtractor()
    return extractor._generate_enhanced_prompt(text)