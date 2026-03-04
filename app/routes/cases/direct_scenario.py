"""Direct scenario generation and viewing routes."""

import logging
from flask import request, jsonify, render_template, redirect, url_for, flash
from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified
from app.utils.environment_auth import auth_optional, auth_required_for_write
from app.models import Document
from app.services.scenario_pipeline.scenario_generation_phase_a import DirectScenarioPipelineService
from app import db

logger = logging.getLogger(__name__)


def register_direct_scenario_routes(bp):

    @bp.route('/<int:case_id>/direct_scenario', methods=['POST'])
    def generate_direct_scenario(case_id):
        """Generate enhanced scenario with LLM-mediated temporal reasoning and ontology integration."""
        try:
            case = Document.query.get_or_404(case_id)
            overwrite = (request.args.get('overwrite', 'false').lower() == 'true')

            pipeline = DirectScenarioPipelineService()

            logger.info(f"Scenario generation for case {case_id}:")
            logger.info(f"  Enhanced enabled: {pipeline.enhanced_enabled}")
            logger.info(f"  LLM temporal enabled: {getattr(pipeline, 'llm_temporal_enabled', False)}")
            logger.info(f"  Enhanced service available: {getattr(pipeline, 'enhanced_service', None) is not None}")

            data = pipeline.generate(case, overwrite=True)

            if data is None:
                logger.error(f"Pipeline generate returned None for case {case_id}")
                return jsonify({
                    'success': False,
                    'error': 'Scenario generation failed - pipeline returned no data'
                }), 500

            if not isinstance(data, dict):
                logger.error(f"Pipeline generate returned invalid data type: {type(data)}")
                return jsonify({
                    'success': False,
                    'error': 'Scenario generation failed - invalid data structure returned'
                }), 500

            if 'stats' not in data:
                logger.error(f"Pipeline data missing 'stats' field for case {case_id}")
                return jsonify({
                    'success': False,
                    'error': 'Scenario generation failed - incomplete data structure'
                }), 500

            include_events = request.args.get('include_events', 'true').lower() != 'false'
            payload = {
                'success': True,
                'case_id': case_id,
                'version_number': data.get('version_number'),
                'stats': data.get('stats'),
                'event_count': data.get('stats', {}).get('event_count', 0),
                'decision_count': data.get('stats', {}).get('decision_count', 0)
            }
            if include_events:
                if request.args.get('trim'):
                    trimmed = []
                    for ev in data['events']:
                        trimmed.append({
                            'id': ev.get('id'),
                            'kind': ev.get('kind'),
                            'section': ev.get('section'),
                            'text': (ev.get('text', '')[:160] + ('\u2026' if len(ev.get('text', '')) > 160 else '')),
                            'options': ev.get('options') and [o.get('label') for o in ev['options']],
                            'refined': ev.get('refined')
                        })
                    payload['events'] = trimmed
                    payload['trimmed'] = True
                else:
                    payload['events'] = data['events']
            return jsonify(payload)
        except Exception as e:
            logger.error(f"Direct scenario generation failed for case {case_id}: {str(e)}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/<int:case_id>/scenario', methods=['GET'])
    @auth_optional
    def view_case_scenario(case_id):
        """Display the generated scenario timeline and ProEthica categories for a case."""
        try:
            case = Document.query.get_or_404(case_id)
            latest_scenario = None

            if case.doc_metadata and isinstance(case.doc_metadata, dict):
                latest_scenario = case.doc_metadata.get('latest_scenario')

            if not latest_scenario:
                flash('No scenario generated yet. Please generate a scenario first.', 'warning')
                return redirect(url_for('cases.view_case', id=case_id))

            if isinstance(latest_scenario, list):
                logger.error(f"Latest scenario is a list instead of dict for case {case_id}: {type(latest_scenario)}")
                flash('Invalid scenario data structure. Please regenerate the scenario.', 'danger')
                return redirect(url_for('cases.view_case', id=case_id))

            if not isinstance(latest_scenario, dict):
                logger.error(f"Latest scenario is not a dict for case {case_id}: {type(latest_scenario)}")
                flash('Invalid scenario data structure. Please regenerate the scenario.', 'danger')
                return redirect(url_for('cases.view_case', id=case_id))

            filtered_events = []
            events = latest_scenario.get('events', [])

            if not isinstance(events, list):
                logger.error(f"Events field is not a list for case {case_id}: {type(events)}")
                events = []

            for event in events:
                if isinstance(event, dict) and event.get('kind') != 'action':
                    filtered_events.append(event)

            display_scenario = dict(latest_scenario) if isinstance(latest_scenario, dict) else {}
            display_scenario['events'] = filtered_events

            stats = display_scenario.get('stats', {})
            if not isinstance(stats, dict):
                logger.warning(f"Stats field is not a dictionary, type: {type(stats)}")
                display_scenario['stats'] = {
                    'event_count': len(filtered_events),
                    'decision_count': sum(1 for e in filtered_events if isinstance(e, dict) and e.get('kind') == 'decision'),
                    'original_stats': stats
                }
            else:
                display_scenario['stats']['event_count'] = len(filtered_events)

            ontology_summary = display_scenario.get('ontology_summary', {})
            if not isinstance(ontology_summary, dict):
                logger.warning(f"Ontology summary is not a dict for case {case_id}: {type(ontology_summary)}")
                display_scenario['ontology_summary'] = {}

            return render_template('case_scenario_detail.html',
                                 case=case,
                                 scenario=display_scenario)
        except Exception as e:
            logger.error(f"Error loading case scenario for case {case_id}: {e}")
            flash(f"Error loading scenario: {e}", 'danger')
            return redirect(url_for('cases.view_case', id=case_id))

    @bp.route('/<int:case_id>/scenario_interim', methods=['GET'])
    def view_interim_scenario(case_id):
        """Legacy interim scenario view - redirects to new scenario view."""
        return redirect(url_for('cases.view_case_scenario', case_id=case_id))

    @bp.route('/<int:case_id>/clear_scenario', methods=['POST'])
    @auth_required_for_write
    def clear_scenario(case_id):
        """Clear all scenario data for a case to enable fresh generation."""
        try:
            case = Document.query.get_or_404(case_id)

            from app.models.scenario import Scenario
            from app.models.event import Event, Action
            from app.models.character import Character
            from app.models.resource import Resource
            from app.models.decision import Decision
            from app.models.principle import Principle
            from app.models.obligation import Obligation
            from app.models.state import State
            from app.models.capability import Capability
            from app.models.constraint import Constraint
            from app.models.reasoning_trace import ReasoningTrace, ReasoningStep

            cleared_items = []

            scenarios_to_clear = []

            metadata_scenarios = Scenario.query.filter(
                text("scenario_metadata->>'source_case_id' = :case_id")
            ).params(case_id=str(case_id)).all()
            scenarios_to_clear.extend(metadata_scenarios)

            case_world_scenarios = Scenario.query.filter_by(world_id=case.world_id).all()
            for scenario in case_world_scenarios:
                if (scenario.scenario_metadata and
                    scenario.scenario_metadata.get('source_case_id') == case_id):
                    if scenario not in scenarios_to_clear:
                        scenarios_to_clear.append(scenario)

            scenario_ids_to_delete = [scenario.id for scenario in scenarios_to_clear]

            for scenario in scenarios_to_clear:
                scenario_id = scenario.id
                scenario_name = scenario.name
                logger.info(f"Deleting scenario {scenario_id}: {scenario_name}")

                tables_to_clean = [
                    'capabilities', 'constraints', 'states', 'obligations', 'principles',
                    'characters', 'resources', 'actions', 'events', 'decisions'
                ]

                for table in tables_to_clean:
                    try:
                        db.session.execute(text(f"DELETE FROM {table} WHERE scenario_id = :scenario_id"),
                                         {"scenario_id": scenario_id})
                    except Exception as e:
                        logger.warning(f"Error deleting {table}: {e}")

                try:
                    db.session.execute(text("DELETE FROM scenarios WHERE id = :scenario_id"),
                                     {"scenario_id": scenario_id})
                    cleared_items.append(f"Scenario {scenario_id}: {scenario_name}")
                except Exception as e:
                    logger.error(f"Error deleting scenario {scenario_id}: {e}")

            reasoning_traces = ReasoningTrace.query.filter_by(case_id=case_id).all()
            for trace in reasoning_traces:
                logger.info(f"Deleting reasoning trace {trace.id}: {trace.session_id}")
                db.session.delete(trace)
                cleared_items.append(f"Reasoning trace {trace.id}: {trace.session_id}")

            metadata = case.doc_metadata or {}
            cleared_metadata_fields = []

            for field in ['latest_scenario', 'scenario_versions', 'temporal_analysis',
                         'llm_validation_session', 'reasoning_trace_id', 'reasoning_session_id']:
                if field in metadata:
                    del metadata[field]
                    cleared_metadata_fields.append(field)

            if cleared_metadata_fields:
                case.doc_metadata = metadata
                flag_modified(case, 'doc_metadata')
                db.session.add(case)

            db.session.commit()

            logger.info(f"Cleared scenario data for case {case_id}:")
            logger.info(f"  - Database scenarios: {len(scenarios_to_clear)}")
            logger.info(f"  - Reasoning traces: {len(reasoning_traces)}")
            logger.info(f"  - Metadata fields: {cleared_metadata_fields}")

            return jsonify({
                'success': True,
                'message': f'Scenario data cleared successfully',
                'database_scenarios_cleared': len(scenarios_to_clear),
                'reasoning_traces_cleared': len(reasoning_traces),
                'metadata_fields_cleared': cleared_metadata_fields,
                'details': {
                    'scenarios': cleared_items,
                    'metadata_fields': cleared_metadata_fields
                }
            })

        except Exception as e:
            logger.error(f"Error clearing scenario for case {case_id}: {str(e)}")
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
