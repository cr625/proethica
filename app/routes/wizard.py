"""
Routes for the wizard functionality.

This module provides interactive wizard-style navigation through ethical scenarios
with session management, step progression, and choice tracking.
"""

import logging
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models.scenario import Scenario
from app.models.wizard import WizardStep, UserWizardSession
from app.services.wizard_controller import WizardController
from app import db

# Set up logging
logger = logging.getLogger(__name__)

# Create blueprint
wizard_bp = Blueprint('wizard', __name__, url_prefix='/scenarios')

# Initialize wizard controller
wizard_controller = WizardController()


@wizard_bp.route('/<int:id>/wizard', methods=['GET'])
@login_required
def start_or_resume_wizard(id):
    """Start a new wizard session or resume an existing one."""
    try:
        # Verify scenario exists
        scenario = Scenario.query.get_or_404(id)
        
        # Get current user
        # current_user is now directly available from flask_login
        user_id = current_user.id
        
        # Get or create session
        wizard_session = wizard_controller.get_or_create_session(user_id, id)
        
        # Generate wizard steps if they don't exist
        existing_steps = WizardStep.query.filter_by(scenario_id=id).count()
        if existing_steps == 0:
            steps = wizard_controller.generate_wizard_steps(id)
            for step in steps:
                db.session.add(step)
            db.session.commit()
            
            # Update session total_steps if needed
            wizard_session.total_steps = len(steps)
            db.session.commit()
        
        # Store session ID in Flask session for convenience
        session['wizard_session_id'] = wizard_session.id
        
        # Always render the wizard start page
        return render_template('wizard/wizard_start.html',
                             scenario=scenario,
                             wizard_session=wizard_session,
                             current_step=wizard_session.current_step,
                             total_steps=wizard_session.total_steps)
        
    except Exception as e:
        logger.error(f"Error starting/resuming wizard session: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error starting wizard session: {str(e)}'
        }), 500


@wizard_bp.route('/<int:id>/wizard/step/<int:step_number>', methods=['GET'])
@login_required
def get_step_content(id, step_number):
    """Get content for a specific wizard step."""
    try:
        # Verify scenario exists
        scenario = Scenario.query.get_or_404(id)
        
        # Get current user and session
        # current_user is now directly available from flask_login
        user_id = current_user.id
        
        # Get active session
        wizard_session = UserWizardSession.query.filter_by(
            user_id=user_id,
            scenario_id=id,
            session_status='active'
        ).first()
        
        if not wizard_session:
            return jsonify({
                'status': 'error',
                'message': 'No active wizard session found. Please start a new session.'
            }), 404
        
        # Validate step number
        if step_number < 1 or step_number > wizard_session.total_steps:
            return jsonify({
                'status': 'error',
                'message': f'Invalid step number. Must be between 1 and {wizard_session.total_steps}'
            }), 400
        
        # Get step content
        step_content = wizard_controller.get_step_content(id, step_number)
        
        if not step_content:
            return jsonify({
                'status': 'error',
                'message': f'Step {step_number} not found'
            }), 404
        
        # Add session context
        session_context = {
            'current_step': wizard_session.current_step,
            'total_steps': wizard_session.total_steps,
            'progress_percentage': round(
                (step_number - 1) / wizard_session.total_steps * 100 if wizard_session.total_steps else 0, 1
            ),
            'can_go_back': step_number > 1,
            'can_go_forward': step_number < wizard_session.total_steps,
            'user_choice': wizard_session.choices.get(str(step_number)) if wizard_session.choices else None
        }
        
        # Render the timeline-specific step template
        return render_template('wizard/wizard_step_timeline.html',
                             scenario=scenario,
                             wizard_session=wizard_session,
                             step=step_content,  # Template expects 'step', not 'step_content'
                             step_number=step_number,
                             session=session_context)  # Template expects 'session', not 'session_context'
        
    except Exception as e:
        logger.error(f"Error getting step content: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error getting step content: {str(e)}'
        }), 500


@wizard_bp.route('/<int:id>/wizard/step/<int:step_number>/choice', methods=['POST'])
@login_required
def submit_choice(id, step_number):
    """Submit a user's choice for a decision step."""
    try:
        # Verify scenario exists
        scenario = Scenario.query.get_or_404(id)
        
        # Get request data
        data = request.json
        if not data or 'option_id' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing option_id in request'
            }), 400
        
        option_id = data['option_id']
        
        # Get current user and session
        # current_user is now directly available from flask_login
        user_id = current_user.id
        
        # Get active session
        wizard_session = UserWizardSession.query.filter_by(
            user_id=user_id,
            scenario_id=id,
            session_status='active'
        ).first()
        
        if not wizard_session:
            return jsonify({
                'status': 'error',
                'message': 'No active wizard session found'
            }), 404
        
        # Validate step number
        if step_number < 1 or step_number > wizard_session.total_steps:
            return jsonify({
                'status': 'error',
                'message': f'Invalid step number. Must be between 1 and {wizard_session.total_steps}'
            }), 400
        
        # Verify this is a decision step
        step = WizardStep.query.filter_by(
            scenario_id=id,
            step_number=step_number,
            step_type='decision'
        ).first()
        
        if not step:
            return jsonify({
                'status': 'error',
                'message': f'Step {step_number} is not a decision step'
            }), 400
        
        # Record the choice
        success = wizard_controller.record_choice(wizard_session, step_number, option_id)
        
        if not success:
            return jsonify({
                'status': 'error',
                'message': 'Failed to record choice'
            }), 500
        
        # Update session progress if this is the current step
        if step_number == wizard_session.current_step:
            wizard_session.advance_step()
            db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Choice recorded successfully',
            'data': {
                'option_id': option_id,
                'step_number': step_number,
                'session': wizard_session.to_dict()
            }
        })
        
    except Exception as e:
        logger.error(f"Error submitting choice: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error submitting choice: {str(e)}'
        }), 500


