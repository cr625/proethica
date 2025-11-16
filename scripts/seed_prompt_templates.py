"""
Seed script to migrate LangExtract prompts from ontology to database.

Extracts current prompts from proethica-cases.ttl and creates initial database templates.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to sys.path to import app modules
proethica_root = str(Path(__file__).parent.parent)
sys.path.insert(0, proethica_root)

# Change to proethica directory to ensure proper app context
os.chdir(proethica_root)

from app import create_app
from app.models import db
from app.models.prompt_templates import SectionPromptTemplate
from datetime import datetime


def extract_ontology_prompts():
    """
    Extract current prompts from the ontology configuration individuals.
    
    Returns:
        List of prompt data dictionaries
    """
    
    # Current prompts extracted from proethica-cases.ttl configuration individuals
    ontology_prompts = [
        {
            'section_type': 'FactualSection',
            'ontology_class_uri': 'http://proethica.org/ontology/cases#FactualSection',
            'config_individual_uri': 'http://proethica.org/ontology/cases#factualSectionConfig',
            'domain': 'generic',
            'name': 'Generic Factual Analysis',
            'description': 'Extracts objective factual information and environmental context from case sections',
            'prompt_template': """Extract factual information from this section including key events, dates, people involved, technical details, and objective circumstances. Focus on:
- Timeline of events
- Key stakeholders and their roles  
- Technical or professional details
- Objective circumstances
- Quantifiable information
- Environmental conditions that affect ethical analysis""",
            'variables': {
                'case_domain': 'Professional domain context (e.g., engineering, medical)',
                'stakeholder_types': 'Types of stakeholders relevant to the domain'
            },
            'extraction_targets': 'factual_statements, environmental_conditions, contextual_factors, situational_details',
            'analysis_priority': 1
        },
        {
            'section_type': 'EthicalQuestionSection',
            'ontology_class_uri': 'http://proethica.org/ontology/cases#EthicalQuestionSection',
            'config_individual_uri': 'http://proethica.org/ontology/cases#ethicalQuestionSectionConfig',
            'domain': 'generic',
            'name': 'Generic Ethical Questions Analysis',
            'description': 'Identifies ethical questions, dilemmas, and decision points requiring professional judgment',
            'prompt_template': """Extract ethical questions and dilemmas from this section including:
- Core ethical questions being asked
- Decision points that need resolution
- Conflicting values or principles
- Stakeholder perspectives
- Potential consequences of different actions
- Professional obligations in conflict""",
            'variables': {
                'professional_code': 'Relevant professional code of ethics',
                'stakeholder_groups': 'Key stakeholder groups affected by decisions'
            },
            'extraction_targets': 'ethical_questions, moral_dilemmas, decision_points, conflicting_obligations',
            'analysis_priority': 2
        },
        {
            'section_type': 'AnalysisSection',
            'ontology_class_uri': 'http://proethica.org/ontology/cases#AnalysisSection',
            'config_individual_uri': 'http://proethica.org/ontology/cases#analysisSectionConfig',
            'domain': 'generic',
            'name': 'Generic Ethical Analysis',
            'description': 'Extracts structured reasoning and argumentation bridging principles to concrete obligations',
            'prompt_template': """Extract analytical content from this section including:
- Ethical frameworks being applied
- Arguments and reasoning chains
- Analysis of different perspectives
- Evaluation of consequences
- Professional standards referenced
- Precedent-based reasoning
- Principle applications to specific context""",
            'variables': {
                'ethical_frameworks': 'Relevant ethical frameworks for the domain',
                'precedent_cases': 'Similar cases that might provide precedent'
            },
            'extraction_targets': 'reasoning_chains, precedent_references, principle_applications, duty_weightings',
            'analysis_priority': 3
        },
        {
            'section_type': 'ConclusionSection',
            'ontology_class_uri': 'http://proethica.org/ontology/cases#ConclusionSection',
            'config_individual_uri': 'http://proethica.org/ontology/cases#conclusionSectionConfig',
            'domain': 'generic',
            'name': 'Generic Conclusions Analysis',
            'description': 'Extracts final decisions and recommendations with precedential value',
            'prompt_template': """Extract conclusions and recommendations from this section including:
- Final decisions or recommendations
- Justification for conclusions
- Implementation guidance
- Lessons learned
- Future considerations
- Concrete actions specified
- Precedential value for similar cases""",
            'variables': {
                'implementation_context': 'Context for implementing recommendations',
                'future_scenarios': 'Types of future scenarios this might apply to'
            },
            'extraction_targets': 'final_decisions, concrete_actions, precedential_determinations, obligation_specifications',
            'analysis_priority': 5
        }
    ]
    
    return ontology_prompts


def create_engineering_variants():
    """
    Create engineering-specific variants of the generic prompts.
    
    Returns:
        List of engineering-specific prompt data dictionaries
    """
    
    engineering_prompts = [
        {
            'section_type': 'FactualSection',
            'ontology_class_uri': 'http://proethica.org/ontology/cases#FactualSection',
            'config_individual_uri': None,  # Database-only, no ontology individual
            'domain': 'engineering',
            'name': 'Engineering Factual Analysis',
            'description': 'Extracts engineering-specific factual information including technical standards and regulatory context',
            'prompt_template': """Extract engineering-specific factual information from this section including technical details, standards, and regulatory context. Focus on:

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

Environmental Factors:
- Physical environment and conditions
- Timeline of engineering decisions and implementations
- Resource constraints and limitations
- Risk factors and safety considerations

