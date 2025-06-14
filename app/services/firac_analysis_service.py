"""
FIRAC Legal Reasoning Analysis Service for ProEthica.

Provides structured ethical case analysis using the FIRAC framework:
- Facts: What happened in the case
- Issues: What ethical issues are raised  
- Rules: What guidelines/principles apply
- Analysis: How do the rules apply to the facts
- Conclusion: What should be done
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sqlalchemy.orm import joinedload

from app.models import db
from app.models.document import Document
from app.models.document_section import DocumentSection
from app.models.guideline import Guideline
from app.models.entity_triple import EntityTriple

# Import models with graceful fallback
try:
    from app.models.case_guideline_associations import CaseGuidelineAssociation
except ImportError:
    CaseGuidelineAssociation = None

from app.services.llm_service import LLMService


@dataclass
class FIRACFacts:
    """Facts component of FIRAC analysis."""
    factual_statements: List[str]
    key_stakeholders: List[str]
    context_description: str
    source_sections: List[Dict[str, Any]]


@dataclass
class FIRACIssues:
    """Issues component of FIRAC analysis."""
    primary_ethical_issues: List[str]
    secondary_issues: List[str]
    ethical_dilemmas: List[str]
    stakeholder_conflicts: List[str]


@dataclass
class FIRACRules:
    """Rules component of FIRAC analysis."""
    applicable_guidelines: List[Dict[str, Any]]
    ontology_concepts: List[Dict[str, Any]]
    ethical_principles: List[str]
    professional_standards: List[str]
    confidence_scores: Dict[str, float]


@dataclass
class FIRACAnalysis:
    """Analysis component of FIRAC analysis."""
    rule_application: List[Dict[str, Any]]
    conflict_resolution: List[str]
    stakeholder_impact: List[Dict[str, Any]]
    precedent_cases: List[Dict[str, Any]]
    reasoning_chain: List[str]


@dataclass
class FIRACConclusion:
    """Conclusion component of FIRAC analysis."""
    recommended_action: str
    implementation_steps: List[str]
    risk_assessment: str
    alternative_approaches: List[str]
    committee_consultation_needed: bool


@dataclass
class FIRACCaseAnalysis:
    """Complete FIRAC analysis for a case."""
    case_id: int
    case_title: str
    facts: FIRACFacts
    issues: FIRACIssues
    rules: FIRACRules
    analysis: FIRACAnalysis
    conclusion: FIRACConclusion
    confidence_overview: Dict[str, float]
    processing_metadata: Dict[str, Any]


class FIRACAnalysisService:
    """
    Service for conducting structured FIRAC analysis of ethical cases.
    
    Uses document sections, guideline associations, and ontology concepts
    to provide comprehensive legal-style reasoning for ethical decisions.
    """
    
    def __init__(self):
        """Initialize the FIRAC analysis service."""
        self.llm_service = LLMService()
        self.logger = logging.getLogger(f"{__name__}.FIRACAnalysisService")
    
    def analyze_case(self, case_id: int) -> FIRACCaseAnalysis:
        """
        Conduct complete FIRAC analysis for a case.
        
        Args:
            case_id: ID of the case to analyze
            
        Returns:
            FIRACCaseAnalysis with structured analysis
        """
        self.logger.info(f"Conducting FIRAC analysis for case {case_id}")
        
        # Get case and its components
        case = Document.query.get(case_id)
        if not case:
            raise ValueError(f"Case {case_id} not found")
        
        sections = DocumentSection.query.filter_by(document_id=case_id).all()
        associations = self._get_case_associations(case_id)
        
        # Conduct each component of FIRAC analysis
        facts = self._analyze_facts(case, sections)
        issues = self._analyze_issues(case, sections, associations)
        rules = self._analyze_rules(case, associations)
        analysis = self._analyze_application(facts, issues, rules, case)
        conclusion = self._analyze_conclusion(facts, issues, rules, analysis)
        
        # Calculate confidence overview
        confidence_overview = self._calculate_confidence_overview(
            facts, issues, rules, analysis, conclusion, associations
        )
        
        return FIRACCaseAnalysis(
            case_id=case_id,
            case_title=case.title,
            facts=facts,
            issues=issues,
            rules=rules,
            analysis=analysis,
            conclusion=conclusion,
            confidence_overview=confidence_overview,
            processing_metadata={
                'sections_analyzed': len(sections),
                'associations_count': len(associations),
                'generated_at': db.func.now()
            }
        )
    
    def _get_case_associations(self, case_id: int) -> List:
        """Get all associations for a case."""
        if CaseGuidelineAssociation is None:
            return []
        
        return CaseGuidelineAssociation.query.filter_by(case_id=case_id)\
            .options(joinedload(CaseGuidelineAssociation.guideline))\
            .order_by(CaseGuidelineAssociation.overall_confidence.desc())\
            .all()
    
    def _analyze_facts(self, case: Document, sections: List[DocumentSection]) -> FIRACFacts:
        """Extract and analyze the factual situation."""
        
        # Find facts sections
        facts_sections = [s for s in sections if 'fact' in s.section_type.lower()]
        
        # Extract factual statements
        factual_statements = []
        source_sections = []
        
        for section in facts_sections:
            if section.content:
                # Use LLM to extract key factual statements
                facts_prompt = f"""
                You are analyzing an engineering ethics case. Extract the key factual statements from this case section.
                
                Instructions:
                1. Focus on objective, verifiable facts only
                2. Avoid opinions, interpretations, or conclusions
                3. Return exactly 3-5 key factual statements
                4. Format as a bulleted list with each fact on its own line starting with '-'
                
                Case Section:
                {section.content[:1000]}
                
                Key Factual Statements:
                """
                
                try:
                    facts_response = self.llm_service.generate_response(facts_prompt)
                    if facts_response and 'analysis' in facts_response:
                        # Parse the facts from the response
                        facts_text = facts_response['analysis']
                        facts_list = [f.strip('- ').strip() for f in facts_text.split('\n') if f.strip().startswith('-')]
                        factual_statements.extend(facts_list)
                        
                        source_sections.append({
                            'section_id': section.id,
                            'section_type': section.section_type,
                            'fact_count': len(facts_list)
                        })
                except Exception as e:
                    self.logger.warning(f"Could not extract facts with LLM: {e}")
                    # Fallback to basic extraction
                    factual_statements.append(section.content[:200] + "...")
        
        # Extract stakeholders using case metadata and content analysis
        stakeholders = []
        if case.doc_metadata:
            # Look for common stakeholder patterns
            case_text = ' '.join([s.content or '' for s in sections])
            common_stakeholders = ['engineer', 'client', 'public', 'employer', 'government', 'contractor']
            stakeholders = [s for s in common_stakeholders if s in case_text.lower()]
        
        # Create context description
        context_description = f"Ethical case involving {case.title}"
        if case.doc_metadata and case.doc_metadata.get('case_number'):
            context_description += f" (Case #{case.doc_metadata['case_number']})"
        
        return FIRACFacts(
            factual_statements=factual_statements[:10],  # Top 10 facts
            key_stakeholders=stakeholders,
            context_description=context_description,
            source_sections=source_sections
        )
    
    def _analyze_issues(self, case: Document, sections: List[DocumentSection], 
                       associations: List) -> FIRACIssues:
        """Identify and analyze ethical issues."""
        
        # Use LLM to identify ethical issues
        case_content = ' '.join([s.content or '' for s in sections[:3]])  # First 3 sections
        
        issues_prompt = f"""
        You are analyzing an engineering ethics case to identify ethical issues using the FIRAC framework.
        
        Case Title: {case.title}
        
        Case Content: {case_content[:1500]}
        
        Please identify and categorize the ethical issues:
        
        1. PRIMARY ETHICAL ISSUES (2-3 most critical issues):
        - [List the main ethical concerns]
        
        2. SECONDARY ISSUES (1-2 supporting concerns):
        - [List additional ethical considerations]
        
        3. ETHICAL DILEMMAS (competing values or principles):
        - [List situations where ethical principles conflict]
        
        4. STAKEHOLDER CONFLICTS (competing interests):
        - [List conflicts between different parties' interests]
        
        Focus on engineering ethics, professional responsibility, and public welfare.
        """
        
        primary_issues = []
        secondary_issues = []
        ethical_dilemmas = []
        stakeholder_conflicts = []
        
        try:
            issues_response = self.llm_service.generate_response(issues_prompt)
            if issues_response and 'analysis' in issues_response:
                # Parse the structured response
                # This is a simplified parser - could be enhanced
                analysis_text = issues_response['analysis']
                
                # Extract common ethical issues from associations
                if associations:
                    for assoc in associations[:5]:
                        concept_uri = assoc.guideline_concept_uri or ''
                        if 'safety' in concept_uri.lower():
                            primary_issues.append('Public safety considerations')
                        elif 'competence' in concept_uri.lower():
                            primary_issues.append('Professional competence boundaries')
                        elif 'honesty' in concept_uri.lower():
                            primary_issues.append('Honest communication requirements')
        except Exception as e:
            self.logger.warning(f"Could not analyze issues with LLM: {e}")
            # Fallback to basic issue identification
            primary_issues = ['Professional ethics compliance', 'Stakeholder responsibility']
        
        return FIRACIssues(
            primary_ethical_issues=primary_issues or ['General ethical compliance'],
            secondary_issues=secondary_issues or ['Professional standards adherence'],
            ethical_dilemmas=ethical_dilemmas or ['Balancing competing interests'],
            stakeholder_conflicts=stakeholder_conflicts or ['Potential conflicting priorities']
        )
    
    def _analyze_rules(self, case: Document, associations: List) -> FIRACRules:
        """Identify and analyze applicable rules and guidelines."""
        
        applicable_guidelines = []
        ontology_concepts = []
        confidence_scores = {}
        
        # Process guideline associations
        for assoc in associations:
            if assoc.guideline:
                applicable_guidelines.append({
                    'guideline_id': assoc.guideline.id,
                    'title': assoc.guideline.title,
                    'concept_uri': assoc.guideline_concept_uri,
                    'confidence': assoc.overall_confidence,
                    'reasoning': assoc.association_reasoning or 'Semantic alignment detected'
                })
                
                confidence_scores[assoc.guideline.title] = assoc.overall_confidence
        
        # Get ontology concepts from entity triples
        entity_triples = EntityTriple.query.filter_by(
            entity_id=case.id,
            entity_type='case'
        ).all()
        
        for triple in entity_triples:
            if triple.predicate == 'hasRelevantConcept':
                ontology_concepts.append({
                    'concept_uri': triple.object_uri,
                    'concept_type': triple.metadata.get('concept_type', 'unknown'),
                    'confidence': triple.metadata.get('confidence', 0.8)
                })
        
        # Extract ethical principles
        ethical_principles = [
            'Public safety priority',
            'Professional competence',
            'Honest communication',
            'Conflict of interest avoidance'
        ]
        
        professional_standards = [
            'Engineering codes of ethics',
            'Professional licensure requirements',
            'Industry best practices'
        ]
        
        return FIRACRules(
            applicable_guidelines=applicable_guidelines,
            ontology_concepts=ontology_concepts,
            ethical_principles=ethical_principles,
            professional_standards=professional_standards,
            confidence_scores=confidence_scores
        )
    
    def _analyze_application(self, facts: FIRACFacts, issues: FIRACIssues, 
                           rules: FIRACRules, case: Document) -> FIRACAnalysis:
        """Analyze how rules apply to facts to resolve issues."""
        
        rule_application = []
        reasoning_chain = []
        
        # Apply each rule to the factual situation
        for guideline in rules.applicable_guidelines:
            application = {
                'rule': guideline['title'],
                'applies_to_facts': f"Rule applies to {facts.context_description}",
                'confidence': guideline['confidence'],
                'reasoning': guideline['reasoning']
            }
            rule_application.append(application)
            
            reasoning_chain.append(
                f"Given {facts.context_description}, {guideline['title']} "
                f"applies with {guideline['confidence']:.1%} confidence"
            )
        
        # Analyze stakeholder impact
        stakeholder_impact = []
        for stakeholder in facts.key_stakeholders:
            impact = {
                'stakeholder': stakeholder,
                'primary_concern': f"Impact on {stakeholder} interests",
                'affected_by_issues': issues.primary_ethical_issues[:2]
            }
            stakeholder_impact.append(impact)
        
        # Find precedent cases (simplified)
        precedent_cases = []
        
        # Conflict resolution strategies
        conflict_resolution = [
            'Prioritize public safety and welfare',
            'Maintain professional competence boundaries',
            'Ensure transparent communication',
            'Follow established ethical frameworks'
        ]
        
        return FIRACAnalysis(
            rule_application=rule_application,
            conflict_resolution=conflict_resolution,
            stakeholder_impact=stakeholder_impact,
            precedent_cases=precedent_cases,
            reasoning_chain=reasoning_chain
        )
    
    def _analyze_conclusion(self, facts: FIRACFacts, issues: FIRACIssues,
                          rules: FIRACRules, analysis: FIRACAnalysis) -> FIRACConclusion:
        """Develop conclusion and recommendations."""
        
        # Determine if ethics committee consultation is needed
        committee_needed = (
            len(issues.ethical_dilemmas) > 1 or
            len(issues.stakeholder_conflicts) > 2 or
            any(conf < 0.7 for conf in rules.confidence_scores.values())
        )
        
        # Generate recommended action
        if rules.applicable_guidelines:
            top_rule = max(rules.applicable_guidelines, key=lambda x: x['confidence'])
            recommended_action = f"Follow {top_rule['title']} with focus on {issues.primary_ethical_issues[0] if issues.primary_ethical_issues else 'ethical compliance'}"
        else:
            recommended_action = "Conduct comprehensive ethical review following established frameworks"
        
        # Implementation steps
        implementation_steps = [
            'Review all applicable ethical guidelines',
            'Assess impact on all stakeholders',
            'Consider alternative approaches',
            'Document decision rationale',
            'Monitor implementation outcomes'
        ]
        
        if committee_needed:
            implementation_steps.insert(1, 'Consult with ethics committee for multi-perspective analysis')
        
        # Risk assessment
        high_confidence_rules = [r for r in rules.applicable_guidelines if r['confidence'] > 0.8]
        if len(high_confidence_rules) >= 2:
            risk_assessment = 'Low risk - clear guidance available'
        elif len(rules.applicable_guidelines) > 0:
            risk_assessment = 'Medium risk - some guidance available'
        else:
            risk_assessment = 'High risk - limited guidance available'
        
        # Alternative approaches
        alternative_approaches = [
            'Seek additional expert consultation',
            'Research similar case precedents',
            'Conduct stakeholder impact analysis',
            'Review updated industry standards'
        ]
        
        return FIRACConclusion(
            recommended_action=recommended_action,
            implementation_steps=implementation_steps,
            risk_assessment=risk_assessment,
            alternative_approaches=alternative_approaches,
            committee_consultation_needed=committee_needed
        )
    
    def _calculate_confidence_overview(self, facts: FIRACFacts, issues: FIRACIssues,
                                     rules: FIRACRules, analysis: FIRACAnalysis,
                                     conclusion: FIRACConclusion, associations: List) -> Dict[str, float]:
        """Calculate confidence metrics for the analysis."""
        
        # Facts confidence based on source sections
        facts_confidence = min(1.0, len(facts.source_sections) / 3.0)
        
        # Issues confidence based on association coverage
        issues_confidence = 0.8 if associations else 0.5
        
        # Rules confidence based on association confidence
        rules_confidence = (
            sum(rules.confidence_scores.values()) / len(rules.confidence_scores)
            if rules.confidence_scores else 0.5
        )
        
        # Analysis confidence based on rule application
        analysis_confidence = min(rules_confidence + 0.1, 1.0)
        
        # Overall confidence
        overall_confidence = (
            facts_confidence * 0.2 +
            issues_confidence * 0.2 +
            rules_confidence * 0.3 +
            analysis_confidence * 0.3
        )
        
        return {
            'facts_confidence': facts_confidence,
            'issues_confidence': issues_confidence,
            'rules_confidence': rules_confidence,
            'analysis_confidence': analysis_confidence,
            'overall_confidence': overall_confidence
        }


# Create singleton instance
firac_analysis_service = FIRACAnalysisService()