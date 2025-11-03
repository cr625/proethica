"""
Step 4 Part D: Institutional Rule Analyzer

Analyzes the normative framework (Principles, Obligations, Constraints) that
structures an engineering ethics case.

Theoretical foundation:
- Marchais-Roubelat & Roubelat (2015): Institutional rules as "what triggers/opposes action"
- Sohrabi et al. (2018): Structured knowledge analysis via AI planning

Maps ProEthica concepts to institutional rules:
- Principles (P): Fundamental ethical commitments
- Obligations (O): Professional duties from NSPE Code  
- Constraints (Cs): Legal/professional/organizational restrictions

Output: Case-level analysis of principle tensions, obligation conflicts,
and constraint influences that explain why this case matters.
"""

import logging
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from app.utils.llm_utils import get_llm_client
from app.models import db
from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass
class PrincipleTension:
    """Tension between two competing principles."""
    principle1: str
    principle1_uri: str
    principle2: str
    principle2_uri: str
    tension_description: str
    symbolic_significance: str


@dataclass
class ObligationConflict:
    """Conflict between professional obligations."""
    obligation1: str
    obligation1_uri: str
    obligation1_code_section: str
    obligation2: str
    obligation2_uri: str
    obligation2_code_section: str
    conflict_description: str


@dataclass
class ConstrainingFactor:
    """Constraint that shaped decision space."""
    constraint: str
    constraint_uri: str
    constraint_type: str  # legal, professional, organizational, resource
    impact_description: str


