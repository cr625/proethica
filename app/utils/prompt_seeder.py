"""
Utility to seed prompt templates into database on application startup.

This ensures the database has the necessary prompt templates when transitioning
from ontology-based to database-based prompt management.
"""

import logging
from typing import List, Dict, Any
from app.models import db
from app.models.prompt_templates import SectionPromptTemplate

logger = logging.getLogger(__name__)


def seed_initial_prompt_templates() -> bool:
    """
    Seed initial prompt templates if they don't exist.
    
    Returns:
        True if seeding was successful, False otherwise
    """
    
    try:
        # Check if templates already exist
        existing_count = SectionPromptTemplate.query.count()
        if existing_count > 0:
            logger.info(f"Prompt templates already exist ({existing_count} found), skipping seed")
            return True
        
        logger.info("Seeding initial prompt templates...")
        
        # Define initial templates based on ontology extraction
        initial_templates = _get_initial_templates()
        
        templates_created = 0
        for template_data in initial_templates:
            template = SectionPromptTemplate(
                section_type=template_data['section_type'],
                ontology_class_uri=template_data['ontology_class_uri'],
                domain=template_data['domain'],
                name=template_data['name'],
                description=template_data['description'],
                prompt_template=template_data['prompt_template'],
                variables=template_data['variables'],
                extraction_targets=template_data['extraction_targets'],
                analysis_priority=template_data['analysis_priority'],
                created_by='auto_seed',
                active=True,
                version=1
            )
            db.session.add(template)
            templates_created += 1
        
        db.session.commit()
        logger.info(f"Successfully seeded {templates_created} prompt templates")
        return True
        
    except Exception as e:
        logger.error(f"Error seeding prompt templates: {e}")
        db.session.rollback()
        return False


def _get_initial_templates() -> List[Dict[str, Any]]:
    """
    Get the initial template definitions extracted from the ontology.
    
    Returns:
        List of template data dictionaries
    """
    
    return [
        {
            'section_type': 'FactualSection',
            'ontology_class_uri': 'http://proethica.org/ontology/cases#FactualSection',
            'domain': 'generic',
            'name': 'Generic Factual Analysis',
            'description': 'Extracts objective factual information and environmental context',
            'prompt_template': """Extract factual information from this section including key events, dates, people involved, technical details, and objective circumstances. Focus on:
- Timeline of events
- Key stakeholders and their roles  
- Technical or professional details
- Objective circumstances
- Quantifiable information
- Environmental conditions that affect ethical analysis""",
            'variables': {},
            'extraction_targets': 'factual_statements, environmental_conditions, contextual_factors, situational_details',
            'analysis_priority': 1
        },
        {
            'section_type': 'EthicalQuestionSection',
            'ontology_class_uri': 'http://proethica.org/ontology/cases#EthicalQuestionSection',
            'domain': 'generic',
            'name': 'Generic Ethical Questions Analysis',
            'description': 'Identifies ethical questions, dilemmas, and decision points',
            'prompt_template': """Extract ethical questions and dilemmas from this section including:
- Core ethical questions being asked
- Decision points that need resolution
- Conflicting values or principles
- Stakeholder perspectives
- Potential consequences of different actions
- Professional obligations in conflict""",
            'variables': {},
            'extraction_targets': 'ethical_questions, moral_dilemmas, decision_points, conflicting_obligations',
            'analysis_priority': 2
        },
        {
            'section_type': 'AnalysisSection',
            'ontology_class_uri': 'http://proethica.org/ontology/cases#AnalysisSection',
            'domain': 'generic',
            'name': 'Generic Ethical Analysis',
            'description': 'Extracts structured reasoning and argumentation',
            'prompt_template': """Extract analytical content from this section including:
- Ethical frameworks being applied
- Arguments and reasoning chains
- Analysis of different perspectives
- Evaluation of consequences
- Professional standards referenced
- Precedent-based reasoning
- Principle applications to specific context""",
            'variables': {},
            'extraction_targets': 'reasoning_chains, precedent_references, principle_applications, duty_weightings',
            'analysis_priority': 3
        },
        {
            'section_type': 'ConclusionSection',
            'ontology_class_uri': 'http://proethica.org/ontology/cases#ConclusionSection',
            'domain': 'generic',
            'name': 'Generic Conclusions Analysis',
            'description': 'Extracts final decisions and recommendations',
            'prompt_template': """Extract conclusions and recommendations from this section including:
- Final decisions or recommendations
- Justification for conclusions
- Implementation guidance
- Lessons learned
- Future considerations
- Concrete actions specified
- Precedential value for similar cases""",
            'variables': {},
            'extraction_targets': 'final_decisions, concrete_actions, precedential_determinations, obligation_specifications',
            'analysis_priority': 5
        },
        {
            'section_type': 'FactualSection',
            'ontology_class_uri': 'http://proethica.org/ontology/cases#FactualSection',
            'domain': 'engineering',
            'name': 'Engineering Factual Analysis',
            'description': 'Engineering-specific factual extraction with technical standards focus',
            'prompt_template': """Extract engineering-specific factual information including technical standards and regulatory context:

Technical Information:
- Engineering standards referenced (ASME, IEEE, ASTM, etc.)
- Technical specifications and design parameters
- Safety factors and margins
- Material properties and environmental conditions
- Calculations, measurements, and quantifiable data

Professional Context:
- Professional licensure and registration requirements
- Regulatory compliance status (OSHA, EPA, building codes, etc.)
- Professional society guidance (NSPE, ASME, IEEE)
- Industry best practices and standards

Stakeholder Analysis:
- Licensed professional engineers involved
- Public safety implications and affected populations  
- Client/employer relationships and obligations
- Regulatory bodies and oversight agencies

Extract factual, objective information establishing technical and regulatory context.""",
            'variables': {},
            'extraction_targets': 'technical_specifications, engineering_standards, regulatory_requirements, safety_factors, professional_obligations, public_safety_implications',
            'analysis_priority': 1
        }
    ]