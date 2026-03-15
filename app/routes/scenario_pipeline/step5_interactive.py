"""
Step 5 Interactive Exploration Routes

Handles the interactive scenario exploration workflow where users
make choices at decision points and view pre-computed consequences.

Routes:
    /step5/interactive/start - Start new exploration session
    /step5/interactive/<session_uuid> - Continue exploration (traversal)
    /step5/interactive/<session_uuid>/choose - Make a choice
    /step5/interactive/<session_uuid>/summary - Post-traversal summary
    /step5/interactive/<session_uuid>/analysis - Branching analysis (board reveal)
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
from app.utils.environment_auth import auth_required_for_write, auth_optional

logger = logging.getLogger(__name__)


def register_interactive_routes(bp):
    """Register interactive exploration routes on the Step 5 blueprint."""

    @bp.route('/case/<int:case_id>/step5/interactive/start', methods=['POST'])
    @auth_required_for_write
    def start_interactive_exploration(case_id):
        """Start a new interactive exploration session."""
        try:
            case = Document.query.get_or_404(case_id)

            from flask_login import current_user
            user_id = current_user.id if current_user.is_authenticated else None

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
    @auth_required_for_write
    def start_interactive_exploration_ajax(case_id):
        """Start a new interactive exploration session (AJAX version)."""
        try:
            case = Document.query.get_or_404(case_id)

            from flask_login import current_user
            user_id = current_user.id if current_user.is_authenticated else None

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
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Error starting interactive exploration for case {case_id}: {e}", exc_info=True)
            return jsonify({'success': False, 'error': 'Failed to start interactive exploration'}), 500

    @bp.route('/case/<int:case_id>/step5/interactive/<session_uuid>')
    @auth_optional
    def interactive_exploration(case_id, session_uuid):
        """Continue an interactive exploration session (traversal view)."""
        try:
            case = Document.query.get_or_404(case_id)
            session = interactive_scenario_service.get_session(session_uuid)

            if not session or session.case_id != case_id:
                flash('Session not found', 'error')
                return redirect(url_for('step5.step5_scenario_generation', case_id=case_id))

            # If completed, redirect to summary
            if session.status == 'completed':
                return redirect(url_for('step5.interactive_summary',
                                       case_id=case_id,
                                       session_uuid=session_uuid))

            # Get current decision
            current_decision = interactive_scenario_service.get_current_decision(session)

            if not current_decision:
                session.status = 'completed'
                session.completed_at = datetime.utcnow()
                db.session.commit()
                return redirect(url_for('step5.interactive_summary',
                                       case_id=case_id,
                                       session_uuid=session_uuid))

            # Get stepper data and previous choices
            decision_points = interactive_scenario_service.get_all_decision_points_for_stepper(case_id)
            previous_choices = [c.to_dict() for c in session.choices]
            pipeline_status = PipelineStatusService.get_step_status(case_id)

            return render_template(
                'scenarios/step5_traversal.html',
                case=case,
                session=session,
                current_decision=current_decision,
                decision_points=decision_points,
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
    @auth_required_for_write
    def make_choice(case_id, session_uuid):
        """Process a user's choice at the current decision point."""
        prov = get_provenance_service()

        try:
            session = interactive_scenario_service.get_session(session_uuid)

            if not session or session.case_id != case_id:
                return jsonify({'success': False, 'error': 'Session not found'}), 404

            if session.status != 'in_progress':
                return jsonify({'success': False, 'error': 'Session already completed'}), 400

            data = request.get_json(silent=True) or request.form
            chosen_option_index = int(data.get('option_index', 0))
            time_spent = data.get('time_spent_seconds')
            time_spent = int(time_spent) if time_spent else None

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

            # Redirect to summary when complete, otherwise next decision
            if request.is_json:
                redirect_url = (
                    url_for('step5.interactive_summary', case_id=case_id, session_uuid=session_uuid)
                    if result['is_complete']
                    else url_for('step5.interactive_exploration', case_id=case_id, session_uuid=session_uuid)
                )
                return jsonify({'success': True, **result, 'redirect_url': redirect_url})
            else:
                if result['is_complete']:
                    return redirect(url_for('step5.interactive_summary',
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

    @bp.route('/case/<int:case_id>/step5/interactive/<session_uuid>/summary')
    @auth_optional
    def interactive_summary(case_id, session_uuid):
        """Summary page between traversal and analysis (board reveal)."""
        case = Document.query.get_or_404(case_id)
        session = interactive_scenario_service.get_session(session_uuid)

        if not session or session.case_id != case_id:
            flash('Session not found', 'error')
            return redirect(url_for('step5.step5_scenario_generation', case_id=case_id))

        if session.status != 'completed':
            return redirect(url_for('step5.interactive_exploration',
                                   case_id=case_id, session_uuid=session_uuid))

        choices_summary = session.get_choices_summary()
        pipeline_status = PipelineStatusService.get_step_status(case_id)

        return render_template(
            'scenarios/step5_summary.html',
            case=case,
            session=session,
            choices_summary=choices_summary,
            current_step=5,
            pipeline_status=pipeline_status,
        )

    @bp.route('/case/<int:case_id>/step5/interactive/<session_uuid>/analysis')
    @auth_optional
    def interactive_analysis(case_id, session_uuid):
        """View branching analysis comparing user choices to board choices."""
        try:
            case = Document.query.get_or_404(case_id)
            session = interactive_scenario_service.get_session(session_uuid)

            if not session or session.case_id != case_id:
                flash('Session not found', 'error')
                return redirect(url_for('step5.step5_scenario_generation', case_id=case_id))

            if session.status != 'completed':
                flash('Complete all decisions before viewing analysis', 'warning')
                return redirect(url_for('step5.interactive_exploration',
                                       case_id=case_id,
                                       session_uuid=session_uuid))

            # For legacy sessions with stored final_analysis, use that
            if session.final_analysis:
                analysis = session.final_analysis
            else:
                # New sessions: build analysis from Phase 4 data (no LLM)
                analysis = interactive_scenario_service.get_analysis_data(session)

            pipeline_status = PipelineStatusService.get_step_status(case_id)

            return render_template(
                'scenarios/step5_branching_analysis.html',
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
        'interactive_summary': interactive_summary,
        'interactive_analysis': interactive_analysis,
        'list_sessions': list_sessions
    }
