"""Step 4 synthesis: phase view (tools/prompt_editor_step4.html), synthesis config GET/PUT, step4 prompt-source endpoint. Includes the module-level helper _extract_method (911-940), referenced ONLY by get_step4_prompt, so it is co-located here at module level inside this file (NOT inside register_step4; define it as a plain module fn alongside the register fn).."""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required
from sqlalchemy import func

from app.models import db
from app.models.extraction_prompt_template import (
    ExtractionPromptTemplate, ExtractionPromptTemplateVersion,
    PIPELINE_STEPS, CONCEPT_COLORS, CONCEPT_SOURCE_FILES, STEP4_PHASES,
    GUIDELINE_PIPELINE_STEPS, GUIDELINE_CONCEPTS
)
from app.models.extraction_prompt import ExtractionPrompt
from app.models.document import Document
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.routes.prompt_editor.web_ui_routes import can_edit_prompts

import logging

logger = logging.getLogger(__name__)


def register_step4(bp):
    # Own subpath: '/tools/prompts/4/<concept>' must fall through to the generic
    # edit_template route for the step-4 template concept_types (the static '4'
    # segment would otherwise shadow the <int:step> rule for every step-4 URL).
    @bp.route('/tools/prompts/4/phase/<phase>')
    def view_step4_phase(phase):
        """View a Step 4 synthesis phase: each prompt links to its editable DB template
        (step_number=4 rows since the 2026-07-11 migration); the source view shows the
        builder that assembles the variables and renders it."""
        from app.models.extraction_prompt_template import STEP4_PHASES
        from app.models.synthesis_config import SynthesisConfig, SYNTHESIS_PARAMETERS

        if phase not in STEP4_PHASES:
            return redirect(url_for('prompt_editor.edit_template', step=1, concept='roles'))

        phase_info = STEP4_PHASES[phase]

        # Get synthesis config
        config = SynthesisConfig.get_active()

        # Get available cases for testing link
        try:
            cases = db.session.query(
                Document.id,
                Document.title
            ).order_by(
                Document.created_at.desc()
            ).limit(20).all()
        except Exception:
            cases = []

        return render_template('tools/prompt_editor_step4.html',
                              phase=phase,
                              can_edit=can_edit_prompts(),
                              phase_info=phase_info,
                              step4_phases=STEP4_PHASES,
                              config=config,
                              parameters=SYNTHESIS_PARAMETERS,
                              cases=cases,
                              pipeline_steps=PIPELINE_STEPS,
                              concept_colors=CONCEPT_COLORS)
    @bp.route('/api/prompts/step4/config')
    @login_required
    def get_synthesis_config():
        """Get current synthesis configuration."""
        from app.models.synthesis_config import SynthesisConfig, SYNTHESIS_PARAMETERS

        config = SynthesisConfig.get_active()

        return jsonify({
            'success': True,
            'config': config.to_dict(),
            'parameters': SYNTHESIS_PARAMETERS
        })
    @bp.route('/api/prompts/step4/config', methods=['PUT'])
    @login_required
    def update_synthesis_config():
        """Update synthesis configuration."""
        from app.models.synthesis_config import SynthesisConfig

        config = SynthesisConfig.get_active()
        data = request.get_json()

        try:
            data['updated_by'] = 'web_editor'
            config.update_from_dict(data)
            db.session.commit()

            logger.info(f"Updated synthesis config: {list(data.keys())}")

            return jsonify({
                'success': True,
                'config': config.to_dict(),
                'message': 'Configuration updated'
            })

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating synthesis config: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    @bp.route('/api/prompts/step4/prompt/<phase>/<prompt_name>')
    @login_required
    def get_step4_prompt(phase, prompt_name):
        """Get the source code for a Step 4 prompt method.

    Returns the actual Python code that generates the prompt,
    since Step 4 prompts are embedded in service files.
    """
        from app.models.extraction_prompt_template import STEP4_PHASES
        import os

        if phase not in STEP4_PHASES:
            return jsonify({'success': False, 'error': 'Unknown phase'}), 404

        phase_info = STEP4_PHASES[phase]

        # Find the prompt info
        prompt_info = None
        for p in phase_info.get('prompts', []):
            if p['method'] == prompt_name or p['name'].lower().replace(' ', '_') == prompt_name:
                prompt_info = p
                break

        if not prompt_info:
            return jsonify({'success': False, 'error': 'Unknown prompt'}), 404

        # Get the source file
        source_file = prompt_info.get('file', phase_info['service_file'])
        full_path = os.path.join('/home/chris/onto/proethica', source_file)

        try:
            with open(full_path, 'r') as f:
                content = f.read()

            # Try to extract just the method
            method_name = prompt_info['method']
            method_code = _extract_method(content, method_name)

            return jsonify({
                'success': True,
                'phase': phase,
                'prompt_name': prompt_info['name'],
                'method': method_name,
                'source_file': source_file,
                'code': method_code or f"# Method {method_name} not found in {source_file}"
            })

        except FileNotFoundError:
            return jsonify({
                'success': False,
                'error': f'Source file not found: {source_file}'
            }), 404
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    def _extract_method(source_code: str, method_name: str) -> str:
        """Extract a method definition from Python source code."""
        import re

        # Match def method_name( and capture until next def at same indent level
        # This is a simplified extraction - handles most common cases
        pattern = rf'^( *)def {re.escape(method_name)}\s*\([^)]*\)[^:]*:'
        match = re.search(pattern, source_code, re.MULTILINE)

        if not match:
            return None

        start_pos = match.start()
        indent = len(match.group(1))
        lines = source_code[start_pos:].split('\n')
        result_lines = [lines[0]]

        for line in lines[1:]:
            # Check if we've hit another def at the same or lower indent level
            stripped = line.lstrip()
            if stripped and not line.startswith(' ' * (indent + 1)):
                if stripped.startswith('def ') or stripped.startswith('class '):
                    break
            result_lines.append(line)

        # Trim trailing empty lines
        while result_lines and not result_lines[-1].strip():
            result_lines.pop()

        return '\n'.join(result_lines)
