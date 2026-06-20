"""Injection-mode API."""
from flask import Blueprint, render_template, jsonify, request
from app.models import db
from app.models.pipeline_run import PipelineRun, PipelineQueue, PIPELINE_STATUS
from app.models.document import Document
from app.services.pipeline_state_manager import PipelineStateManager
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def register_injection_routes(bp):
    @bp.route('/api/set_injection_mode', methods=['POST'])
    def api_set_injection_mode():
        """Set the ontology injection mode for extraction.

    Used by run_pipeline.py --injection-mode to switch between
    'full' (Phase 1) and 'label_only' (Phase 2).
    """
        from flask import current_app
        data = request.get_json() or {}
        mode = data.get('mode', 'full')
        if mode not in ('full', 'label_only'):
            return jsonify({'error': f'Invalid mode: {mode}'}), 400
        current_app.config['INJECTION_MODE'] = mode
        logger.info(f"Injection mode set to: {mode}")
        return jsonify({'mode': mode, 'success': True})


    @bp.route('/api/get_injection_mode', methods=['GET'])
    def api_get_injection_mode():
        """Get the current ontology injection mode."""
        from flask import current_app
        mode = current_app.config.get('INJECTION_MODE', 'full')
        return jsonify({'mode': mode})


    # Web Pages

