"""
Engineering Ethics adapter for NSPE case deconstruction.

This adapter specializes in deconstructing NSPE (National Society of Professional Engineers)
ethics cases into structured components for scenario generation and analysis.
"""

import re
from typing import Dict, List, Any, Optional
import logging

from .base_adapter import BaseCaseDeconstructionAdapter
from .data_models import (
    Stakeholder, StakeholderRole,
    EthicalDecisionPoint, DecisionType, DecisionOption, ComponentAction,
    ReasoningChain, ReasoningStep, AlternativePath
)


logger = logging.getLogger(__name__)


class EngineeringEthicsAdapter(BaseCaseDeconstructionAdapter):
    """
    NSPE Engineering Ethics case deconstruction adapter.
    
    Specializes in extracting engineering-specific stakeholders, ethical dilemmas,
    and reasoning patterns from NSPE ethics cases.
    """
    
    def __init__(self):
        super().__init__("engineering_ethics", "1.0")
        
        # Engineering-specific stakeholder patterns
        self.stakeholder_patterns = {
            StakeholderRole.PROFESSIONAL: [
                r'\bengineer(?:s)?\b', r'\bdesigner(?:s)?\b', r'\bconsultant(?:s)?\b',
                r'\bproject manager(?:s)?\b', r'\btechnical(?:\s+\w+)*\s+engineer(?:s)?\b'
            ],
            StakeholderRole.CLIENT: [
                r'\bclient(?:s)?\b', r'\bcustomer(?:s)?\b', r'\bowner(?:s)?\b'
            ],
            StakeholderRole.EMPLOYER: [
                r'\bemployer(?:s)?\b', r'\bcompany\b', r'\bfirm\b', r'\bcorporation\b'
            ],
            StakeholderRole.PUBLIC: [
                r'\bpublic\b', r'\bcitizen(?:s)?\b', r'\bcommunity\b', r'\bsociety\b'
            ],
            StakeholderRole.REGULATOR: [
                r'\bregulatory\s+(?:agency|body|authority)\b', r'\bgovernment\b',
                r'\bstate\s+(?:agency|board)\b', r'\bmunicipal(?:ity)?\b'
            ]
        }
        
        # NSPE Code principles mapping
        self.nspe_principles = {
            'public_safety': 'Hold paramount the safety, health, and welfare of the public',
            'competence': 'Perform services only in areas of their competence', 
            'objective_truthful': 'Issue public statements only in an objective and truthful manner',
            'employer_client_agent': 'Act for each employer or client as faithful agents or trustees',
            'avoid_conflicts': 'Avoid deceptive acts',
            'conduct_honorably': 'Conduct themselves honorably, responsibly, ethically, and lawfully'
        }
        
        # Common engineering decision types
        self.decision_type_patterns = {
            DecisionType.SAFETY: [
                r'\bsafety\b', r'\bhazard(?:s)?\b', r'\brisk(?:s)?\b', r'\bdanger(?:ous)?\b'
            ],
            DecisionType.DISCLOSURE: [
                r'\bdisclos(?:e|ure)\b', r'\breport(?:ing)?\b', r'\bwhistleblow(?:er|ing)?\b'
            ],
            DecisionType.CONFIDENTIALITY: [
                r'\bconfidential(?:ity)?\b', r'\bproprietary\b', r'\btrade\s+secret(?:s)?\b'
            ],
            DecisionType.PROFESSIONAL_DUTY: [
                r'\bprofessional\s+(?:duty|obligation|responsibility)\b', r'\bcompetenc(?:e|y)\b'
            ],
            DecisionType.CONFLICT_OF_INTEREST: [
                r'\bconflict\s+of\s+interest\b', r'\bbias(?:ed)?\b', r'\bimpartial(?:ity)?\b'
            ]
        }
    
    def extract_stakeholders(self, case_content: Dict[str, Any]) -> List[Stakeholder]:
        """Extract engineering-specific stakeholders from NSPE case."""
        stakeholders = []
        
        # Get case text for analysis
        case_text = self._get_case_text(case_content)
        
        # Extract stakeholders using pattern matching
        for role, patterns in self.stakeholder_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, case_text, re.IGNORECASE)
                for match in matches:
                    # Extract context around the match
                    start = max(0, match.start() - 50)
                    end = min(len(case_text), match.end() + 50)
                    context = case_text[start:end].strip()
                    
                    # Create stakeholder
                    stakeholder_name = self._generate_stakeholder_name(role, match.group())
                    description = f"Identified from context: {context}"
                    
                    # Avoid duplicates
                    if not any(s.name == stakeholder_name for s in stakeholders):
                        stakeholder = Stakeholder(
                            name=stakeholder_name,
                            role=role,
                            description=description,
                            interests=self._infer_stakeholder_interests(role, context)
                        )
                        stakeholders.append(stakeholder)
        
        # Ensure we have at least a primary engineer
        if not any(s.role == StakeholderRole.PROFESSIONAL for s in stakeholders):
            stakeholders.append(Stakeholder(
                name="Primary Engineer",
                role=StakeholderRole.PROFESSIONAL,
                description="The professional engineer at the center of the ethical dilemma",
                interests=["professional_integrity", "career_advancement", "technical_excellence"]
            ))
        
        return stakeholders[:6]  # Limit to 6 most relevant stakeholders
    
    def identify_ethical_decision_points(self, case_content: Dict[str, Any]) -> List[EthicalDecisionPoint]:
        """Identify engineering ethics decision points in the case."""
        decision_points = []
        
        case_text = self._get_case_text(case_content)
        discussion_text = self._get_section_text(case_content, 'discussion')
        
        # Identify decision types present in the case
        identified_types = self._identify_decision_types(case_text)
        
        for decision_type in identified_types:
            # Extract relevant principles
            relevant_principles = self._get_relevant_principles(decision_type)
            
            # Create decision point
            decision_point = EthicalDecisionPoint(
                decision_id=f"decision_{decision_type.value}",
                title=self._generate_decision_title(decision_type, case_text),
                description=self._extract_decision_description(decision_type, discussion_text),
                decision_type=decision_type,
                ethical_principles=relevant_principles,
                primary_options=self._generate_decision_options(decision_type, case_text),
                context_factors=self._extract_context_factors(case_text)
            )
            
            decision_points.append(decision_point)
        
        # If no specific decisions identified, create a general professional judgment decision
        if not decision_points:
            decision_points.append(self._create_default_decision_point(case_text))
        
        return decision_points
    
    def extract_reasoning_chain(self, case_content: Dict[str, Any]) -> ReasoningChain:
        """Extract the reasoning chain from facts to conclusion."""
        
        # Extract case components
        facts = self._extract_facts(case_content)
        discussion = self._get_section_text(case_content, 'discussion')
        conclusion = self._get_section_text(case_content, 'conclusion')
        
        # Build reasoning chain
        reasoning_chain = ReasoningChain(
            case_facts=facts,
            applicable_principles=self._extract_applicable_principles(discussion),
            reasoning_steps=self._extract_reasoning_steps(discussion),
            predicted_outcome=self._extract_predicted_outcome(conclusion),
            actual_outcome=conclusion if conclusion else ""
        )
        
        return reasoning_chain
    
    def _get_case_text(self, case_content: Dict[str, Any]) -> str:
        """Get the full case text for analysis."""
        # Try to get from content field
        if 'content' in case_content:
            return str(case_content['content'])
        
        # Try to combine sections
        sections = []
        for section_name in ['facts', 'discussion', 'conclusion', 'questions']:
            section_text = self._get_section_text(case_content, section_name)
            if section_text:
                sections.append(section_text)
        
        return ' '.join(sections)
    
    def _get_section_text(self, case_content: Dict[str, Any], section_name: str) -> str:
        """Get text from a specific section."""
        # Try doc_metadata sections first
        doc_metadata = case_content.get('doc_metadata', {})
        sections = doc_metadata.get('sections', {})
        
        if section_name in sections:
            section_data = sections[section_name]
            if isinstance(section_data, dict):
                return section_data.get('content', '') or section_data.get('text', '')
            elif isinstance(section_data, str):
                return section_data
        
        # Try direct field access
        return case_content.get(section_name, '')
    
    def _generate_stakeholder_name(self, role: StakeholderRole, matched_text: str) -> str:
        """Generate a descriptive name for a stakeholder."""
        role_names = {
            StakeholderRole.PROFESSIONAL: "Professional Engineer",
            StakeholderRole.CLIENT: "Client",
            StakeholderRole.EMPLOYER: "Employer",
            StakeholderRole.PUBLIC: "Public",
            StakeholderRole.REGULATOR: "Regulatory Authority"
        }
        return role_names.get(role, matched_text.title())
    
    def _infer_stakeholder_interests(self, role: StakeholderRole, context: str) -> List[str]:
        """Infer likely interests based on stakeholder role and context."""
        interest_mapping = {
            StakeholderRole.PROFESSIONAL: ["professional_integrity", "career_advancement", "technical_competence"],
            StakeholderRole.CLIENT: ["project_success", "cost_effectiveness", "timely_delivery"],
            StakeholderRole.EMPLOYER: ["company_reputation", "profitability", "legal_compliance"],
            StakeholderRole.PUBLIC: ["safety", "welfare", "environmental_protection"],
            StakeholderRole.REGULATOR: ["regulatory_compliance", "public_safety", "oversight"]
        }
        return interest_mapping.get(role, ["general_welfare"])
    
    def _identify_decision_types(self, case_text: str) -> List[DecisionType]:
        """Identify what types of decisions are present in the case."""
        identified_types = []
        
        for decision_type, patterns in self.decision_type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, case_text, re.IGNORECASE):
                    identified_types.append(decision_type)
                    break
        
        # Default to professional duty if nothing specific found
        if not identified_types:
            identified_types.append(DecisionType.PROFESSIONAL_DUTY)
        
        return identified_types
    
    def _get_relevant_principles(self, decision_type: DecisionType) -> List[str]:
        """Get NSPE principles relevant to a decision type."""
        principle_mapping = {
            DecisionType.SAFETY: ["public_safety", "competence"],
            DecisionType.DISCLOSURE: ["public_safety", "objective_truthful"],
            DecisionType.CONFIDENTIALITY: ["employer_client_agent", "avoid_conflicts"],
            DecisionType.PROFESSIONAL_DUTY: ["competence", "conduct_honorably"],
            DecisionType.CONFLICT_OF_INTEREST: ["avoid_conflicts", "employer_client_agent"]
        }
        
        relevant_keys = principle_mapping.get(decision_type, ["conduct_honorably"])
        return [self.nspe_principles[key] for key in relevant_keys if key in self.nspe_principles]
    
    def _generate_decision_title(self, decision_type: DecisionType, case_text: str) -> str:
        """Generate a descriptive title for the decision."""
        titles = {
            DecisionType.SAFETY: "Safety Risk Disclosure Decision",
            DecisionType.DISCLOSURE: "Information Disclosure Decision", 
            DecisionType.CONFIDENTIALITY: "Confidentiality vs Transparency Decision",
            DecisionType.PROFESSIONAL_DUTY: "Professional Duty Decision",
            DecisionType.CONFLICT_OF_INTEREST: "Conflict of Interest Resolution"
        }
        return titles.get(decision_type, "Professional Ethical Decision")
    
    def _extract_decision_description(self, decision_type: DecisionType, discussion_text: str) -> str:
        """Extract description of the decision from discussion text."""
        if not discussion_text:
            return f"Decision regarding {decision_type.value.replace('_', ' ')}"
        
        # Take first 200 characters of discussion as description
        return discussion_text[:200] + "..." if len(discussion_text) > 200 else discussion_text
    
    def _generate_decision_options(self, decision_type: DecisionType, case_text: str) -> List[DecisionOption]:
        """Generate typical decision options for this type of decision."""
        options_map = {
            DecisionType.SAFETY: [
                DecisionOption(
                    option_id="disclose_risk",
                    title="Disclose Safety Risk",
                    ethical_justification="Prioritizes public safety and welfare as mandated by NSPE Code"
                ),
                DecisionOption(
                    option_id="maintain_confidentiality", 
                    title="Maintain Client Confidentiality",
                    ethical_justification="Honors professional duty to client while seeking alternative solutions"
                )
            ],
            DecisionType.DISCLOSURE: [
                DecisionOption(
                    option_id="full_disclosure",
                    title="Full Disclosure to Authorities",
                    ethical_justification="Ensures transparency and public protection"
                ),
                DecisionOption(
                    option_id="internal_resolution",
                    title="Seek Internal Resolution First", 
                    ethical_justification="Attempts to resolve issues through proper channels"
                )
            ]
        }
        
        return options_map.get(decision_type, [
            DecisionOption(
                option_id="follow_code",
                title="Follow NSPE Code Guidance",
                ethical_justification="Adheres to professional ethical standards"
            )
        ])
    
    def _extract_context_factors(self, case_text: str) -> List[str]:
        """Extract contextual factors that influence the decision."""
        factors = []
        
        # Look for common contextual elements
        context_patterns = {
            "time_pressure": r'\b(?:urgent|deadline|immediate|time\s+pressure)\b',
            "financial_impact": r'\b(?:cost|budget|financial|money|profit)\b',
            "legal_implications": r'\b(?:legal|lawsuit|liability|regulation)\b',
            "public_visibility": r'\b(?:public|media|publicity|reputation)\b'
        }
        
        for factor, pattern in context_patterns.items():
            if re.search(pattern, case_text, re.IGNORECASE):
                factors.append(factor.replace('_', ' ').title())
        
        return factors
    
    def _create_default_decision_point(self, case_text: str) -> EthicalDecisionPoint:
        """Create a default decision point when none are specifically identified."""
        return EthicalDecisionPoint(
            decision_id="general_professional_decision",
            title="Professional Ethical Decision",
            description="General professional ethical decision requiring consideration of NSPE Code principles",
            decision_type=DecisionType.PROFESSIONAL_DUTY,
            ethical_principles=["Hold paramount the safety, health, and welfare of the public"],
            primary_options=[
                DecisionOption(
                    option_id="follow_nspe_code",
                    title="Follow NSPE Code Principles",
                    ethical_justification="Adhere to established professional ethical standards"
                )
            ]
        )
    
    def _extract_facts(self, case_content: Dict[str, Any]) -> List[str]:
        """Extract factual statements from the case."""
        facts_text = self._get_section_text(case_content, 'facts')
        
        if not facts_text:
            return ["Case facts not explicitly available"]
        
        # Split into sentences and clean up
        sentences = re.split(r'[.!?]+', facts_text)
        facts = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        
        return facts[:10]  # Limit to 10 most relevant facts
    
    def _extract_applicable_principles(self, discussion_text: str) -> List[str]:
        """Extract NSPE principles mentioned in discussion."""
        principles = []
        
        for key, principle in self.nspe_principles.items():
            # Look for key phrases from the principle
            principle_words = principle.lower().split()[:3]  # First 3 words
            pattern = r'\b' + r'\s+'.join(principle_words) + r'\b'
            
            if re.search(pattern, discussion_text, re.IGNORECASE):
                principles.append(principle)
        
        # Default principles if none found
        if not principles:
            principles.append(self.nspe_principles['public_safety'])
        
        return principles
    
    def _extract_reasoning_steps(self, discussion_text: str) -> List[ReasoningStep]:
        """Extract reasoning steps from discussion text."""
        if not discussion_text:
            return []
        
        # Simple approach: split into paragraphs and treat as reasoning steps
        paragraphs = [p.strip() for p in discussion_text.split('\n\n') if p.strip()]
        
        steps = []
        for i, paragraph in enumerate(paragraphs[:5]):  # Limit to 5 steps
            step = ReasoningStep(
                step_order=i + 1,
                reasoning_type="ethical_analysis",
                input_elements=["case_facts", "nspe_principles"],
                reasoning_logic=paragraph,
                output_conclusion=f"Conclusion from step {i + 1}",
                confidence=0.7  # Default confidence
            )
            steps.append(step)
        
        return steps
    
    def _extract_predicted_outcome(self, conclusion_text: str) -> str:
        """Extract the predicted/actual outcome from conclusion."""
        if not conclusion_text:
            return "Outcome not specified"
        
        # Take first sentence as the main outcome
        sentences = re.split(r'[.!?]+', conclusion_text)
        return sentences[0].strip() if sentences else conclusion_text[:100]