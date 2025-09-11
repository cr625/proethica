"""
Enhanced Constraints Extraction with Chapter 2 Literature Grounding
Based on Pass 2: Normative (SHOULD/MUST/CAN'T) - Limitations and Restrictions

This module implements constraint extraction grounded in professional ethics literature,
focusing on identifying limitations, restrictions, and boundaries that constrain
ethical decision-making and professional action.
"""

from typing import List, Dict, Any, Optional
import logging
import json
from datetime import datetime

from .base import ConceptCandidate

# Optional provenance tracking
try:
    from app.models.provenance import ProvenanceActivity
    from app.services.provenance_service import get_provenance_service
except ImportError:
    ProvenanceActivity = None
    get_provenance_service = lambda: None

logger = logging.getLogger(__name__)


def create_enhanced_constraints_prompt(text: str) -> str:
    """
    Create an enhanced prompt for constraint extraction based on professional ethics literature.
    
    Theoretical foundations:
    - Jensen & Meckling (1976): Resource and informational constraints on decision-making
    - Simon (1955): Bounded rationality and decision constraints
    - NSPE Guidelines: Technical, legal, and ethical boundaries
    - Sutton & Barto (2018): Environmental constraints on agent actions
    """
    
    prompt = f"""You are an expert in professional ethics and constraint analysis, specifically trained in identifying 
limitations, restrictions, and boundaries that affect ethical decision-making in engineering contexts.

THEORETICAL GROUNDING:
Based on decision theory and professional ethics literature (Jensen & Meckling 1976, Simon 1955), constraints represent:
1. **Limitations** that restrict available options or actions
2. **Boundaries** that cannot be crossed (legal, ethical, technical)
3. **Resource restrictions** (time, budget, materials, personnel)
4. **Information limitations** (uncertainty, incomplete data)
5. **External requirements** (regulations, standards, policies)

CONSTRAINT CATEGORIES:
1. **Resource Constraints**: Budget, time, materials, personnel limitations
2. **Technical Constraints**: Physical laws, technological limitations, feasibility
3. **Legal/Regulatory**: Laws, codes, standards, compliance requirements
4. **Ethical Boundaries**: Non-negotiable ethical limits (e.g., no harm to public)
5. **Informational Constraints**: Data availability, uncertainty, knowledge gaps
6. **Organizational Constraints**: Policies, procedures, hierarchical limitations
7. **Environmental Constraints**: Physical environment, sustainability requirements
8. **Stakeholder Constraints**: Client requirements, public expectations

EXTRACTION TASK:
Analyze the following discussion/analysis text and identify ALL constraints that limit or restrict decision-making and action.

For each constraint, provide:
1. **label**: A clear, descriptive name (e.g., "Budget Limitation", "Safety Code Compliance")
2. **description**: What this constraint restricts or limits in the specific context
3. **constraint_category**: Category from above (resource, technical, legal, etc.)
4. **flexibility**: How negotiable is this constraint (non-negotiable, flexible, soft)
5. **impact_on_decisions**: How this constraint affects available options
6. **affected_stakeholders**: Who is impacted by this constraint
7. **potential_violations**: What happens if this constraint is violated
8. **mitigation_strategies**: Possible ways to work within or around the constraint
9. **temporal_aspect**: Is this constraint permanent, temporary, or conditional
10. **quantifiable_metrics**: Measurable aspects if applicable (e.g., "$X budget", "Y days")

TEXT TO ANALYZE:
{text}

IMPORTANT EXTRACTION GUIDELINES:
- Identify both explicit constraints ("limited by", "cannot", "restricted to") and implicit ones
- Look for resource limitations mentioned in the context
- Consider legal and regulatory requirements as hard constraints
- Note ethical boundaries that cannot be crossed
- Include constraints from multiple perspectives (technical, social, economic)
- Distinguish between hard constraints (must not violate) and soft constraints (preferably avoid)
- Consider how constraints interact and potentially conflict

Return your analysis as a JSON array of constraint objects.
Each object should contain all fields specified above.
Focus on constraints that are:
1. Significant to the decision-making process
2. Clearly defined or measurable when possible
3. Relevant to the ethical dimensions of the case
4. Important for understanding solution boundaries

Example format:
[
    {{
        "label": "Project Budget Limit",
        "description": "Total project budget cannot exceed $500,000",
        "constraint_category": "resource",
        "flexibility": "non-negotiable",
        "impact_on_decisions": "Eliminates high-cost safety features and premium materials",
        "affected_stakeholders": ["client", "contractor", "end users"],
        "potential_violations": "Project cancellation, legal breach of contract",
        "mitigation_strategies": ["Value engineering", "Phased implementation", "Cost-benefit optimization"],
        "temporal_aspect": "permanent",
        "quantifiable_metrics": "$500,000 maximum budget"
    }}
]
"""
    return prompt