Extract factual, objective information that establishes the technical and regulatory context for ethical analysis.""",
            'variables': {
                'engineering_discipline': 'Specific engineering discipline (civil, mechanical, electrical, etc.)',
                'applicable_standards': 'Relevant engineering standards and codes',
                'regulatory_context': 'Applicable regulations and oversight bodies',
                'safety_considerations': 'Key safety factors and public welfare concerns'
            },
            'extraction_targets': 'technical_specifications, engineering_standards, regulatory_requirements, safety_factors, professional_obligations, public_safety_implications',
            'analysis_priority': 1
        },
        {
            'section_type': 'EthicalQuestionSection',
            'ontology_class_uri': 'http://proethica.org/ontology/cases#EthicalQuestionSection',
            'config_individual_uri': None,
            'domain': 'engineering',
            'name': 'Engineering Ethics Questions Analysis',
            'description': 'Identifies engineering-specific ethical questions and professional dilemmas',
            'prompt_template': """Extract engineering ethics questions and professional dilemmas from this section, focusing on core engineering obligations and professional responsibilities:

NSPE Fundamental Principles:
- How does this relate to holding paramount the safety, health, and welfare of the public?
- What professional competence and judgment issues are involved?
- How do truthfulness and professional integrity apply?

Professional Obligations:
- What conflicts exist between employer/client loyalty and public welfare?
- Are there competence boundaries being challenged?
- What disclosure obligations exist regarding conflicts of interest?
- How do professional registration and licensure requirements apply?

Stakeholder Conflicts:
- Public vs. private interests
- Short-term economics vs. long-term safety
- Individual professional judgment vs. organizational pressure
- Current regulations vs. emerging best practices

Decision Points:
- What specific professional decisions must be made?
- What are the consequences of different engineering choices?
- How do NSPE Code provisions apply to this situation?
- What precedent does this set for the engineering profession?

Extract questions that require professional engineering judgment and reference specific NSPE Code obligations.""",
            'variables': {
                'nspe_provisions': 'Specific NSPE Code provisions most relevant',
                'engineering_discipline_ethics': 'Discipline-specific ethical considerations',
                'public_safety_scope': 'Scope and nature of public safety implications',
                'professional_relationships': 'Key professional relationships (client, employer, public, colleagues)'
            },
            'extraction_targets': 'nspe_code_conflicts, public_safety_questions, professional_competence_issues, disclosure_obligations, stakeholder_conflicts',
            'analysis_priority': 2
        }
    ]
    
    return engineering_prompts


def seed_prompt_templates():
    """
    Seed the database with initial prompt templates extracted from ontology.
    """
    
    # Set environment variables if not already set
    if 'SQLALCHEMY_DATABASE_URI' not in os.environ:
        os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5432/ai_ethical_dm'
    
    app = create_app()
    
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        
        print("Seeding prompt templates from ontology extraction...")
        
        # Clear existing templates (for clean re-seeding)
        existing_count = SectionPromptTemplate.query.count()
        if existing_count > 0:
            print(f"Found {existing_count} existing templates. Clearing for clean seed...")
            SectionPromptTemplate.query.delete()
            db.session.commit()
        
        # Seed generic templates from ontology
        generic_prompts = extract_ontology_prompts()
        templates_created = 0
        
        for prompt_data in generic_prompts:
            template = SectionPromptTemplate(
                section_type=prompt_data['section_type'],
                ontology_class_uri=prompt_data['ontology_class_uri'],
                domain=prompt_data['domain'],
                name=prompt_data['name'],
                description=prompt_data['description'],
                prompt_template=prompt_data['prompt_template'],
                variables=prompt_data['variables'],
                extraction_targets=prompt_data['extraction_targets'],
                analysis_priority=prompt_data['analysis_priority'],
                created_by='ontology_migration',
                active=True,
                version=1
            )
            db.session.add(template)
            templates_created += 1
            print(f"  Created: {template.domain}:{template.section_type}:{template.name}")
        
        # Seed engineering-specific templates
        engineering_prompts = create_engineering_variants()
        
        for prompt_data in engineering_prompts:
            template = SectionPromptTemplate(
                section_type=prompt_data['section_type'],
                ontology_class_uri=prompt_data['ontology_class_uri'],
                domain=prompt_data['domain'],
                name=prompt_data['name'],
                description=prompt_data['description'],
                prompt_template=prompt_data['prompt_template'],
                variables=prompt_data['variables'],
                extraction_targets=prompt_data['extraction_targets'],
                analysis_priority=prompt_data['analysis_priority'],
                created_by='engineering_specialization',
                active=True,
                version=1
            )
            db.session.add(template)
            templates_created += 1
            print(f"  Created: {template.domain}:{template.section_type}:{template.name}")
        
        # Commit all templates
        db.session.commit()
        
        print(f"\nSuccessfully seeded {templates_created} prompt templates!")
        print("Migration complete - prompts are now managed in the database.")
        
        # Show summary
        generic_count = SectionPromptTemplate.query.filter_by(domain='generic').count()
        engineering_count = SectionPromptTemplate.query.filter_by(domain='engineering').count()
        
        print(f"\nTemplate Summary:")
        print(f"  Generic templates: {generic_count}")
        print(f"  Engineering templates: {engineering_count}")
        print(f"  Total templates: {generic_count + engineering_count}")


if __name__ == '__main__':
    seed_prompt_templates()