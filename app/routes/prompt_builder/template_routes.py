"""Prompt-builder template-management routes (index, domain, editor, save/preview, perf)."""
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
from app.routes.prompt_builder.helpers import (
    get_ontology_section_types,
    get_domain_specific_section_types,
    get_template_variable_schemas,
)


def register_template_routes(bp):
    @bp.route('/')
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


    @bp.route('/domain/<domain_name>')
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


    @bp.route('/editor')
    @bp.route('/editor/<int:template_id>')
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


    @bp.route('/api/template', methods=['POST'])
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


    @bp.route('/api/template/<int:template_id>/preview', methods=['POST'])
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


    @bp.route('/api/section-types/<domain_name>')
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


    @bp.route('/api/template/<int:template_id>/performance')
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


