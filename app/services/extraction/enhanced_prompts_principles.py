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
        
    def extract(self, text: str, context: Optional[Dict[str, Any]] = None, 
                activity: Optional[Any] = None) -> List[ConceptCandidate]:
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
            
        # Use provided activity or create our own tracking
        own_activity = False
        if not activity:
            activity = self._start_provenance_tracking(text, context)
            own_activity = True
        
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
            
            # Complete provenance tracking only if we created the activity
            if own_activity:
                self._complete_provenance_tracking(activity, candidates)
            
            return candidates
            
        except Exception as e:
            logger.error(f"Error in enhanced principles extraction: {str(e)}")
            if activity and hasattr(self.provenance_service, 'record_error'):
                self.provenance_service.record_error(activity, str(e))
            return []
    
    def _generate_enhanced_prompt(self, text: str, include_mcp_context: bool = True, 
                                    existing_principles: list = None) -> str:
        """
        Generate an enhanced prompt based on Chapter 2.2.2 literature insights.
        
        Key insights from Chapter 2.2.2:
        - McLaren (2003): Extensional definition through concrete cases required
        - Taddeo et al. (2024): Three-step operationalization process essential
        - Anderson & Anderson (2018): Principles learned from expert examples
        - Hallamaa & Kalliokoski (2022): Context-sensitive mediating role
        - Prem (2023): Inherent challenge of operationalization
        - Benzmüller et al. (2020): Formal verification approaches
        - Segun (2021): Principles resist formal specification
        """
        
        # Fetch MCP data dynamically if not provided
        mcp_context = ""
        if include_mcp_context:
            try:
                # If existing_principles not provided, fetch from MCP server
                if existing_principles is None:
                    from app.services.external_mcp_client import get_external_mcp_client
                    import logging
                    
                    logger = logging.getLogger(__name__)
                    logger.info("Fetching principles context from external MCP server...")
                    
                    external_client = get_external_mcp_client()
                    existing_principles = external_client.get_all_principle_entities()
                    logger.info(f"Retrieved {len(existing_principles)} existing principles from MCP")
                
                # Build MCP context with full definitions
                if existing_principles:
                    mcp_context = f"""
EXISTING PRINCIPLES IN ONTOLOGY:
Found {len(existing_principles)} existing principle concepts in the professional ethics ontology:
"""
                    # Include ALL principles with their full definitions
                    for principle in existing_principles:
                        label = principle.get('label', 'Unknown')
                        definition = principle.get('definition', principle.get('description', 'No description'))
                        mcp_context += f"- **{label}**: {definition}\n"
                    
                    mcp_context += "\nConsider these when extracting new principles - identify if principles match existing concepts or are genuinely new.\n"
                else:
                    mcp_context = "No existing principles found in ontology (fresh setup)\n"
                    
            except Exception as e:
                logger.error(f"Failed to get MCP context for principles: {e}")
                mcp_context = "// MCP server unavailable - proceeding without ontology context\n"
        
        prompt = f"""{mcp_context}

You are analyzing an ethics guideline to extract PRINCIPLES based on the ProEthica formalism and Chapter 2.2.2 literature review.

THEORETICAL FRAMEWORK (Chapter 2.2.2 - Principles as Abstract Ethical Foundations):

According to the literature, principles represent abstract ethical foundations that require extensional definition through concrete cases and precedents (McLaren 2003). They cannot be applied through formal deduction alone but gain meaning through their manifestation in specific professional contexts.

**CORE PRINCIPLE CATEGORIES TO IDENTIFY:**

1. **Fundamental Ethical Principles**
   - Definition: Universal moral foundations like public welfare, integrity, respect for persons
   - Function: Highest-level abstractions requiring extensive interpretation
   - Extensional Grounding: Defined through landmark ethics cases and professional code applications
   - Example: "Hold paramount the safety, health, and welfare of the public" (NSPE Fundamental Canon 1)

2. **Professional Virtue Principles**  
   - Definition: Character-based principles defining professional excellence
   - Function: Guide professional identity and ethical sensitivities (Oakley & Cocking 2001)
   - Extensional Grounding: Exemplified through model professional behavior cases
   - Example: Integrity, Competence, Honesty, Accountability

3. **Relational Principles**
   - Definition: Principles governing professional relationships and trust
   - Function: Establish frameworks for stakeholder interactions
   - Extensional Grounding: Precedents from client-professional disputes and resolutions
   - Example: Confidentiality, Loyalty, Fairness, Transparency

4. **Domain-Specific Principles**
   - Definition: Principles particular to professional domain contexts
   - Function: Bridge general ethics to specific technical practices
   - Extensional Grounding: Industry-specific cases and technical standards applications
   - Example: Environmental Stewardship (engineering), Patient Autonomy (medicine)

**OPERATIONALIZATION PROCESS (Taddeo et al. 2024):**

For each principle, apply the three-step operationalization:
1. Identify abstraction level appropriate for the context
2. Interpret to extract specific professional requirements
3. Define criteria for balancing against other principles

**EXTRACTION GUIDELINES:**

- Focus on abstract values requiring interpretation, not specific rules
- Identify how principles mediate between ideals and practice (Hallamaa & Kalliokoski 2022)
- Link principles to concrete cases that give them meaning (McLaren 2003)
- Consider how principles generate multiple context-specific obligations
- Note potential conflicts between competing principles

GUIDELINE TEXT:
{text[:3000] if isinstance(text, str) else str(text)[:3000]}

OUTPUT FORMAT:
Return a JSON array with this structure:
[
  {{
    "label": "Public Welfare Paramount",
    "description": "Fundamental principle placing public safety and welfare above all other considerations",
    "type": "principle",
    "principle_category": "fundamental_ethical",  // One of: fundamental_ethical, professional_virtue, relational, domain_specific
    "extensional_definition": ["NSPE Case 92-6 on public safety disclosure", "Challenger disaster precedent"],
    "operationalization": {{
      "abstraction_level": "high",  // high, medium, low
      "specific_requirements": ["Report safety risks", "Refuse unsafe work", "Disclose conflicts"],
      "balancing_criteria": "Public welfare overrides client confidentiality when immediate danger exists"
    }},
    "mediating_function": "Transforms abstract duty to society into concrete professional actions",
    "derived_obligations": ["Report safety violations", "Maintain competence", "Disclose risks"],
    "context_sensitivity": "Interpretation varies by risk magnitude and immediacy",
    "potential_conflicts": ["Client confidentiality", "Employer loyalty"],
    "text_references": ["specific quote from text showing this principle"],
    "theoretical_grounding": "McLaren (2003) - Requires extensional definition through safety cases",
    "professional_grounding": "NSPE Fundamental Canon 1",
    "importance": "high",
    "is_existing": false,
    "ontology_match_reasoning": "Exact match to PublicWelfarePrinciple in ontology"
  }}
]

Focus on identifying principles that serve as abstract ethical foundations requiring interpretation rather than concrete rules or specific obligations.
"""

        return prompt
    
    def _extract_with_llm(self, text: str, prompt: str, activity: Any) -> List[ConceptCandidate]:
        """
        Extract principles using LLM with enhanced prompt.
        """
        try:
            # Call LLM with proper API based on client type
            if hasattr(self.llm_client, 'messages') and hasattr(self.llm_client.messages, 'create'):
                # Anthropic client
                response = self.llm_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2000,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                response_text = response.content[0].text if response.content else ""
            elif hasattr(self.llm_client, 'chat') and hasattr(self.llm_client.chat, 'completions'):
                # OpenAI client
                response = self.llm_client.chat.completions.create(
                    model="gpt-4",
                    max_tokens=2000,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                response_text = response.choices[0].message.content
            else:
                raise ValueError("Unknown LLM client type")
            
            response = response_text
            
            # Extract JSON from response (LLM might include extra text)
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                response = json_match.group(0)
            
            # Parse JSON response
            principles = json.loads(response)
            
            # Convert to ConceptCandidates with all enhanced fields
            candidates = []
            for p in principles:
                # Parse importance to confidence score
                importance = p.get('importance', 'medium')
                if importance == 'high':
                    confidence = 0.9
                elif importance == 'low':
                    confidence = 0.6
                else:
                    confidence = 0.75
                
                candidate = ConceptCandidate(
                    label=p.get('label', ''),
                    description=p.get('description', ''),
                    primary_type='principle',
                    category='principle',
                    confidence=confidence,
                    debug={
                        # Core categorization
                        'principle_category': p.get('principle_category'),
                        'importance': p.get('importance', 'medium'),
                        
                        # Extensional definition fields (McLaren 2003)
                        'extensional_definition': p.get('extensional_definition', []),
                        'text_references': p.get('text_references', []),
                        
                        # Operationalization fields (Taddeo et al. 2024)
                        'operationalization': p.get('operationalization', {}),
                        'abstraction_level': p.get('operationalization', {}).get('abstraction_level'),
                        'specific_requirements': p.get('operationalization', {}).get('specific_requirements', []),
                        'balancing_criteria': p.get('operationalization', {}).get('balancing_criteria'),
                        
                        # Mediation and context (Hallamaa & Kalliokoski 2022)
                        'mediating_function': p.get('mediating_function'),
                        'context_sensitivity': p.get('context_sensitivity'),
                        
                        # Relationships and grounding
                        'derived_obligations': p.get('derived_obligations', []),
                        'potential_conflicts': p.get('potential_conflicts', []),
                        'theoretical_grounding': p.get('theoretical_grounding'),
                        'professional_grounding': p.get('professional_grounding'),
                        
                        # Ontology matching
                        'is_existing': p.get('is_existing', False),
                        'ontology_match_reasoning': p.get('ontology_match_reasoning'),
                        
                        # Metadata
                        'extraction_method': 'enhanced_chapter2',
                        'extracted_at': datetime.now().isoformat()
                    }
                )
                candidates.append(candidate)
                
            return candidates
            
        except Exception as e:
            logger.error(f"LLM extraction failed: {str(e)}")
            return self._fallback_extraction(text)
    
    def _fallback_extraction(self, text) -> List[ConceptCandidate]:
        """
        Fallback heuristic extraction when LLM is unavailable.
        Based on common principle keywords from professional codes.
        """
        import re
        
        # Convert text to string if it's not already
        if not isinstance(text, str):
            text = str(text)
        
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


def create_enhanced_principles_prompt(text: str, include_mcp_context: bool = False, 
                                     existing_principles: list = None) -> str:
    """
    Standalone function to generate enhanced principles prompt.
    Can be used independently of the extractor class.
    
    Args:
        text: The guideline text to analyze
        include_mcp_context: Whether to include existing ontology concepts
        existing_principles: List of existing principle concepts from ontology
        
    Returns:
        Enhanced prompt string following Chapter 2.2.2 framework
    """
    extractor = EnhancedPrinciplesExtractor()
    return extractor._generate_enhanced_prompt(text, include_mcp_context, existing_principles)
