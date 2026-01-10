"""
Prompt Editor Routes for extraction template management.

Provides web UI and API for viewing and editing extraction prompt templates.
Mirrors the provenance viewer structure for consistency.
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required
from sqlalchemy import func

from app.models import db
from app.models.extraction_prompt_template import (
    ExtractionPromptTemplate, ExtractionPromptTemplateVersion,
    PIPELINE_STEPS, CONCEPT_COLORS, CONCEPT_SOURCE_FILES
)
from app.models.extraction_prompt import ExtractionPrompt
from app.models.document import Document
from app.models.temporary_rdf_storage import TemporaryRDFStorage

import logging

logger = logging.getLogger(__name__)

prompt_editor_bp = Blueprint('prompt_editor', __name__)


# ============================================================================
# Web UI Routes
# ============================================================================

@prompt_editor_bp.route('/tools/prompts')
@login_required
def index():
    """Main prompt editor page showing pipeline structure."""
    # Get all active templates
    templates = ExtractionPromptTemplate.query.filter_by(is_active=True).all()

    # Organize templates by step and concept
    templates_by_concept = {t.concept_type: t for t in templates}

    # Build pipeline data structure for UI
    pipeline_data = []
    for step in PIPELINE_STEPS:
        step_data = {
            'step': step['step'],
            'name': step['name'],
            'color': step['color'],
            'concepts': []
        }
        for concept in step['concepts']:
            template = templates_by_concept.get(concept)
            step_data['concepts'].append({
                'type': concept,
                'color': CONCEPT_COLORS.get(concept, '#6c757d'),
                'template': template,
                'has_template': template is not None
            })
        pipeline_data.append(step_data)

    # Get statistics
    stats = {
        'total_templates': len(templates),
        'total_versions': ExtractionPromptTemplateVersion.query.count(),
    }

    return render_template('tools/prompt_editor.html',
                          pipeline_data=pipeline_data,
                          stats=stats,
                          concept_colors=CONCEPT_COLORS)


@prompt_editor_bp.route('/tools/prompts/<int:step>/<concept>')
@login_required
def edit_template(step, concept):
    """Edit a specific template."""
    # Get the template
    template = ExtractionPromptTemplate.query.filter_by(
        step_number=step,
        concept_type=concept,
        is_active=True
    ).first()

    if not template:
        # Try to find any template for this concept
        template = ExtractionPromptTemplate.query.filter_by(
            concept_type=concept,
            is_active=True
        ).first()

    # Get step info
    step_info = next((s for s in PIPELINE_STEPS if s['step'] == step), None)

    # Get cases that have extraction prompts for this concept
    cases_with_extractions = db.session.query(
        Document.id,
        Document.title,
        func.count(ExtractionPrompt.id).label('extraction_count'),
        func.max(ExtractionPrompt.created_at).label('last_extraction')
    ).join(
        ExtractionPrompt, ExtractionPrompt.case_id == Document.id
    ).filter(
        ExtractionPrompt.concept_type == concept
    ).group_by(
        Document.id, Document.title
    ).order_by(
        func.max(ExtractionPrompt.created_at).desc()
    ).limit(20).all()

    # Get version history
    versions = []
    if template:
        versions = ExtractionPromptTemplateVersion.query.filter_by(
            template_id=template.id
        ).order_by(
            ExtractionPromptTemplateVersion.version_number.desc()
        ).limit(10).all()

    return render_template('tools/prompt_editor_detail.html',
                          template=template,
                          step=step,
                          concept=concept,
                          step_info=step_info,
                          concept_color=CONCEPT_COLORS.get(concept, '#6c757d'),
                          cases_with_extractions=cases_with_extractions,
                          versions=versions,
                          pipeline_steps=PIPELINE_STEPS,
                          concept_colors=CONCEPT_COLORS)


# ============================================================================
# API Routes
# ============================================================================

@prompt_editor_bp.route('/api/prompts/templates')
@login_required
def get_templates():
    """Get all templates organized by pipeline step."""
    templates = ExtractionPromptTemplate.query.filter_by(is_active=True).all()
    templates_by_concept = {t.concept_type: t for t in templates}

    result = {
        'steps': []
    }

    for step in PIPELINE_STEPS:
        step_data = {
            'step': step['step'],
            'name': step['name'],
            'color': step['color'],
            'concepts': []
        }
        for concept in step['concepts']:
            template = templates_by_concept.get(concept)
            step_data['concepts'].append({
                'type': concept,
                'color': CONCEPT_COLORS.get(concept, '#6c757d'),
                'template_id': template.id if template else None,
                'has_active': template is not None,
                'version': template.version if template else 0,
                'name': template.name if template else f'{concept.title()} Extraction'
            })
        result['steps'].append(step_data)

    return jsonify(result)


@prompt_editor_bp.route('/api/prompts/template/<int:template_id>')
@login_required
def get_template(template_id):
    """Get a single template by ID."""
    template = ExtractionPromptTemplate.query.get_or_404(template_id)
    return jsonify({
        'success': True,
        'template': template.to_dict()
    })


@prompt_editor_bp.route('/api/prompts/template/<int:template_id>', methods=['PUT'])
@login_required
def update_template(template_id):
    """Update a template (creates new version)."""
    template = ExtractionPromptTemplate.query.get_or_404(template_id)

    data = request.get_json()

    # Validate required fields
    if 'template_text' not in data:
        return jsonify({
            'success': False,
            'error': 'template_text is required'
        }), 400

    try:
        # Create version history record
        version_record = ExtractionPromptTemplateVersion(
            template_id=template.id,
            version_number=template.version,
            template_text=template.template_text,
            variables_schema=template.variables_schema,
            change_description=data.get('change_description', 'Updated via web editor'),
            changed_by=data.get('changed_by', 'web_editor')
        )
        db.session.add(version_record)

        # Update template
        template.template_text = data['template_text']
        template.version += 1

        # Update optional fields
        if 'name' in data:
            template.name = data['name']
        if 'description' in data:
            template.description = data['description']
        if 'variables_schema' in data:
            template.variables_schema = data['variables_schema']

        db.session.commit()

        logger.info(f"Updated template {template_id} to version {template.version}")

        return jsonify({
            'success': True,
            'template': template.to_dict(),
            'message': f'Template updated to version {template.version}'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating template {template_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@prompt_editor_bp.route('/api/prompts/template/<int:template_id>/examples')
@login_required
def get_template_examples(template_id):
    """Get example extractions for a template."""
    template = ExtractionPromptTemplate.query.get_or_404(template_id)

    # Get case_id from query params or default to most recent
    case_id = request.args.get('case_id', type=int)

    # Query extraction prompts for this concept type
    query = ExtractionPrompt.query.filter_by(concept_type=template.concept_type)

    if case_id:
        query = query.filter_by(case_id=case_id)

    extractions = query.order_by(
        ExtractionPrompt.created_at.desc()
    ).limit(10).all()

    examples = []
    for extraction in extractions:
        # Get case info
        case = Document.query.get(extraction.case_id)

        # Count extracted entities
        entity_count = TemporaryRDFStorage.query.filter_by(
            case_id=extraction.case_id,
            concept_type=template.concept_type
        ).count()

        examples.append({
            'id': extraction.id,
            'case_id': extraction.case_id,
            'case_title': case.title if case else f'Case {extraction.case_id}',
            'section_type': extraction.section_type,
            'prompt_text': extraction.prompt_text,
            'raw_response': extraction.raw_response,
            'entities_extracted': entity_count,
            'llm_model': extraction.llm_model,
            'created_at': extraction.created_at.isoformat() if extraction.created_at else None
        })

    return jsonify({
        'success': True,
        'concept_type': template.concept_type,
        'examples': examples
    })


@prompt_editor_bp.route('/api/prompts/template/<int:template_id>/preview', methods=['POST'])
@login_required
def preview_template(template_id):
    """Preview a template with sample variables."""
    template = ExtractionPromptTemplate.query.get_or_404(template_id)

    data = request.get_json()
    template_text = data.get('template_text', template.template_text)
    variables = data.get('variables', {})

    try:
        from jinja2 import Template
        jinja_template = Template(template_text)
        rendered = jinja_template.render(**variables)

        return jsonify({
            'success': True,
            'rendered_template': rendered,
            'variables_used': list(variables.keys()),
            'character_count': len(rendered)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@prompt_editor_bp.route('/api/prompts/template/<int:template_id>/versions')
@login_required
def get_template_versions(template_id):
    """Get version history for a template."""
    template = ExtractionPromptTemplate.query.get_or_404(template_id)

    versions = ExtractionPromptTemplateVersion.query.filter_by(
        template_id=template_id
    ).order_by(
        ExtractionPromptTemplateVersion.version_number.desc()
    ).all()

    return jsonify({
        'success': True,
        'current_version': template.version,
        'versions': [v.to_dict() for v in versions]
    })


@prompt_editor_bp.route('/api/prompts/template/<int:template_id>/revert/<int:version_number>', methods=['POST'])
@login_required
def revert_template(template_id, version_number):
    """Revert a template to a previous version."""
    template = ExtractionPromptTemplate.query.get_or_404(template_id)

    # Find the version to revert to
    version = ExtractionPromptTemplateVersion.query.filter_by(
        template_id=template_id,
        version_number=version_number
    ).first()

    if not version:
        return jsonify({
            'success': False,
            'error': f'Version {version_number} not found'
        }), 404

    try:
        # Create new version record for current state before reverting
        current_version = ExtractionPromptTemplateVersion(
            template_id=template.id,
            version_number=template.version,
            template_text=template.template_text,
            variables_schema=template.variables_schema,
            change_description=f'Before revert to version {version_number}',
            changed_by='web_editor'
        )
        db.session.add(current_version)

        # Update template with reverted content
        template.template_text = version.template_text
        template.variables_schema = version.variables_schema
        template.version += 1

        db.session.commit()

        logger.info(f"Reverted template {template_id} to version {version_number}")

        return jsonify({
            'success': True,
            'template': template.to_dict(),
            'message': f'Template reverted to version {version_number}'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error reverting template {template_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@prompt_editor_bp.route('/api/prompts/cases-with-extractions/<concept>')
@login_required
def get_cases_with_extractions(concept):
    """Get list of cases that have extractions for a concept type."""
    cases = db.session.query(
        Document.id,
        Document.title,
        func.count(ExtractionPrompt.id).label('extraction_count'),
        func.max(ExtractionPrompt.created_at).label('last_extraction')
    ).join(
        ExtractionPrompt, ExtractionPrompt.case_id == Document.id
    ).filter(
        ExtractionPrompt.concept_type == concept
    ).group_by(
        Document.id, Document.title
    ).order_by(
        func.max(ExtractionPrompt.created_at).desc()
    ).limit(50).all()

    return jsonify({
        'success': True,
        'concept_type': concept,
        'cases': [
            {
                'id': c.id,
                'title': c.title,
                'extraction_count': c.extraction_count,
                'last_extraction': c.last_extraction.isoformat() if c.last_extraction else None
            }
            for c in cases
        ]
    })


# ============================================================================
# CSRF Exemption
# ============================================================================

def init_prompt_editor_csrf_exemption(app):
    """Exempt prompt editor API routes from CSRF protection."""
    if app.csrf:
        app.csrf.exempt(update_template)
        app.csrf.exempt(preview_template)
        app.csrf.exempt(revert_template)
