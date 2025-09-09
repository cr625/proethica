"""
Advanced Prompt Builder Routes with Domain-Specific Organization and Ontology Integration.

Provides comprehensive web-based interface for managing prompt templates across domains
with syntax highlighting, template variables, and ontology-driven case structures.
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from app.models import db
from app.models.prompt_templates import SectionPromptTemplate, SectionPromptInstance, PromptTemplateVersion, LangExtractExample, LangExtractExampleExtraction
from sqlalchemy import func, text
import requests
import logging
import json
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Create the prompt builder blueprint
prompt_builder_bp = Blueprint('prompt_builder', __name__, url_prefix='/prompt-builder')


@prompt_builder_bp.route('/')
@login_required
def index():
    """
    Main prompt builder dashboard with domain organization.
    """
    try:
        # Get all worlds/domains from the database
        worlds = db.session.execute(text("SELECT name, description FROM worlds ORDER BY name")).fetchall()
        
        # Get template statistics by domain
        template_stats = db.session.execute(text("""
            SELECT 
                domain,
                section_type,
                COUNT(*) as template_count,
                SUM(usage_count) as total_usage,
                AVG(avg_performance_score) as avg_performance
            FROM section_prompt_templates 
            WHERE active = true 
            GROUP BY domain, section_type 
            ORDER BY domain, section_type
        """)).fetchall()
        
        # Get section types available from ontology
        section_types = get_ontology_section_types()
        
        # Organize data for frontend
        domain_data = {}
        for world in worlds:
            domain_key = world.name.lower()
            domain_data[domain_key] = {
                'name': world.name,
                'description': world.description,
                'templates': {},
                'total_templates': 0,
                'total_usage': 0
            }
        
        # Add generic domain if not exists
        if 'generic' not in domain_data:
            domain_data['generic'] = {
                'name': 'Generic',
                'description': 'Universal templates applicable across all domains',
                'templates': {},
                'total_templates': 0,
                'total_usage': 0
            }
        
        # Populate template statistics
        for stat in template_stats:
            domain_key = stat.domain.lower()
            if domain_key not in domain_data:
                domain_data[domain_key] = {
                    'name': stat.domain.title(),
                    'description': f'{stat.domain.title()} domain templates',
                    'templates': {},
                    'total_templates': 0,
                    'total_usage': 0
                }
            
            domain_data[domain_key]['templates'][stat.section_type] = {
                'count': stat.template_count,
                'usage': stat.total_usage or 0,
                'performance': round(stat.avg_performance, 2) if stat.avg_performance else None
            }
            domain_data[domain_key]['total_templates'] += stat.template_count
            domain_data[domain_key]['total_usage'] += stat.total_usage or 0
        
        return render_template('prompt_builder/index.html', 
                             domain_data=domain_data,
                             section_types=section_types,
                             worlds=worlds)
    
    except Exception as e:
        logger.error(f"Error loading prompt builder: {e}")
        flash(f'Error loading prompt builder: {e}', 'error')
        return render_template('prompt_builder/index.html', 
                             domain_data={}, 
                             section_types=[],
                             worlds=[])


@prompt_builder_bp.route('/domain/<domain_name>')
@login_required
def domain_templates(domain_name):
    """
    View and manage templates for a specific domain.
    """
    try:
        # Get templates for this domain
        templates = SectionPromptTemplate.query.filter_by(
            domain=domain_name,
            active=True
        ).order_by(SectionPromptTemplate.section_type, SectionPromptTemplate.analysis_priority).all()
        
        # Get domain info from worlds
        world_info = db.session.execute(text(
            "SELECT name, description FROM worlds WHERE LOWER(name) = LOWER(:domain)"
        ), {'domain': domain_name}).fetchone()
        
        # Get section types from ontology for this domain
        section_types = get_ontology_section_types()
        domain_section_types = get_domain_specific_section_types(domain_name)
        
        return render_template('prompt_builder/domain.html',
                             domain_name=domain_name,
                             world_info=world_info,
                             templates=templates,
                             section_types=section_types,
                             domain_section_types=domain_section_types)
    
    except Exception as e:
        logger.error(f"Error loading domain {domain_name}: {e}")
        flash(f'Error loading domain: {e}', 'error')
        return redirect(url_for('prompt_builder.index'))


@prompt_builder_bp.route('/editor')
@prompt_builder_bp.route('/editor/<int:template_id>')
@login_required
def editor(template_id=None):
    """
    Advanced prompt template editor with syntax highlighting.
    """
    try:
        logger.info(f"Editor function called with template_id: {template_id}")
        template = None
        if template_id:
            logger.info(f"Loading template with ID: {template_id}")
            template = SectionPromptTemplate.query.get_or_404(template_id)
            logger.info(f"Template loaded successfully: {template.name if template else None}")
        
        # Get available domains and section types
        logger.info("Getting domains...")
        domains = ['generic'] + [w.name.lower() for w in db.session.execute(text("SELECT name FROM worlds")).fetchall()]
        logger.info(f"Domains loaded: {domains}")
        
        logger.info("Getting section types...")
        section_types = get_ontology_section_types()
        logger.info(f"Section types loaded: {len(section_types) if section_types else 0}")
        
        # Get template variables schema for autocomplete
        logger.info("Getting variable schemas...")
        variable_schemas = get_template_variable_schemas()
        logger.info("Variable schemas loaded successfully")
        
        return render_template('prompt_builder/editor.html',
                             template=template,
                             domains=domains,
                             section_types=section_types,
                             variable_schemas=variable_schemas)
    
    except Exception as e:
        logger.error(f"Error loading editor: {e}")
        flash(f'Error loading editor: {e}', 'error')
        return redirect(url_for('prompt_builder.index'))


@prompt_builder_bp.route('/api/template', methods=['POST'])
@login_required
def save_template():
    """
    Save or update a prompt template.
    """
    try:
        data = request.get_json()
        
        template_id = data.get('template_id')
        if template_id:
            # Update existing template
            template = SectionPromptTemplate.query.get_or_404(template_id)
            
            # Create version history
            version = PromptTemplateVersion(
                template_id=template.id,
                version_number=template.version,
                prompt_template=template.prompt_template,
                variables=template.variables,
                extraction_targets=template.extraction_targets,
                analysis_priority=template.analysis_priority,
                change_description=data.get('change_description', 'Updated via web editor'),
                changed_by=data.get('changed_by', 'web_editor')
            )
            db.session.add(version)
            
            # Update template
            template.prompt_template = data['prompt_template']
            template.variables = data.get('variables', {})
            template.extraction_targets = data.get('extraction_targets', '')
            template.analysis_priority = data.get('analysis_priority', 1)
            template.description = data.get('description', '')
            template.version += 1
        else:
            # Create new template
            template = SectionPromptTemplate(
                section_type=data['section_type'],
                ontology_class_uri=f"http://proethica.org/ontology/cases#{data['section_type']}",
                domain=data['domain'],
                name=data['name'],
                description=data.get('description', ''),
                prompt_template=data['prompt_template'],
                variables=data.get('variables', {}),
                extraction_targets=data.get('extraction_targets', ''),
                analysis_priority=data.get('analysis_priority', 1),
                created_by='web_editor',
                active=True,
                version=1
            )
            db.session.add(template)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'template_id': template.id,
            'message': 'Template saved successfully'
        })
    
    except Exception as e:
        logger.error(f"Error saving template: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@prompt_builder_bp.route('/api/template/<int:template_id>/preview', methods=['POST'])
@login_required
def preview_template(template_id):
    """
    Preview a template with sample variables.
    """
    try:
        data = request.get_json()
        template_text = data['template']
        variables = data.get('variables', {})
        
        # Render template with Jinja2
        from jinja2 import Template
        jinja_template = Template(template_text)
        rendered = jinja_template.render(**variables)
        
        return jsonify({
            'success': True,
            'rendered_template': rendered,
            'variables_used': list(variables.keys())
        })
    
    except Exception as e:
        logger.error(f"Error previewing template: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@prompt_builder_bp.route('/api/section-types/<domain_name>')
@login_required
def get_domain_section_types_api(domain_name):
    """
    Get section types available for a specific domain from ontology.
    """
    try:
        section_types = get_domain_specific_section_types(domain_name)
        return jsonify({
            'success': True,
            'section_types': section_types
        })
    
    except Exception as e:
        logger.error(f"Error getting section types for {domain_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@prompt_builder_bp.route('/api/template/<int:template_id>/performance')
@login_required
def get_template_performance(template_id):
    """
    Get performance analytics for a template.
    """
    try:
        # Get usage statistics
        stats = db.session.execute(text("""
            SELECT 
                COUNT(*) as total_uses,
                AVG(performance_score) as avg_performance,
                AVG(processing_time_ms) as avg_processing_time,
                AVG(concepts_extracted) as avg_concepts,
                SUM(CASE WHEN analysis_successful THEN 1 ELSE 0 END) as successful_analyses
            FROM section_prompt_instances 
            WHERE template_id = :template_id
        """), {'template_id': template_id}).fetchone()
        
        # Get recent usage
        recent_uses = db.session.execute(text("""
            SELECT 
                case_id,
                section_title,
                performance_score,
                concepts_extracted,
                created_at
            FROM section_prompt_instances 
            WHERE template_id = :template_id 
            ORDER BY created_at DESC 
            LIMIT 10
        """), {'template_id': template_id}).fetchall()
        
        return jsonify({
            'success': True,
            'statistics': {
                'total_uses': stats.total_uses or 0,
                'avg_performance': round(stats.avg_performance, 2) if stats.avg_performance else None,
                'avg_processing_time': round(stats.avg_processing_time, 1) if stats.avg_processing_time else None,
                'avg_concepts': round(stats.avg_concepts, 1) if stats.avg_concepts else None,
                'success_rate': round((stats.successful_analyses / stats.total_uses) * 100, 1) if stats.total_uses else 0
            },
            'recent_uses': [
                {
                    'case_id': use.case_id,
                    'section_title': use.section_title,
                    'performance_score': use.performance_score,
                    'concepts_extracted': use.concepts_extracted,
                    'created_at': use.created_at.isoformat() if use.created_at else None
                } for use in recent_uses
            ]
        })
    
    except Exception as e:
        logger.error(f"Error getting template performance: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def get_ontology_section_types() -> List[Dict[str, str]]:
    """
    Get section types from the ontology via SPARQL.
    Falls back to hardcoded types if SPARQL fails.
    """
    try:
        query = "PREFIX cases: <http://proethica.org/ontology/cases#> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> PREFIX skos: <http://www.w3.org/2004/02/skos/core#> SELECT DISTINCT ?sectionType ?label ?definition WHERE { ?sectionType rdfs:subClassOf cases:SectionType . OPTIONAL { ?sectionType rdfs:label ?label . } OPTIONAL { ?sectionType skos:definition ?definition . } FILTER(?sectionType != cases:SectionType) } ORDER BY ?sectionType"
        
        response = requests.post(
            "http://localhost:8082/sparql",
            json={"query": query},
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        if response.status_code == 200:
            logger.info(f"SPARQL response length: {len(response.text)}")
            logger.info(f"SPARQL response preview: {response.text[:500]}...")
            results = response.json()
            section_types = []
            
            for binding in results.get('results', {}).get('bindings', []):
                section_type_uri = binding['sectionType']['value']
                section_type_name = section_type_uri.split('#')[-1]
                
                section_types.append({
                    'name': section_type_name,
                    'label': binding['label']['value'],
                    'definition': binding.get('definition', {}).get('value', ''),
                    'uri': section_type_uri
                })
            
            return section_types
        
        # If SPARQL failed, fall back to hardcoded section types
        logger.warning(f"SPARQL query failed with status {response.status_code}, using fallback")
        return get_fallback_section_types()
    
    except Exception as e:
        logger.error(f"Error getting ontology section types: {e}")
        # Return hardcoded fallback section types
        return get_fallback_section_types()


def get_fallback_section_types() -> List[Dict[str, str]]:
    """
    Fallback section types when SPARQL is unavailable.
    """
    return [
        {
            'name': 'FactualSection',
            'label': 'Factual Section',
            'definition': 'Section containing factual information and background details',
            'uri': 'http://proethica.org/ontology/cases#FactualSection'
        },
        {
            'name': 'EthicalQuestionSection',
            'label': 'Ethical Question Section', 
            'definition': 'Section containing ethical questions and dilemmas',
            'uri': 'http://proethica.org/ontology/cases#EthicalQuestionSection'
        },
        {
            'name': 'AnalysisSection',
            'label': 'Analysis Section',
            'definition': 'Section containing ethical analysis and reasoning',
            'uri': 'http://proethica.org/ontology/cases#AnalysisSection'
        },
        {
            'name': 'ConclusionSection',
            'label': 'Conclusion Section',
            'definition': 'Section containing conclusions and recommendations',
            'uri': 'http://proethica.org/ontology/cases#ConclusionSection'
        }
    ]


def get_domain_specific_section_types(domain_name: str) -> List[Dict[str, str]]:
    """
    Get section types specific to a domain, including domain-specific extensions.
    """
    # Start with generic section types
    section_types = get_ontology_section_types()
    
    # Add domain-specific logic here
    if domain_name.lower() == 'engineering':
        # Engineering might have additional section types
        section_types.extend([
            {
                'name': 'CodeReferenceSection',
                'label': 'Code Reference Section',
                'definition': 'References to engineering codes and standards',
                'uri': 'http://proethica.org/ontology/cases#CodeReferenceSection'
            },
            {
                'name': 'SafetyAnalysisSection', 
                'label': 'Safety Analysis Section',
                'definition': 'Analysis of safety implications and risk factors',
                'uri': 'http://proethica.org/ontology/cases#SafetyAnalysisSection'
            }
        ])
    
    return section_types


@prompt_builder_bp.route('/examples')
@login_required
def examples_index():
    """
    LangExtract examples management dashboard.
    """
    try:
        # Get example statistics by domain and type
        example_stats = db.session.execute(text("""
            SELECT 
                domain,
                example_type,
                section_type,
                COUNT(*) as example_count,
                SUM(usage_count) as total_usage,
                AVG(effectiveness_score) as avg_effectiveness
            FROM langextract_examples 
            WHERE active = true 
            GROUP BY domain, example_type, section_type 
            ORDER BY domain, example_type
        """)).fetchall()
        
        # Get all domains
        domains = ['generic'] + [w.name.lower() for w in db.session.execute(text("SELECT name FROM worlds")).fetchall()]
        
        # Organize data for frontend
        domain_data = {}
        for domain in domains:
            domain_data[domain] = {
                'name': domain.title(),
                'examples': {},
                'total_examples': 0,
                'total_usage': 0
            }
        
        # Populate example statistics
        for stat in example_stats:
            domain_key = stat.domain.lower()
            if domain_key not in domain_data:
                domain_data[domain_key] = {
                    'name': stat.domain.title(),
                    'examples': {},
                    'total_examples': 0,
                    'total_usage': 0
                }
            
            example_key = f"{stat.example_type}_{stat.section_type or 'generic'}"
            domain_data[domain_key]['examples'][example_key] = {
                'type': stat.example_type,
                'section_type': stat.section_type,
                'count': stat.example_count,
                'usage': stat.total_usage or 0,
                'effectiveness': round(stat.avg_effectiveness, 2) if stat.avg_effectiveness else None
            }
            domain_data[domain_key]['total_examples'] += stat.example_count
            domain_data[domain_key]['total_usage'] += stat.total_usage or 0
        
        return render_template('prompt_builder/examples.html', 
                             domain_data=domain_data,
                             domains=domains)
    
    except Exception as e:
        logger.error(f"Error loading examples dashboard: {e}")
        flash(f'Error loading examples: {e}', 'error')
        return render_template('prompt_builder/examples.html', 
                             domain_data={}, 
                             domains=[])


@prompt_builder_bp.route('/examples/<domain_name>')
@login_required
def examples_domain(domain_name):
    """
    View and manage examples for a specific domain.
    """
    try:
        # Get examples for this domain
        examples = LangExtractExample.query.filter_by(
            domain=domain_name,
            active=True
        ).order_by(LangExtractExample.example_type, LangExtractExample.priority.desc()).all()
        
        # Get example types and section types
        example_types = ['factual', 'question', 'analysis', 'conclusion', 'code_reference', 'dissenting', 'generic']
        section_types = get_ontology_section_types()
        
        return render_template('prompt_builder/examples_domain.html',
                             domain_name=domain_name,
                             examples=examples,
                             example_types=example_types,
                             section_types=section_types)
    
    except Exception as e:
        logger.error(f"Error loading examples for domain {domain_name}: {e}")
        flash(f'Error loading examples: {e}', 'error')
        return redirect(url_for('prompt_builder.examples_index'))


@prompt_builder_bp.route('/examples/editor')
@prompt_builder_bp.route('/examples/editor/<int:example_id>')
@login_required
def examples_editor(example_id=None):
    """
    LangExtract example editor with structured extraction support.
    """
    try:
        example = None
        if example_id:
            example = LangExtractExample.query.get_or_404(example_id)
        
        # Get available domains and types
        domains = ['generic'] + [w.name.lower() for w in db.session.execute(text("SELECT name FROM worlds")).fetchall()]
        example_types = ['factual', 'question', 'analysis', 'conclusion', 'code_reference', 'dissenting', 'generic']
        section_types = get_ontology_section_types()
        
        # Get extraction class schemas for different types
        extraction_schemas = get_extraction_class_schemas()
        
        return render_template('prompt_builder/examples_editor.html',
                             example=example,
                             domains=domains,
                             example_types=example_types,
                             section_types=section_types,
                             extraction_schemas=extraction_schemas)
    
    except Exception as e:
        logger.error(f"Error loading example editor: {e}")
        flash(f'Error loading editor: {e}', 'error')
        return redirect(url_for('prompt_builder.examples_index'))


@prompt_builder_bp.route('/api/example', methods=['POST'])
@login_required
def save_example():
    """
    Save or update a LangExtract example.
    """
    try:
        data = request.get_json()
        
        example_id = data.get('example_id')
        if example_id:
            # Update existing example
            example = LangExtractExample.query.get_or_404(example_id)
            
            example.name = data['name']
            example.description = data.get('description', '')
            example.example_text = data['example_text']
            example.example_type = data['example_type']
            example.domain = data['domain']
            example.section_type = data.get('section_type')
            example.priority = data.get('priority', 1)
            example.active = data.get('active', True)
        else:
            # Create new example
            example = LangExtractExample(
                name=data['name'],
                description=data.get('description', ''),
                example_text=data['example_text'],
                example_type=data['example_type'],
                domain=data['domain'],
                section_type=data.get('section_type'),
                priority=data.get('priority', 1),
                active=data.get('active', True),
                created_by='web_editor'
            )
            db.session.add(example)
            db.session.flush()  # Get the ID
        
        # Handle extractions
        # First, remove existing extractions if updating
        if example_id:
            LangExtractExampleExtraction.query.filter_by(example_id=example.id).delete()
        
        # Add new extractions
        extractions_data = data.get('extractions', [])
        for idx, extraction_data in enumerate(extractions_data):
            extraction = LangExtractExampleExtraction(
                example_id=example.id,
                extraction_class=extraction_data['extraction_class'],
                extraction_text=extraction_data['extraction_text'],
                attributes=extraction_data.get('attributes', {}),
                order_index=idx
            )
            db.session.add(extraction)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'example_id': example.id,
            'message': 'Example saved successfully'
        })
    
    except Exception as e:
        logger.error(f"Error saving example: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@prompt_builder_bp.route('/api/example/<int:example_id>', methods=['GET'])
@login_required
def get_example(example_id):
    """
    Get a specific LangExtract example with its extractions.
    """
    try:
        example = LangExtractExample.query.get_or_404(example_id)
        return jsonify({
            'success': True,
            'example': example.to_dict()
        })
    
    except Exception as e:
        logger.error(f"Error getting example {example_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@prompt_builder_bp.route('/api/example/<int:example_id>/test', methods=['POST'])
@login_required
def test_example(example_id):
    """
    Test a LangExtract example by converting it to LangExtract format.
    """
    try:
        example = LangExtractExample.query.get_or_404(example_id)
        
        # Convert to LangExtract format
        langextract_data = example.to_langextract_data()
        
        # Return the converted data for preview
        return jsonify({
            'success': True,
            'langextract_format': {
                'text': langextract_data.text,
                'extractions': [
                    {
                        'extraction_class': ext.extraction_class,
                        'extraction_text': ext.extraction_text,
                        'attributes': ext.attributes
                    } for ext in langextract_data.extractions
                ]
            }
        })
    
    except Exception as e:
        logger.error(f"Error testing example {example_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@prompt_builder_bp.route('/api/examples/statistics')
@login_required
def get_examples_statistics():
    """
    Get comprehensive statistics about LangExtract examples usage.
    """
    try:
        # Import here to avoid circular imports
        from ..services.database_langextract_service import DatabaseLangExtractService
        
        service = DatabaseLangExtractService()
        stats = service.get_example_statistics()
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
    
    except Exception as e:
        logger.error(f"Error getting example statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@prompt_builder_bp.route('/api/examples/coverage')
@login_required
def get_examples_coverage():
    """
    Get coverage validation report for LangExtract examples.
    """
    try:
        # Import here to avoid circular imports
        from ..services.database_langextract_service import DatabaseLangExtractService
        
        service = DatabaseLangExtractService()
        coverage = service.validate_example_coverage()
        
        return jsonify({
            'success': True,
            'coverage': coverage
        })
    
    except Exception as e:
        logger.error(f"Error getting example coverage: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def get_extraction_class_schemas() -> Dict[str, Any]:
    """
    Get schemas for different extraction classes to help with example creation.
    """
    return {
        'factual_analysis': {
            'extraction_text_options': ['structured_facts', 'key_information', 'factual_content'],
            'attribute_schema': {
                'key_agents': {'type': 'array', 'description': 'People involved with their roles and credentials'},
                'key_entities': {'type': 'array', 'description': 'Important entities, organizations, or objects'},
                'technical_details': {'type': 'array', 'description': 'Technical specifications or requirements'},
                'contextual_factors': {'type': 'array', 'description': 'Environmental or situational factors'}
            }
        },
        'ethical_question': {
            'extraction_text_options': ['ethical_concerns', 'questions_identified', 'ethical_issues'],
            'attribute_schema': {
                'primary_questions': {'type': 'array', 'description': 'Main ethical questions raised'},
                'underlying_concerns': {'type': 'array', 'description': 'Deeper ethical concerns'},
                'stakeholders_affected': {'type': 'array', 'description': 'Who is impacted by these questions'}
            }
        },
        'ethical_analysis': {
            'extraction_text_options': ['ethical_reasoning', 'analysis_content', 'ethical_evaluation'],
            'attribute_schema': {
                'central_principles': {'type': 'array', 'description': 'Key ethical principles involved'},
                'stakeholder_impacts': {'type': 'array', 'description': 'How different stakeholders are affected'},
                'ethical_tensions': {'type': 'array', 'description': 'Conflicts between ethical principles'}
            }
        }
    }


def get_template_variable_schemas() -> Dict[str, Any]:
    """
    Get common template variable schemas for autocomplete and validation.
    """
    return {
        'case_domain': {
            'type': 'string',
            'description': 'Professional domain context (e.g., engineering, medical)',
            'examples': ['engineering', 'medical', 'legal', 'business']
        },
        'stakeholder_types': {
            'type': 'array',
            'description': 'Types of stakeholders relevant to the domain',
            'examples': ['engineers', 'public', 'clients', 'regulators']
        },
        'professional_codes': {
            'type': 'array', 
            'description': 'Relevant professional codes of ethics',
            'examples': ['NSPE Code', 'IEEE Code', 'AMA Code']
        },
        'regulatory_context': {
            'type': 'string',
            'description': 'Applicable regulations and oversight bodies',
            'examples': ['OSHA compliance', 'EPA regulations', 'FDA approval']
        },
        'safety_considerations': {
            'type': 'array',
            'description': 'Key safety factors and public welfare concerns',
            'examples': ['public safety', 'environmental impact', 'product safety']
        }
    }