@dataclass
class InstitutionalAnalysis:
    """
    Complete institutional rule analysis for a case.
    
    Answers: What ethical framework structures this case?
    Why did these particular rules come into tension?
    What does this reveal about professional ethics?
    """
    principle_tensions: List[PrincipleTension]
    principle_conflict_description: str
    
    obligation_conflicts: List[ObligationConflict]
    obligation_conflict_description: str
    
    constraining_factors: List[ConstrainingFactor]
    constraint_influence_description: str
    
    case_significance: str  # Why this case matters / what it represents
    
    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        return {
            'principle_tensions': [
                {
                    'principle1': pt.principle1,
                    'principle1_uri': pt.principle1_uri,
                    'principle2': pt.principle2,
                    'principle2_uri': pt.principle2_uri,
                    'tension_description': pt.tension_description,
                    'symbolic_significance': pt.symbolic_significance
                }
                for pt in self.principle_tensions
            ],
            'principle_conflict_description': self.principle_conflict_description,
            'obligation_conflicts': [
                {
                    'obligation1': oc.obligation1,
                    'obligation1_uri': oc.obligation1_uri,
                    'obligation1_code_section': oc.obligation1_code_section,
                    'obligation2': oc.obligation2,
                    'obligation2_uri': oc.obligation2_uri,
                    'obligation2_code_section': oc.obligation2_code_section,
                    'conflict_description': oc.conflict_description
                }
                for oc in self.obligation_conflicts
            ],
            'obligation_conflict_description': self.obligation_conflict_description,
            'constraining_factors': [
                {
                    'constraint': cf.constraint,
                    'constraint_uri': cf.constraint_uri,
                    'constraint_type': cf.constraint_type,
                    'impact_description': cf.impact_description
                }
                for cf in self.constraining_factors
            ],
            'constraint_influence_description': self.constraint_influence_description,
            'case_significance': self.case_significance
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'InstitutionalAnalysis':
        """
        Reconstruct InstitutionalAnalysis from dictionary.

        Args:
            data: Dictionary from to_dict()

        Returns:
            InstitutionalAnalysis instance
        """
        # Reconstruct principle tensions
        principle_tensions = [
            PrincipleTension(
                principle1=pt['principle1'],
                principle1_uri=pt['principle1_uri'],
                principle2=pt['principle2'],
                principle2_uri=pt['principle2_uri'],
                tension_description=pt['tension_description'],
                symbolic_significance=pt['symbolic_significance']
            )
            for pt in data.get('principle_tensions', [])
        ]

        # Reconstruct obligation conflicts
        obligation_conflicts = [
            ObligationConflict(
                obligation1=oc['obligation1'],
                obligation1_uri=oc['obligation1_uri'],
                obligation1_code_section=oc['obligation1_code_section'],
                obligation2=oc['obligation2'],
                obligation2_uri=oc['obligation2_uri'],
                obligation2_code_section=oc['obligation2_code_section'],
                conflict_description=oc['conflict_description']
            )
            for oc in data.get('obligation_conflicts', [])
        ]

        # Reconstruct constraining factors
        constraining_factors = [
            ConstrainingFactor(
                constraint=cf['constraint'],
                constraint_uri=cf['constraint_uri'],
                constraint_type=cf['constraint_type'],
                impact_description=cf['impact_description']
            )
            for cf in data.get('constraining_factors', [])
        ]

        return cls(
            principle_tensions=principle_tensions,
            principle_conflict_description=data.get('principle_conflict_description', ''),
            obligation_conflicts=obligation_conflicts,
            obligation_conflict_description=data.get('obligation_conflict_description', ''),
            constraining_factors=constraining_factors,
            constraint_influence_description=data.get('constraint_influence_description', ''),
            case_significance=data.get('case_significance', '')
        )


class InstitutionalRuleAnalyzer:
    """
    Analyzes institutional rules (P, O, Cs) for a case.
    
    Inspired by Sohrabi et al. (2018) approach to structured knowledge analysis,
    adapted for retrospective case analysis rather than prospective scenario planning.
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize analyzer with LLM client.

        Args:
            llm_client: Optional pre-initialized LLM client. If None, will get one via get_llm_client().
                       Pass an existing client when calling from SSE generator to avoid Flask context issues.
        """
        if llm_client is not None:
            self.llm_client = llm_client
        else:
            self.llm_client = get_llm_client()
        logger.info("[Institutional Analyzer] Initialized")
    
    def analyze_case(
        self,
        case_id: int,
        principles: List[Any],
        obligations: List[Any],
        constraints: List[Any],
        case_context: Optional[Dict] = None
    ) -> InstitutionalAnalysis:
        """
        Analyze institutional rules for entire case.
        
        Args:
            case_id: Case ID
            principles: List of Principle entities (Pass 2)
            obligations: List of Obligation entities (Pass 2)
            constraints: List of Constraint entities (Pass 2)
            case_context: Optional context (questions, conclusions, actions)
            
        Returns:
            InstitutionalAnalysis with principle tensions, obligation conflicts, constraints
        """
        logger.info(f"[Institutional Analyzer] Analyzing case {case_id}")
        logger.info(f"  Principles: {len(principles)}, Obligations: {len(obligations)}, Constraints: {len(constraints)}")
        
        # Build prompt for LLM analysis
        prompt = self._build_analysis_prompt(principles, obligations, constraints, case_context)

        try:
            # Call LLM with Claude Sonnet 4
            # Using Sonnet 4 - Sonnet 4.5 has consistent timeout issues with complex reasoning tasks
            # See: chapter3_notes.md for detailed analysis of this model selection
            logger.info("[Institutional Analyzer] Calling LLM for institutional rule analysis...")
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = response.content[0].text
            logger.debug(f"[Institutional Analyzer] Response length: {len(response_text)} chars")

            # Store prompt and response for SSE streaming display
            self.last_prompt = prompt
            self.last_response = response_text

            # Extract JSON from response (may be wrapped in markdown code blocks)
            json_text = self._extract_json_from_response(response_text)

            # Parse JSON response
            analysis_data = json.loads(json_text)
            
            # Build InstitutionalAnalysis object
            analysis = self._parse_analysis_response(analysis_data)
            
            logger.info(f"[Institutional Analyzer] Analysis complete:")
            logger.info(f"  - {len(analysis.principle_tensions)} principle tensions")
            logger.info(f"  - {len(analysis.obligation_conflicts)} obligation conflicts")
            logger.info(f"  - {len(analysis.constraining_factors)} constraining factors")
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"[Institutional Analyzer] Failed to parse LLM JSON: {e}")
            logger.debug(f"Raw response: {response_text[:500]}...")
            raise
        except Exception as e:
            logger.error(f"[Institutional Analyzer] Analysis error: {e}")
            raise
    
    def save_to_database(
        self,
        case_id: int,
        analysis: InstitutionalAnalysis,
        llm_model: str = "claude-sonnet-4-20250514"
    ) -> bool:
        """
        Save institutional analysis to database.
        
        Args:
            case_id: Case ID
            analysis: InstitutionalAnalysis result
            llm_model: LLM model used
            
        Returns:
            True if successful
        """
        try:
            # Delete existing analysis
            delete_query = text("""
                DELETE FROM case_institutional_analysis WHERE case_id = :case_id
            """)
            db.session.execute(delete_query, {'case_id': case_id})
            
            # Insert new analysis
            insert_query = text("""
                INSERT INTO case_institutional_analysis (
                    case_id, principle_tensions, principle_conflict_description,
                    obligation_conflicts, obligation_conflict_description,
                    constraining_factors, constraint_influence_description,
                    case_significance, llm_model
                ) VALUES (
                    :case_id, :principle_tensions, :principle_conflict_description,
                    :obligation_conflicts, :obligation_conflict_description,
                    :constraining_factors, :constraint_influence_description,
                    :case_significance, :llm_model
                )
            """)
            
            analysis_dict = analysis.to_dict()
            
            db.session.execute(insert_query, {
                'case_id': case_id,
                'principle_tensions': json.dumps(analysis_dict['principle_tensions']),
                'principle_conflict_description': analysis.principle_conflict_description,
                'obligation_conflicts': json.dumps(analysis_dict['obligation_conflicts']),
                'obligation_conflict_description': analysis.obligation_conflict_description,
                'constraining_factors': json.dumps(analysis_dict['constraining_factors']),
                'constraint_influence_description': analysis.constraint_influence_description,
                'case_significance': analysis.case_significance,
                'llm_model': llm_model
            })
            
            db.session.commit()
            
            logger.info(f"[Institutional Analyzer] Saved analysis to database for case {case_id}")
            return True
            
        except Exception as e:
            logger.error(f"[Institutional Analyzer] Database save error: {e}")
            db.session.rollback()
            raise
    
    def _build_analysis_prompt(
        self,
        principles: List[Any],
        obligations: List[Any],
        constraints: List[Any],
        case_context: Optional[Dict]
    ) -> str:
        """Build LLM prompt for institutional analysis."""
        
        prompt = f"""Analyze the institutional rules (normative framework) for this engineering ethics case.

**Context**: Professional engineering ethics case published by NSPE Board of Ethical Review.

**Available Principles** ({len(principles)} total):
{self._format_principles(principles)}

**Available Obligations** ({len(obligations)} total):
{self._format_obligations(obligations)}

**Available Constraints** ({len(constraints)} total):
{self._format_constraints(constraints)}

**Task**: Identify the institutional rule structure that makes this case ethically significant.

**Analysis Questions**:
1. Which principles are in tension? (not just mentioned, but actually conflicting)
2. Which professional obligations conflict? (competing duties from NSPE Code)
3. What constraints shaped the decision space? (legal, professional, organizational limits)
4. Why did the NSPE Board publish this case? What strategic ethical issue does it represent?

**Output Format** (JSON only, no markdown):
{{
  "principle_tensions": [
    {{
      "principle1": "Principle Name",
      "principle1_uri": "uri",
      "principle2": "Principle Name 2",
      "principle2_uri": "uri",
      "tension_description": "Clear description of how these principles create ethical tension",
      "symbolic_significance": "What this tension represents for the profession"
    }}
  ],
  "principle_conflict_description": "Overall narrative of how principles structure this case",
  "obligation_conflicts": [
    {{
      "obligation1": "Obligation Name",
      "obligation1_uri": "uri",
      "obligation1_code_section": "III.2.a",
      "obligation2": "Obligation Name 2",
      "obligation2_uri": "uri",
      "obligation2_code_section": "III.9",
      "conflict_description": "How these obligations conflict in this case"
    }}
  ],
  "obligation_conflict_description": "Overall narrative of obligation tensions",
  "constraining_factors": [
    {{
      "constraint": "Constraint Name",
      "constraint_uri": "uri",
      "constraint_type": "legal|professional|organizational|resource",
      "impact_description": "How this constraint shaped choices"
    }}
  ],
  "constraint_influence_description": "How constraints shaped the decision space",
  "case_significance": "Why this case matters - what strategic ethical issue it represents for professional engineering practice"
}}

Respond with valid JSON only. Focus on ACTUAL tensions and conflicts, not just lists of concepts."""

        return prompt
    
    def _get_entity_attr(self, entity: Any, attr_name: str, default: Any = None) -> Any:
        """Get entity attribute, checking both TemporaryRDFStorage and OntServe naming."""
        temp_name = f'entity_{attr_name}'
        temp_val = getattr(entity, temp_name, None)
        if temp_val is not None:
            return temp_val
        std_val = getattr(entity, attr_name, None)
        if std_val is not None:
            return std_val
        return default

    def _format_principles(self, principles: List[Any]) -> str:
        """Format principles for LLM (without URIs to reduce prompt size)."""
        if not principles:
            return "None available"

        lines = []
        for i, p in enumerate(principles[:20], 1):
            label = self._get_entity_attr(p, 'label', 'Unknown')
            definition = self._get_entity_attr(p, 'definition', '')
            # Omit URI to reduce prompt size
            lines.append(f"{i}. **{label}**: {definition}")

        if len(principles) > 20:
            lines.append(f"... and {len(principles) - 20} more")

        return "\n".join(lines)
    
    def _format_obligations(self, obligations: List[Any]) -> str:
        """Format obligations for LLM (without URIs to reduce prompt size)."""
        if not obligations:
            return "None available"

        lines = []
        for i, o in enumerate(obligations[:20], 1):
            label = self._get_entity_attr(o, 'label', 'Unknown')

            # Get obligation statement from RDF
            rdf_data = getattr(o, 'rdf_json_ld', {}) or {}
            props = rdf_data.get('properties', {})
            statement = props.get('obligationStatement', [''])[0] if 'obligationStatement' in props else ''
            code_section = props.get('derivedFrom', [''])[0] if 'derivedFrom' in props else ''

            # Omit URI to reduce prompt size
            lines.append(f"{i}. **{label}**: {statement}\n   Code: {code_section}")

        if len(obligations) > 20:
            lines.append(f"... and {len(obligations) - 20} more")

        return "\n".join(lines)
    
    def _format_constraints(self, constraints: List[Any]) -> str:
        """Format constraints for LLM (without URIs to reduce prompt size)."""
        if not constraints:
            return "None available"

        lines = []
        for i, c in enumerate(constraints[:20], 1):
            label = self._get_entity_attr(c, 'label', 'Unknown')
            definition = self._get_entity_attr(c, 'definition', '')
            # Omit URI to reduce prompt size
            lines.append(f"{i}. **{label}**: {definition}")

        if len(constraints) > 20:
            lines.append(f"... and {len(constraints) - 20} more")

        return "\n".join(lines)
    
    def _parse_analysis_response(self, data: Dict) -> InstitutionalAnalysis:
        """Parse LLM JSON response into InstitutionalAnalysis object."""
        
        # Parse principle tensions
        principle_tensions = []
        for pt_data in data.get('principle_tensions', []):
            principle_tensions.append(PrincipleTension(
                principle1=pt_data.get('principle1', ''),
                principle1_uri=pt_data.get('principle1_uri', ''),
                principle2=pt_data.get('principle2', ''),
                principle2_uri=pt_data.get('principle2_uri', ''),
                tension_description=pt_data.get('tension_description', ''),
                symbolic_significance=pt_data.get('symbolic_significance', '')
            ))
        
        # Parse obligation conflicts
        obligation_conflicts = []
        for oc_data in data.get('obligation_conflicts', []):
            obligation_conflicts.append(ObligationConflict(
                obligation1=oc_data.get('obligation1', ''),
                obligation1_uri=oc_data.get('obligation1_uri', ''),
                obligation1_code_section=oc_data.get('obligation1_code_section', ''),
                obligation2=oc_data.get('obligation2', ''),
                obligation2_uri=oc_data.get('obligation2_uri', ''),
                obligation2_code_section=oc_data.get('obligation2_code_section', ''),
                conflict_description=oc_data.get('conflict_description', '')
            ))
        
        # Parse constraining factors
        constraining_factors = []
        for cf_data in data.get('constraining_factors', []):
            constraining_factors.append(ConstrainingFactor(
                constraint=cf_data.get('constraint', ''),
                constraint_uri=cf_data.get('constraint_uri', ''),
                constraint_type=cf_data.get('constraint_type', 'unknown'),
                impact_description=cf_data.get('impact_description', '')
            ))
        
        return InstitutionalAnalysis(
            principle_tensions=principle_tensions,
            principle_conflict_description=data.get('principle_conflict_description', ''),
            obligation_conflicts=obligation_conflicts,
            obligation_conflict_description=data.get('obligation_conflict_description', ''),
            constraining_factors=constraining_factors,
            constraint_influence_description=data.get('constraint_influence_description', ''),
            case_significance=data.get('case_significance', '')
        )

    def _extract_json_from_response(self, response_text: str) -> str:
        """
        Extract JSON from LLM response, handling markdown code blocks.

        Args:
            response_text: Raw LLM response text

        Returns:
            Extracted JSON string
        """
        import re

        # Try to find JSON in markdown code blocks first
        json_match = re.search(r'```json\s*\n(.*?)\n```', response_text, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()

        # Try generic code block
        code_match = re.search(r'```\s*\n(.*?)\n```', response_text, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # Try to find JSON object directly (starts with { and ends with })
        json_obj_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_obj_match:
            return json_obj_match.group(0).strip()

        # If all else fails, return the original text and let json.loads fail with a better error
        logger.warning("[Institutional Analyzer] Could not extract JSON from response, trying raw text")
        return response_text.strip()
