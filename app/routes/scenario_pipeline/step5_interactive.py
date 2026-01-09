"""
Step 5 Interactive Exploration Routes

Handles the interactive scenario exploration workflow where users
make choices at decision points and see LLM-generated consequences.

Routes:
    /step5/interactive/start - Start new exploration session
    /step5/interactive/<session_uuid> - Continue exploration
    /step5/interactive/<session_uuid>/choose - Make a choice
    /step5/interactive/<session_uuid>/analysis - View final analysis
"""

import logging
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash

from app.models import db, Document
from app.models.scenario_exploration import ScenarioExplorationSession, ScenarioExplorationChoice
from app.services.interactive_scenario_service import interactive_scenario_service
from app.services.pipeline_status_service import PipelineStatusService
from app.services.provenance_service import get_provenance_service
from app.utils.environment_auth import auth_required_for_llm, auth_optional

logger = logging.getLogger(__name__)


def register_interactive_routes(bp):
    """Register interactive exploration routes on the Step 5 blueprint."""

    @bp.route('/case/<int:case_id>/step5/interactive/start', methods=['POST'])
    @auth_required_for_llm
    def start_interactive_exploration(case_id):
        """Start a new interactive exploration session."""
        try:
            case = Document.query.get_or_404(case_id)

            # Get user_id if authenticated
            from flask_login import current_user
            user_id = current_user.id if current_user.is_authenticated else None

            # Start session
            session = interactive_scenario_service.start_session(case_id, user_id)

            return redirect(url_for('step5.interactive_exploration',
                                   case_id=case_id,
                                   session_uuid=session.session_uuid))

        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('step5.step5_scenario_generation', case_id=case_id))
        except Exception as e:
            logger.error(f"Error starting interactive exploration for case {case_id}: {e}")
            flash('Failed to start interactive exploration', 'error')
            return redirect(url_for('step5.step5_scenario_generation', case_id=case_id))

    @bp.route('/case/<int:case_id>/step5/interactive/start_ajax', methods=['POST'])
    @auth_required_for_llm
    def start_interactive_exploration_ajax(case_id):
        """Start a new interactive exploration session (AJAX version with JSON response)."""
        try:
            case = Document.query.get_or_404(case_id)

            # Get user_id if authenticated
            from flask_login import current_user
            user_id = current_user.id if current_user.is_authenticated else None

            # Start session - this may call LLM for option label generation
            session = interactive_scenario_service.start_session(case_id, user_id)

            return jsonify({
                'success': True,
                'session_uuid': session.session_uuid,
                'redirect_url': url_for('step5.interactive_exploration',
                                        case_id=case_id,
                                        session_uuid=session.session_uuid)
            })

        except ValueError as e:
            logger.warning(f"Cannot start exploration for case {case_id}: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400
        except Exception as e:
            logger.error(f"Error starting interactive exploration for case {case_id}: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': 'Failed to start interactive exploration'
            }), 500

    @bp.route('/case/<int:case_id>/step5/interactive/<session_uuid>')
    @auth_optional
    def interactive_exploration(case_id, session_uuid):
        """Continue an interactive exploration session."""
        try:
            case = Document.query.get_or_404(case_id)
            session = interactive_scenario_service.get_session(session_uuid)

            if not session or session.case_id != case_id:
                flash('Session not found', 'error')
                return redirect(url_for('step5.step5_scenario_generation', case_id=case_id))

            # If completed, redirect to analysis
            if session.status == 'completed':
                return redirect(url_for('step5.interactive_analysis',
                                       case_id=case_id,
                                       session_uuid=session_uuid))

            # Get current decision
            current_decision = interactive_scenario_service.get_current_decision(session)

            if not current_decision:
                # No more decisions - complete and redirect to analysis
                session.status = 'completed'
                session.completed_at = datetime.utcnow()
                db.session.commit()
                return redirect(url_for('step5.interactive_analysis',
                                       case_id=case_id,
                                       session_uuid=session_uuid))

            # Get previous choices for display
            previous_choices = [c.to_dict() for c in session.choices]

            # Get pipeline status for navigation
            pipeline_status = PipelineStatusService.get_step_status(case_id)

            return render_template(
                'scenarios/step5_interactive.html',
                case=case,
                session=session,
                current_decision=current_decision,
                previous_choices=previous_choices,
                current_step=5,
                prev_step_url=f"/scenario_pipeline/case/{case_id}/step5",
                next_step_url="#",
                pipeline_status=pipeline_status
            )

        except Exception as e:
            logger.error(f"Error loading interactive exploration: {e}")
            import traceback
            traceback.print_exc()
            return str(e), 500

    @bp.route('/case/<int:case_id>/step5/interactive/<session_uuid>/choose', methods=['POST'])
    @auth_required_for_llm
    def make_choice(case_id, session_uuid):
        """Process a user's choice at the current decision point."""
        prov = get_provenance_service()

        try:
            session = interactive_scenario_service.get_session(session_uuid)

            if not session or session.case_id != case_id:
                return jsonify({'success': False, 'error': 'Session not found'}), 404

            if session.status != 'in_progress':
                return jsonify({'success': False, 'error': 'Session already completed'}), 400

            # Get choice from request (form data or JSON)
            data = request.get_json(silent=True) or request.form
            chosen_option_index = int(data.get('option_index', 0))
            time_spent = data.get('time_spent_seconds')
            time_spent = int(time_spent) if time_spent else None

            # Process the choice with provenance tracking
            prov_session_id = str(uuid.uuid4())

            with prov.track_activity(
                activity_type='interaction',
                activity_name='step5_user_choice',
                case_id=case_id,
                session_id=prov_session_id,
                agent_type='user_interaction',
                agent_name='interactive_scenario',
                execution_plan={
                    'session_uuid': session_uuid,
                    'chosen_option_index': chosen_option_index,
                    'decision_number': session.current_decision_index + 1
                }
            ) as activity:
                result = interactive_scenario_service.process_choice(
                    session=session,
                    chosen_option_index=chosen_option_index,
                    time_spent_seconds=time_spent
                )

                # Record the choice and consequence
                prov.record_extraction_results(
                    results={
                        'chosen_option_index': chosen_option_index,
                        'consequence_preview': result.get('consequence', '')[:500] if result.get('consequence') else '',
                        'is_complete': result.get('is_complete', False)
                    },
                    activity=activity,
                    entity_type='interactive_choice_result',
                    metadata={'exploration_session': session_uuid}
                )

            # Return JSON for AJAX or redirect for form submission
            if request.is_json:
                return jsonify({
                    'success': True,
                    **result,
                    'redirect_url': (
                        url_for('step5.interactive_analysis', case_id=case_id, session_uuid=session_uuid)
                        if result['is_complete']
                        else url_for('step5.interactive_exploration', case_id=case_id, session_uuid=session_uuid)
                    )
                })
            else:
                if result['is_complete']:
                    return redirect(url_for('step5.interactive_analysis',
                                           case_id=case_id,
                                           session_uuid=session_uuid))
                else:
                    return redirect(url_for('step5.interactive_exploration',
                                           case_id=case_id,
                                           session_uuid=session_uuid))

        except Exception as e:
            logger.error(f"Error processing choice: {e}")
            import traceback
            traceback.print_exc()
            if request.is_json:
                return jsonify({'success': False, 'error': str(e)}), 500
            flash(f'Error processing choice: {e}', 'error')
            return redirect(url_for('step5.interactive_exploration',
                                   case_id=case_id,
                                   session_uuid=session_uuid))

    @bp.route('/case/<int:case_id>/step5/interactive/<session_uuid>/analysis')
    @auth_optional
    def interactive_analysis(case_id, session_uuid):
        """View final analysis comparing user choices to board choices."""
        prov = get_provenance_service()

        try:
            case = Document.query.get_or_404(case_id)
            session = interactive_scenario_service.get_session(session_uuid)

            if not session or session.case_id != case_id:
                flash('Session not found', 'error')
                return redirect(url_for('step5.step5_scenario_generation', case_id=case_id))

            # Generate analysis if not already done
            if not session.final_analysis:
                if session.status == 'completed':
                    # Track the analysis generation with provenance
                    prov_session_id = str(uuid.uuid4())

                    with prov.track_activity(
                        activity_type='synthesis',
                        activity_name='step5_final_analysis',
                        case_id=case_id,
                        session_id=prov_session_id,
                        agent_type='llm_model',
                        agent_name='analysis_generator',
                        execution_plan={
                            'exploration_session': session_uuid,
                            'total_choices': len(session.choices)
                        }
                    ) as activity:
                        analysis = interactive_scenario_service.generate_final_analysis(session)

                        # Record analysis results
                        prov.record_extraction_results(
                            results={
                                'analysis_summary': str(analysis)[:1000] if analysis else '',
                                'choices_count': len(session.choices)
                            },
                            activity=activity,
                            entity_type='exploration_analysis_results',
                            metadata={'exploration_session': session_uuid}
                        )
                else:
                    # Session not complete - redirect back
                    flash('Complete all decisions before viewing analysis', 'warning')
                    return redirect(url_for('step5.interactive_exploration',
                                           case_id=case_id,
                                           session_uuid=session_uuid))
            else:
                analysis = session.final_analysis

            # Get pipeline status for navigation
            pipeline_status = PipelineStatusService.get_step_status(case_id)

            return render_template(
                'scenarios/step5_analysis.html',
                case=case,
                session=session,
                analysis=analysis,
                current_step=5,
                prev_step_url=f"/scenario_pipeline/case/{case_id}/step5",
                next_step_url="#",
                pipeline_status=pipeline_status
            )

        except Exception as e:
            logger.error(f"Error loading analysis: {e}")
            import traceback
            traceback.print_exc()
            return str(e), 500

    @bp.route('/case/<int:case_id>/step5/sessions')
    @auth_optional
    def list_sessions(case_id):
        """List all exploration sessions for a case."""
        try:
            case = Document.query.get_or_404(case_id)

            sessions = ScenarioExplorationSession.query.filter_by(
                case_id=case_id
            ).order_by(ScenarioExplorationSession.started_at.desc()).all()

            # Get pipeline status for navigation
            pipeline_status = PipelineStatusService.get_step_status(case_id)

            return render_template(
                'scenarios/step5_sessions.html',
                case=case,
                sessions=sessions,
                current_step=5,
                prev_step_url=f"/scenario_pipeline/case/{case_id}/step5",
                next_step_url="#",
                pipeline_status=pipeline_status
            )

        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return str(e), 500

    return {
        'start_interactive_exploration': start_interactive_exploration,
        'interactive_exploration': interactive_exploration,
        'make_choice': make_choice,
        'interactive_analysis': interactive_analysis,
        'list_sessions': list_sessions
    }
