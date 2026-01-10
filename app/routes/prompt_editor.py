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
    # Get domain filter from query params
    selected_domain = request.args.get('domain', 'engineering')

    # Get available domains
    domains = db.session.query(ExtractionPromptTemplate.domain).distinct().all()
    available_domains = sorted(set(d[0] for d in domains if d[0])) or ['engineering']

    # Get all active templates for selected domain
    templates = ExtractionPromptTemplate.query.filter_by(
        is_active=True,
        domain=selected_domain
    ).all()

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

    # Get statistics for selected domain
    stats = {
        'total_templates': len(templates),
        'total_versions': ExtractionPromptTemplateVersion.query.count(),
    }

    return render_template('tools/prompt_editor.html',
                          pipeline_data=pipeline_data,
                          stats=stats,
                          concept_colors=CONCEPT_COLORS,
                          available_domains=available_domains,
                          selected_domain=selected_domain)


@prompt_editor_bp.route('/tools/prompts/<int:step>/<concept>')
@login_required
def edit_template(step, concept):
    """Edit a specific template."""
    # Get domain from query params
    selected_domain = request.args.get('domain', 'engineering')

    # Get available domains - handle case where table might be empty
    try:
        domains = db.session.query(ExtractionPromptTemplate.domain).distinct().all()
        available_domains = sorted(set(d[0] for d in domains if d[0])) or ['engineering']
    except Exception as e:
        logger.warning(f"Could not get domains: {e}")
        available_domains = ['engineering']

    # Get the template for this domain
    template = ExtractionPromptTemplate.query.filter_by(
        step_number=step,
        concept_type=concept,
        domain=selected_domain,
        is_active=True
    ).first()

    if not template:
        # Try to find any template for this concept in this domain
        template = ExtractionPromptTemplate.query.filter_by(
            concept_type=concept,
            domain=selected_domain,
            is_active=True
        ).first()

    if not template:
        # Fall back to any domain
        template = ExtractionPromptTemplate.query.filter_by(
            concept_type=concept,
            is_active=True
        ).first()

    # Get step info
    step_info = next((s for s in PIPELINE_STEPS if s['step'] == step), None)

    # Get cases that have extraction prompts for this concept
    try:
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
    except Exception as e:
        logger.warning(f"Could not get cases with extractions: {e}")
        cases_with_extractions = []

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
                          concept_colors=CONCEPT_COLORS,
                          available_domains=available_domains,
                          selected_domain=selected_domain)


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

        # Count extracted entities (TemporaryRDFStorage uses extraction_type, not concept_type)
        entity_count = TemporaryRDFStorage.query.filter_by(
            case_id=extraction.case_id,
            extraction_type=template.concept_type
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


@prompt_editor_bp.route('/api/prompts/template/<int:template_id>/render', methods=['POST'])
@login_required
def render_template_with_case(template_id):
    """Render a template with auto-resolved variables from case context.

    Expects JSON body:
        case_id: int - Document ID
        section_type: str - 'facts' or 'discussion'

    Returns:
        rendered_prompt: str - The fully rendered prompt
        variables_used: dict - Variables that were resolved
    """
    template = ExtractionPromptTemplate.query.get_or_404(template_id)

    data = request.get_json()
    case_id = data.get('case_id')
    section_type = data.get('section_type', 'facts')

    if not case_id:
        return jsonify({
            'success': False,
            'error': 'case_id is required'
        }), 400

    try:
        from app.services.prompt_variable_resolver import get_prompt_variable_resolver

        # Resolve variables from case context
        resolver = get_prompt_variable_resolver()
        variables = resolver.resolve_variables(
            case_id=case_id,
            section_type=section_type,
            concept_type=template.concept_type
        )

        # Render the template
        rendered = template.render(**variables)

        # Get case info for display
        case = Document.query.get(case_id)
        case_title = case.title if case else f'Case {case_id}'

        return jsonify({
            'success': True,
            'rendered_prompt': rendered,
            'variables_used': {k: str(v)[:200] + '...' if len(str(v)) > 200 else str(v)
                              for k, v in variables.items()},
            'case_title': case_title,
            'section_type': section_type,
            'character_count': len(rendered)
        })

    except Exception as e:
        logger.error(f"Error rendering template {template_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@prompt_editor_bp.route('/api/prompts/template/<int:template_id>/test-run', methods=['POST'])
@login_required
def test_run_template(template_id):
    """Execute a test extraction with the template.

    Expects JSON body:
        case_id: int - Document ID
        section_type: str - 'facts' or 'discussion'

    Returns:
        rendered_prompt: str - The prompt sent to LLM
        raw_response: str - Raw LLM response
        entities: dict - Parsed entities
        duration_ms: int - Execution time
    """
    import time
    template = ExtractionPromptTemplate.query.get_or_404(template_id)

    data = request.get_json()
    case_id = data.get('case_id')
    section_type = data.get('section_type', 'facts')

    if not case_id:
        return jsonify({
            'success': False,
            'error': 'case_id is required'
        }), 400

    try:
        from app.services.prompt_variable_resolver import get_prompt_variable_resolver

        start_time = time.time()

        # Resolve variables from case context
        resolver = get_prompt_variable_resolver()
        variables = resolver.resolve_variables(
            case_id=case_id,
            section_type=section_type,
            concept_type=template.concept_type
        )

        # Render the template
        rendered_prompt = template.render(**variables)

        # Call the LLM
        from app.services.llm_utils import call_llm
        from models import ModelConfig
        import json as json_module

        model_name = ModelConfig.get_claude_model("powerful")
        raw_response = call_llm(rendered_prompt, model=model_name)

        # Try to parse as JSON
        entities = {}
        try:
            # Clean response if it has markdown code blocks
            response_text = raw_response
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0]

            entities = json_module.loads(response_text.strip())
        except json_module.JSONDecodeError as e:
            logger.warning(f"Could not parse LLM response as JSON: {e}")
            entities = {'parse_error': str(e), 'raw_text': raw_response[:500]}

        duration_ms = int((time.time() - start_time) * 1000)

        return jsonify({
            'success': True,
            'rendered_prompt': rendered_prompt,
            'raw_response': raw_response,
            'entities': entities,
            'duration_ms': duration_ms,
            'model': model_name
        })

    except Exception as e:
        logger.error(f"Error running test extraction for template {template_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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


@prompt_editor_bp.route('/api/prompts/template/<int:template_id>/resolve-variables', methods=['POST'])
@login_required
def resolve_template_variables(template_id):
    """Resolve all template variables for a given case.

    Expects JSON body:
        case_id: int - Document ID
        section_type: str - 'facts' or 'discussion' (optional, defaults to 'facts')

    Returns:
        variables: dict - All resolved variables with their values
    """
    template = ExtractionPromptTemplate.query.get_or_404(template_id)

    data = request.get_json()
    case_id = data.get('case_id')
    section_type = data.get('section_type', 'facts')

    if not case_id:
        return jsonify({
            'success': False,
            'error': 'case_id is required'
        }), 400

    try:
        from app.services.prompt_variable_resolver import get_prompt_variable_resolver

        resolver = get_prompt_variable_resolver()
        variables = resolver.resolve_variables(
            case_id=case_id,
            section_type=section_type,
            concept_type=template.concept_type
        )

        # Get case info
        case = Document.query.get(case_id)
        case_title = case.title if case else f'Case {case_id}'

        # Format variables for display - include metadata
        formatted_vars = {}
        for key, value in variables.items():
            str_value = str(value)
            formatted_vars[key] = {
                'value': str_value,
                'length': len(str_value),
                'preview': str_value[:500] + '...' if len(str_value) > 500 else str_value,
                'type': type(value).__name__
            }

        return jsonify({
            'success': True,
            'case_id': case_id,
            'case_title': case_title,
            'section_type': section_type,
            'concept_type': template.concept_type,
            'variables': formatted_vars
        })

    except Exception as e:
        logger.error(f"Error resolving variables for template {template_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# CSRF Exemption
# ============================================================================

def init_prompt_editor_csrf_exemption(app):
    """Exempt prompt editor API routes from CSRF protection."""
    if app.csrf:
        app.csrf.exempt(update_template)
        app.csrf.exempt(preview_template)
        app.csrf.exempt(revert_template)
        app.csrf.exempt(render_template_with_case)
        app.csrf.exempt(test_run_template)
        app.csrf.exempt(resolve_template_variables)