@wizard_bp.route('/<int:id>/wizard/navigate', methods=['POST'])
@login_required
def navigate_wizard(id):
    """Navigate to next/previous step in the wizard."""
    try:
        # Verify scenario exists
        scenario = Scenario.query.get_or_404(id)
        
        # Get request data
        data = request.json
        if not data or 'direction' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing direction in request (must be "next" or "previous")'
            }), 400
        
        direction = data['direction']
        if direction not in ['next', 'previous']:
            return jsonify({
                'status': 'error',
                'message': 'Direction must be "next" or "previous"'
            }), 400
        
        # Get current user and session
        # current_user is now directly available from flask_login
        user_id = current_user.id
        
        # Get active session
        wizard_session = UserWizardSession.query.filter_by(
            user_id=user_id,
            scenario_id=id,
            session_status='active'
        ).first()
        
        if not wizard_session:
            return jsonify({
                'status': 'error',
                'message': 'No active wizard session found'
            }), 404
        
        # Perform navigation
        if direction == 'next':
            success = wizard_controller.advance_session(wizard_session)
            if not success:
                # Check if we've reached the end
                if wizard_session.current_step >= wizard_session.total_steps:
                    # Complete the session
                    wizard_session.complete_session()
                    db.session.commit()
                    
                    return jsonify({
                        'status': 'success',
                        'message': 'Wizard completed',
                        'data': {
                            'session': wizard_session.to_dict(),
                            'completed': True
                        }
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': 'Cannot advance further'
                    }), 400
        else:  # previous
            success = wizard_controller.go_back(wizard_session)
            if not success:
                return jsonify({
                    'status': 'error',
                    'message': 'Cannot go back further'
                }), 400
        
        return jsonify({
            'status': 'success',
            'message': f'Navigated {direction} successfully',
            'data': {
                'session': wizard_session.to_dict()
            }
        })
        
    except Exception as e:
        logger.error(f"Error navigating wizard: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error navigating wizard: {str(e)}'
        }), 500


@wizard_bp.route('/<int:id>/wizard/summary', methods=['GET'])
@login_required
def view_summary(id):
    """View summary of wizard completion and choices."""
    try:
        # Verify scenario exists
        scenario = Scenario.query.get_or_404(id)
        
        # Get current user and session
        # current_user is now directly available from flask_login
        user_id = current_user.id
        
        # Get session (can be active or completed)
        wizard_session = UserWizardSession.query.filter_by(
            user_id=user_id,
            scenario_id=id
        ).order_by(UserWizardSession.last_accessed_at.desc()).first()
        
        if not wizard_session:
            return jsonify({
                'status': 'error',
                'message': 'No wizard session found'
            }), 404
        
        # Generate summary
        summary = wizard_controller.generate_summary(wizard_session)
        
        # Add scenario context
        summary['scenario'] = {
            'id': scenario.id,
            'name': scenario.name,
            'description': scenario.description
        }
        
        # Add session info
        summary['session'] = wizard_session.to_dict()
        
        return jsonify({
            'status': 'success',
            'data': summary
        })
        
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error generating summary: {str(e)}'
        }), 500


# Additional utility routes

@wizard_bp.route('/<int:id>/wizard/session', methods=['GET'])
@login_required
def get_session_status(id):
    """Get current session status and progress."""
    try:
        # Verify scenario exists
        scenario = Scenario.query.get_or_404(id)
        
        # Get current user
        # current_user is now directly available from flask_login
        user_id = current_user.id
        
        # Get active session
        wizard_session = UserWizardSession.query.filter_by(
            user_id=user_id,
            scenario_id=id,
            session_status='active'
        ).first()
        
        if not wizard_session:
            return jsonify({
                'status': 'success',
                'data': {
                    'has_active_session': False,
                    'message': 'No active session found'
                }
            })
        
        return jsonify({
            'status': 'success',
            'data': {
                'has_active_session': True,
                'session': wizard_session.to_dict()
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting session status: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error getting session status: {str(e)}'
        }), 500


@wizard_bp.route('/<int:id>/wizard/reset', methods=['POST'])
@login_required
def reset_wizard_session(id):
    """Reset/restart the wizard session."""
    try:
        # Verify scenario exists
        scenario = Scenario.query.get_or_404(id)
        
        # Get current user
        # current_user is now directly available from flask_login
        user_id = current_user.id
        
        # Get existing session
        existing_session = UserWizardSession.query.filter_by(
            user_id=user_id,
            scenario_id=id,
            session_status='active'
        ).first()
        
        if existing_session:
            # Mark existing session as abandoned
            existing_session.session_status = 'abandoned'
            db.session.commit()
        
        # Create new session
        new_session = wizard_controller.get_or_create_session(user_id, id)
        
        # Store session ID in Flask session
        session['wizard_session_id'] = new_session.id
        
        return jsonify({
            'status': 'success',
            'message': 'Wizard session reset successfully',
            'data': {
                'session': new_session.to_dict(),
                'scenario': {
                    'id': scenario.id,
                    'name': scenario.name,
                    'description': scenario.description
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Error resetting wizard session: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error resetting wizard session: {str(e)}'
        }), 500