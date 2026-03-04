"""Legacy scenario generation routes (deconstruction-based)."""

import logging
from flask import request, jsonify, url_for
from flask_login import current_user
from app.utils.environment_auth import auth_required_for_llm
from app.models import Document
from app.services.case_to_scenario_service import CaseToScenarioService
from app.services.scenario_generation_service import ScenarioGenerationService

logger = logging.getLogger(__name__)


def register_scenario_legacy_routes(bp):

    @bp.route('/<int:case_id>/generate_scenario', methods=['POST'])
    @auth_required_for_llm
    def generate_scenario_from_case(case_id):
        """Generate a scenario from a case using background processing."""
        try:
            logger.info(f"Starting scenario generation for case {case_id}")

            case = Document.query.get_or_404(case_id)
            scenario_service = CaseToScenarioService()

            can_process, reason = scenario_service.can_deconstruct_case(case)
            logger.info(f"Can deconstruct case {case_id}: {can_process}, reason: {reason}")

            if not can_process:
                return jsonify({
                    'success': False,
                    'error': f'Cannot generate scenario: {reason}'
                }), 400

            task_id = scenario_service.deconstruct_case_async(case_id)
            logger.info(f"Started async deconstruction for case {case_id} with task_id: {task_id}")

            return jsonify({
                'success': True,
                'task_id': task_id,
                'message': 'Scenario generation started'
            })

        except Exception as e:
            logger.error(f"Error starting scenario generation for case {case_id}: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/<int:case_id>/scenario_generation_progress', methods=['GET'])
    def get_scenario_generation_progress(case_id):
        """Get the progress of scenario generation for a case."""
        try:
            scenario_service = CaseToScenarioService()
            progress = scenario_service.get_deconstruction_progress(case_id)

            return jsonify({
                'success': True,
                'progress': progress
            })

        except Exception as e:
            logger.error(f"Error getting scenario generation progress for case {case_id}: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/<int:case_id>/scenario_status', methods=['GET'])
    def get_scenario_status(case_id):
        """Check if a case has been deconstructed and can generate scenarios."""
        try:
            from app.models.deconstructed_case import DeconstructedCase
            from app.models.scenario_template import ScenarioTemplate

            case = Document.query.get_or_404(case_id)
            scenario_service = CaseToScenarioService()

            can_deconstruct, reason = scenario_service.can_deconstruct_case(case)

            deconstructed = DeconstructedCase.query.filter_by(case_id=case_id).first()

            templates = []
            scenarios = []
            if deconstructed:
                try:
                    templates = ScenarioTemplate.query.filter_by(deconstructed_case_id=deconstructed.id).all()
                except Exception as e:
                    logger.warning(f"Error querying scenario templates: {str(e)}")
                    templates = []

                try:
                    from app.models.scenario import Scenario
                    all_scenarios = Scenario.query.filter_by(world_id=case.world_id).all()
                    for scenario in all_scenarios:
                        if scenario.scenario_metadata and scenario.scenario_metadata.get('source_case_id') == case_id:
                            scenarios.append(scenario)
                except Exception as e:
                    logger.warning(f"Error querying scenarios: {str(e)}")
                    scenarios = []

            return jsonify({
                'success': True,
                'can_deconstruct': can_deconstruct,
                'deconstruct_reason': reason,
                'is_deconstructed': deconstructed is not None,
                'deconstructed_case_id': deconstructed.id if deconstructed else None,
                'has_templates': len(templates) > 0,
                'template_count': len(templates),
                'templates': [{'id': t.id, 'title': t.title} for t in templates],
                'has_scenarios': len(scenarios) > 0,
                'scenario_count': len(scenarios),
                'scenarios': [{'id': s.id, 'name': s.name, 'url': f'/scenarios/{s.id}'} for s in scenarios]
            })

        except Exception as e:
            logger.error(f"Error getting scenario status for case {case_id}: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/<int:case_id>/create_scenario_template', methods=['POST'])
    @auth_required_for_llm
    def create_scenario_template(case_id):
        """Create a scenario template from a deconstructed case."""
        try:
            from app.models.deconstructed_case import DeconstructedCase

            deconstructed = DeconstructedCase.query.filter_by(case_id=case_id).first()
            if not deconstructed:
                return jsonify({
                    'success': False,
                    'error': 'Case must be deconstructed first'
                }), 400

            generation_service = ScenarioGenerationService()
            template = generation_service.generate_scenario_template(deconstructed)

            if not template:
                return jsonify({
                    'success': False,
                    'error': 'Failed to generate scenario template'
                }), 500

            return jsonify({
                'success': True,
                'template_id': template.id,
                'template_title': template.title,
                'message': 'Scenario template created successfully'
            })

        except Exception as e:
            logger.error(f"Error creating scenario template for case {case_id}: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/templates/<int:template_id>/create_scenario', methods=['POST'])
    @auth_required_for_llm
    def create_scenario_from_template(template_id):
        """Create a playable scenario from a template."""
        try:
            from app.models.scenario_template import ScenarioTemplate

            template = ScenarioTemplate.query.get_or_404(template_id)

            customizations = request.json or {}

            generation_service = ScenarioGenerationService()
            scenario = generation_service.create_scenario_instance(
                template,
                current_user.id,
                customizations
            )

            if not scenario:
                return jsonify({
                    'success': False,
                    'error': 'Failed to create scenario instance'
                }), 500

            return jsonify({
                'success': True,
                'scenario_id': scenario.id,
                'scenario_title': scenario.title,
                'redirect_url': url_for('scenarios.view_scenario', id=scenario.id)
            })

        except Exception as e:
            logger.error(f"Error creating scenario from template {template_id}: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
