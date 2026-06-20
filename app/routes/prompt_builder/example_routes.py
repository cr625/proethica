"""Prompt-builder LangExtract example routes."""
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


def register_example_routes(bp):
    @bp.route('/examples')
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


    @bp.route('/api/example', methods=['POST'])
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


    @bp.route('/api/example/<int:example_id>', methods=['GET'])
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


    @bp.route('/api/example/<int:example_id>/test', methods=['POST'])
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