class EnhancedConstraintsExtractor:
    """
    Enhanced extractor for constraints based on decision theory and ethics literature.
    
    Key theoretical foundations:
    - Jensen & Meckling (1976): Agency theory and resource constraints
    - Simon (1955): Bounded rationality and decision constraints
    - NSPE Guidelines: Professional and ethical boundaries
    - Sutton & Barto (2018): Environmental constraints on actions
    """
    
    def __init__(self, llm_client=None, provenance_service=None):
        self.llm_client = llm_client
        self.provenance_service = provenance_service or get_provenance_service()
        
    def extract(self, text: str, context: Optional[Dict[str, Any]] = None,
                activity: Optional[ProvenanceActivity] = None) -> List[ConceptCandidate]:
        """
        Extract constraints with enhanced prompt based on decision theory literature.
        
        Args:
            text: The discussion/analysis text to extract constraints from
            context: Optional context including case metadata
            activity: Optional provenance activity for tracking
            
        Returns:
            List of ConceptCandidate objects representing extracted constraints
        """
        if not text:
            return []
            
        try:
            # Generate enhanced prompt
            prompt = create_enhanced_constraints_prompt(text)
            
            # Record prompt in provenance if available
            if activity and self.provenance_service:
                prompt_entity = self.provenance_service.record_prompt(
                    prompt_text=prompt,
                    activity=activity,
                    entity_name="constraints_extraction_prompt",
                    metadata={
                        'extractor': 'EnhancedConstraintsExtractor',
                        'prompt_version': '2.0_normative_pass',
                        'theoretical_grounding': 'Jensen & Meckling 1976, Simon 1955'
                    }
                )
            
            # Get LLM extraction if available
            if self.llm_client:
                candidates = self._extract_with_llm(text, prompt, activity)
            else:
                candidates = self._fallback_extraction(text)
                
            # Enhance with regulatory ontology if available
            candidates = self._enhance_with_regulatory_ontology(candidates)
            
            return candidates
            
        except Exception as e:
            logger.error(f"Error in enhanced constraints extraction: {str(e)}")
            if activity and self.provenance_service:
                self.provenance_service.record_extraction_results(
                    results=[],
                    activity=activity,
                    entity_type='extracted_constraints_error',
                    metadata={'error': str(e)}
                )
            return []
    
    def _extract_with_llm(self, text: str, prompt: str, activity: Optional[ProvenanceActivity]) -> List[ConceptCandidate]:
        """Extract constraints using LLM with the enhanced prompt."""
        try:
            # Call LLM with proper API based on client type
            if hasattr(self.llm_client, 'messages') and hasattr(self.llm_client.messages, 'create'):
                # Anthropic client
                llm_response = self.llm_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2000,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                response = llm_response.content[0].text if llm_response.content else ""
            elif hasattr(self.llm_client, 'chat') and hasattr(self.llm_client.chat, 'completions'):
                # OpenAI client
                llm_response = self.llm_client.chat.completions.create(
                    model="gpt-4",
                    max_tokens=2000,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                response = llm_response.choices[0].message.content
            else:
                raise ValueError("Unknown LLM client type")
            
            # Record response in provenance if available
            if activity and self.provenance_service:
                response_entity = self.provenance_service.record_response(
                    response_text=response,
                    activity=activity,
                    entity_name="constraints_llm_response",
                    metadata={
                        'model': getattr(self.llm_client, 'model_name', 'unknown'),
                        'token_count': len(response.split())
                    }
                )
            
            # Parse JSON response
            try:
                constraints_data = json.loads(response)
                if not isinstance(constraints_data, list):
                    constraints_data = [constraints_data]
            except json.JSONDecodeError:
                logger.warning("Failed to parse LLM response as JSON, attempting text extraction")
                constraints_data = self._parse_text_response(response)
            
            # Convert to ConceptCandidates
            candidates = []
            for item in constraints_data:
                candidate = ConceptCandidate(
                    label=item.get('label', 'Unknown Constraint'),
                    description=item.get('description', ''),
                    primary_type='constraint',
                    category='constraint',
                    confidence=0.85,  # Base confidence for LLM extraction
                    debug={
                        'constraint_category': item.get('constraint_category', 'resource'),
                        'flexibility': item.get('flexibility', 'non-negotiable'),
                        'impact_on_decisions': item.get('impact_on_decisions', ''),
                        'affected_stakeholders': item.get('affected_stakeholders', []),
                        'potential_violations': item.get('potential_violations', ''),
                        'mitigation_strategies': item.get('mitigation_strategies', []),
                        'temporal_aspect': item.get('temporal_aspect', 'permanent'),
                        'quantifiable_metrics': item.get('quantifiable_metrics', ''),
                        'extraction_method': 'llm_enhanced',
                        'prompt_version': '2.0_normative_pass'
                    }
                )
                candidates.append(candidate)
            
            # Record extraction results in provenance
            if activity and self.provenance_service:
                self.provenance_service.record_extraction_results(
                    results=[{
                        'label': c.label,
                        'description': c.description,
                        'confidence': c.confidence,
                        'debug': c.debug
                    } for c in candidates],
                    activity=activity,
                    entity_type='extracted_constraints',
                    metadata={'count': len(candidates), 'method': 'llm_enhanced'}
                )
            
            return candidates
            
        except Exception as e:
            logger.error(f"LLM extraction failed: {str(e)}")
            return self._fallback_extraction(text)
    
    def _parse_text_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse non-JSON text response for constraints."""
        constraints = []
        
        # Look for constraint patterns in text
        lines = response.split('\n')
        current_constraint = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_constraint:
                    constraints.append(current_constraint)
                    current_constraint = {}
                continue
                
            # Look for labeled items
            if line.startswith('-') or line.startswith('*') or line.startswith('•'):
                if current_constraint:
                    constraints.append(current_constraint)
                current_constraint = {'label': line[1:].strip(), 'description': ''}
            elif ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                current_constraint[key] = value.strip()
            elif current_constraint:
                current_constraint['description'] += ' ' + line
        
        if current_constraint:
            constraints.append(current_constraint)
            
        return constraints
    
    def _fallback_extraction(self, text: str) -> List[ConceptCandidate]:
        """Fallback heuristic extraction when LLM is unavailable."""
        candidates = []
        
        # Simple keyword-based extraction for constraints
        constraint_patterns = [
            (r'\blimited\s+to\s+(\w+(?:\s+\w+){0,3})', 'resource'),
            (r'\bcannot\s+(\w+(?:\s+\w+){0,3})', 'technical'),
            (r'\bmust\s+not\s+(\w+(?:\s+\w+){0,3})', 'ethical'),
            (r'\brestricted\s+to\s+(\w+(?:\s+\w+){0,3})', 'legal'),
            (r'\bmaximum\s+(\w+(?:\s+\w+){0,3})', 'resource'),
            (r'\bminimum\s+(\w+(?:\s+\w+){0,3})', 'technical'),
            (r'\bprohibited\s+from\s+(\w+(?:\s+\w+){0,3})', 'legal'),
            (r'\bbudget\s+of\s+(\$?[\d,]+)', 'resource'),
            (r'\bdeadline\s+of\s+(\w+(?:\s+\w+){0,3})', 'resource'),
            (r'\bcompliance\s+with\s+(\w+(?:\s+\w+){0,3})', 'legal'),
        ]
        
        import re
        for pattern, category in constraint_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                constraint_text = match.group(1) if match.lastindex else match.group(0)
                candidate = ConceptCandidate(
                    label=f"{constraint_text.title()} Constraint",
                    description=f"Constraint limiting {constraint_text}",
                    primary_type='constraint',
                    category='constraint',
                    confidence=0.6,  # Lower confidence for heuristic extraction
                    debug={
                        'constraint_category': category,
                        'flexibility': 'non-negotiable' if category in ['legal', 'ethical'] else 'flexible',
                        'extraction_method': 'heuristic_fallback',
                        'pattern_matched': pattern
                    }
                )
                candidates.append(candidate)
        
        # Look for budget constraints
        budget_pattern = r'\$[\d,]+(?:\.\d{2})?'
        budget_matches = re.finditer(budget_pattern, text)
        for match in budget_matches:
            amount = match.group(0)
            candidate = ConceptCandidate(
                label=f"Budget Constraint {amount}",
                description=f"Financial constraint of {amount}",
                concept_type='constraint',
                confidence=0.7,
                debug={
                    'constraint_category': 'resource',
                    'flexibility': 'non-negotiable',
                    'quantifiable_metrics': amount,
                    'extraction_method': 'heuristic_fallback'
                }
            )
            candidates.append(candidate)
        
        return candidates
    
    def _enhance_with_regulatory_ontology(self, candidates: List[ConceptCandidate]) -> List[ConceptCandidate]:
        """Enhance candidates with regulatory and standards references if available."""
        # This would connect to regulatory ontology via MCP if available
        # For now, add standard regulatory categories
        
        regulatory_keywords = {
            'code': 'Building/Engineering Code Compliance',
            'regulation': 'Regulatory Requirement',
            'standard': 'Industry Standard Compliance',
            'law': 'Legal Requirement',
            'permit': 'Permitting Requirement',
            'safety': 'Safety Standard Compliance',
            'environmental': 'Environmental Regulation',
            'osha': 'OSHA Compliance',
            'epa': 'EPA Regulation',
            'iso': 'ISO Standard'
        }
        
        for candidate in candidates:
            # Try to match with regulatory categories
            label_lower = candidate.label.lower()
            desc_lower = candidate.description.lower()
            
            for keyword, category in regulatory_keywords.items():
                if keyword in label_lower or keyword in desc_lower:
                    candidate.debug['regulatory_category'] = category
                    candidate.debug['constraint_category'] = 'legal'
                    candidate.debug['flexibility'] = 'non-negotiable'
                    candidate.confidence = min(candidate.confidence * 1.1, 1.0)  # Boost confidence
                    break
        
        return candidates