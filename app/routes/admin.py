"""
Admin routes for ProEthica Authentication System.

Provides admin-only interfaces for:
- User management
- Test data reset operations
- System statistics and monitoring
- Audit logging
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app.utils.auth_utils import admin_required
from app.services.test_data_reset_service import TestDataResetService
from app.models.user import User
from app.models.world import World
from app.models.document import Document
from app.models.guideline import Guideline
from app.models.scenario import Scenario
from app import db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    """Admin dashboard with system overview and management tools."""
    
    # Get system statistics
    stats = {
        'users': {
            'total': User.query.count(),
            'admin': User.query.filter_by(is_admin=True).count(),
            'test_users': User.query.filter_by(is_admin=False).count(),
            'active_last_30_days': User.query.filter(
                User.last_login >= datetime.utcnow() - timedelta(days=30)
            ).count() if User.query.filter(User.last_login.isnot(None)).count() > 0 else 0
        },
        'data': {
            'total_worlds': World.query.count(),
            'system_worlds': World.query.filter_by(data_type='system').count(),
            'user_worlds': World.query.filter_by(data_type='user').count(),
            'total_documents': Document.query.count(),
            'system_documents': Document.query.filter_by(data_type='system').count(),
            'user_documents': Document.query.filter_by(data_type='user').count(),
            'total_guidelines': Guideline.query.count(),
            'system_guidelines': Guideline.query.filter_by(data_type='system').count(),
            'user_guidelines': Guideline.query.filter_by(data_type='user').count(),
            'total_scenarios': Scenario.query.count()
        }
    }
    
    # Get recent user activity
    recent_users = User.query.order_by(User.last_login.desc().nullslast()).limit(10).all()
    
    # Get users with reset history
    reset_users = User.query.filter(User.data_reset_count > 0).order_by(
        User.last_data_reset.desc()
    ).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         recent_users=recent_users,
                         reset_users=reset_users)

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """User management interface."""
    
    # Get all users with their data counts
    users = User.query.order_by(User.created_at.desc()).all()
    
    # Enhance user data with content counts
    user_data = []
    for user in users:
        user_info = user.to_dict()
        
        # Count user-created content
        user_info['content_counts'] = {
            'worlds': World.query.filter_by(created_by=user.id, data_type='user').count(),
            'documents': Document.query.filter_by(created_by=user.id, data_type='user').count(),
            'guidelines': Guideline.query.filter_by(created_by=user.id, data_type='user').count()
        }
        
        # Calculate total user content
        user_info['total_content'] = sum(user_info['content_counts'].values())
        
        user_data.append(user_info)
    
    return render_template('admin/users.html', users=user_data)

@admin_bp.route('/user/<int:user_id>/summary')
@login_required
@admin_required
def user_data_summary(user_id):
    """Get detailed data summary for a specific user."""
    
    reset_service = TestDataResetService()
    summary = reset_service.get_user_data_summary(user_id)
    
    if 'error' in summary:
        return jsonify({'error': summary['error']}), 404
    
    return jsonify(summary)

@admin_bp.route('/user/<int:user_id>/reset', methods=['POST'])
@login_required
@admin_required
def reset_user_data(user_id):
    """Reset data for a specific user."""
    
    data = request.get_json()
    confirm = data.get('confirm', False)
    dry_run = data.get('dry_run', False)
    
    if not confirm and not dry_run:
        return jsonify({'error': 'Reset must be confirmed or run in dry-run mode'}), 400
    
    reset_service = TestDataResetService()
    result = reset_service.reset_user_data(user_id, confirm=confirm, dry_run=dry_run)
    
    if result.get('success'):
        if not dry_run:
            flash(f"Successfully reset data for user {result['username']}", 'success')
        return jsonify(result)
    else:
        return jsonify(result), 500

@admin_bp.route('/users/bulk-reset', methods=['POST'])
@login_required
@admin_required
def bulk_reset_users():
    """Reset data for all test users."""
    
    data = request.get_json()
    confirm = data.get('confirm', False)
    dry_run = data.get('dry_run', False)
    
    if not confirm and not dry_run:
        return jsonify({'error': 'Bulk reset must be confirmed or run in dry-run mode'}), 400
    
    reset_service = TestDataResetService()
    result = reset_service.bulk_reset_all_test_users(confirm=confirm, dry_run=dry_run)
    
    if result.get('success'):
        if not dry_run:
            flash(f"Successfully reset data for {result['overall_stats']['users_processed']} users", 'success')
        return jsonify(result)
    else:
        return jsonify(result), 500

@admin_bp.route('/data-overview')
@login_required
@admin_required
def data_overview():
    """Detailed data breakdown and management interface."""
    
    # Get counts for each data type
    worlds_total = World.query.count()
    worlds_system = World.query.filter_by(data_type='system').count()
    worlds_user = World.query.filter_by(data_type='user').count()
    
    documents_total = Document.query.count()
    documents_system = Document.query.filter_by(data_type='system').count()
    documents_user = Document.query.filter_by(data_type='user').count()
    
    guidelines_total = Guideline.query.count()
    guidelines_system = Guideline.query.filter_by(data_type='system').count()
    guidelines_user = Guideline.query.filter_by(data_type='user').count()
    
    scenarios_total = Scenario.query.count()
    scenarios_system = Scenario.query.filter_by(data_type='system').count() if hasattr(Scenario, 'data_type') else 0
    scenarios_user = Scenario.query.filter_by(data_type='user').count() if hasattr(Scenario, 'data_type') else scenarios_total
    
    # Structure data to match template expectations
    data_stats = {
        'system': {
            'total': worlds_system + documents_system + guidelines_system + scenarios_system,
            'worlds': worlds_system,
            'documents': documents_system,
            'guidelines': guidelines_system,
            'scenarios': scenarios_system
        },
        'user': {
            'total': worlds_user + documents_user + guidelines_user + scenarios_user,
            'worlds': worlds_user,
            'documents': documents_user,
            'guidelines': guidelines_user,
            'scenarios': scenarios_user
        },
        # Keep additional detailed data for potential future use
        'detailed': {
            'worlds': {
                'total': worlds_total,
                'system': worlds_system,
                'user': worlds_user,
                'by_creator': db.session.query(
                    User.username,
                    db.func.count(World.id).label('count')
                ).join(World, User.id == World.created_by).group_by(User.username).all()
            },
            'documents': {
                'total': documents_total,
                'system': documents_system,
                'user': documents_user,
                'by_type': db.session.query(
                    Document.document_type,
                    db.func.count(Document.id).label('count')
                ).group_by(Document.document_type).all(),
                'cases': Document.query.filter(Document.document_type.ilike('%case%')).count()
            },
            'guidelines': {
                'total': guidelines_total,
                'system': guidelines_system,
                'user': guidelines_user,
                'by_world': db.session.query(
                    World.name,
                    db.func.count(Guideline.id).label('count')
                ).join(Guideline, World.id == Guideline.world_id).group_by(World.name).all()
            }
        }
    }
    
    return render_template('admin/data_overview.html', data_stats=data_stats)

@admin_bp.route('/audit-log')
@login_required
@admin_required
def audit_log():
    """View audit log of admin actions."""
    
    # For now, this is a placeholder
    # In a full implementation, you'd have an audit log table
    # that tracks all admin actions with timestamps and details
    
    audit_entries = [
        {
            'timestamp': datetime.utcnow() - timedelta(hours=2),
            'admin_user': current_user.username,
            'action': 'User Data Reset',
            'target': 'test@proethica.org',
            'details': 'Reset user data: 3 worlds, 5 documents, 2 guidelines deleted'
        },
        {
            'timestamp': datetime.utcnow() - timedelta(days=1),
            'admin_user': current_user.username,
            'action': 'Bulk User Reset',
            'target': 'All test users',
            'details': 'Bulk reset completed: 2 users processed'
        }
    ]
    
    return render_template('admin/audit_log.html', audit_entries=audit_entries)

@admin_bp.route('/system-health')
@login_required
@admin_required
def system_health():
    """System health and diagnostics."""
    
    # Get system statistics
    total_users = User.query.count()
    total_data_items = World.query.count() + Document.query.count() + Guideline.query.count() + Scenario.query.count()
    
    # Calculate approximate uptime (placeholder - in production you'd track actual uptime)
    uptime_hours = 24  # Placeholder value
    
    # Check for any data integrity issues
    alerts = []
    try:
        # Check for unclassified data
        unclassified_worlds = World.query.filter(World.data_type.is_(None)).count()
        unclassified_docs = Document.query.filter(Document.data_type.is_(None)).count()
        unclassified_guidelines = Guideline.query.filter(Guideline.data_type.is_(None)).count()
        
        if unclassified_worlds > 0 or unclassified_docs > 0 or unclassified_guidelines > 0:
            alerts.append({
                'type': 'warning',
                'icon': 'exclamation-triangle',
                'title': 'Data Classification Issue',
                'message': f'Found unclassified data: {unclassified_worlds} worlds, {unclassified_docs} documents, {unclassified_guidelines} guidelines'
            })
        
        # Check for orphaned data
        orphaned_worlds = World.query.filter(World.created_by.is_(None)).count()
        if orphaned_worlds > 0:
            alerts.append({
                'type': 'warning',
                'icon': 'unlink',
                'title': 'Orphaned Data',
                'message': f'Found {orphaned_worlds} worlds without creators'
            })
        
    except Exception as e:
        alerts.append({
            'type': 'danger',
            'icon': 'exclamation-circle',
            'title': 'System Error',
            'message': f'Error checking data integrity: {str(e)}'
        })
    
    # Get recent admin actions (placeholder data)
    recent_admin_actions = [
        {
            'action': 'User Data Reset',
            'timestamp': 'Today at 2:30 PM',
            'status': 'Success',
            'status_color': 'success'
        },
        {
            'action': 'System Health Check',
            'timestamp': 'Today at 1:15 PM',
            'status': 'Complete',
            'status_color': 'info'
        }
    ]
    
    # Get recent user activity (placeholder data)
    recent_user_activity = []
    recent_users = User.query.order_by(User.last_login.desc().nullslast()).limit(5).all()
    for user in recent_users:
        if user.last_login:
            recent_user_activity.append({
                'username': user.username,
                'action': 'Login',
                'timestamp': user.last_login.strftime('%m/%d %I:%M %p'),
                'type': 'login'
            })
    
    # Prepare health statistics
    health_stats = {
        'total_users': total_users,
        'active_sessions': 1,  # Placeholder - would need session tracking
        'total_data_items': total_data_items,
        'system_uptime': uptime_hours,
        'alerts': alerts,
        'db_tables': 15,  # Approximate number of main tables
        'db_connections': 5,  # Placeholder
        'db_response_time': 25,  # Placeholder in ms
        'db_size': 150,  # Placeholder in MB
        'recent_admin_actions': recent_admin_actions,
        'recent_user_activity': recent_user_activity,
        'environment': 'Development',
        'debug_mode': True,  # Would check actual Flask debug mode
        'session_timeout': 30,  # Minutes
        'secure_cookies': False  # Would check actual config
    }
    
    return render_template('admin/system_health.html', health_stats=health_stats)

# Error handlers for admin routes
@admin_bp.errorhandler(403)
def admin_forbidden(error):
    """Handle 403 errors in admin routes."""
    flash('Admin access required for this operation.', 'error')
    return redirect(url_for('index.home'))

@admin_bp.errorhandler(404)
def admin_not_found(error):
    """Handle 404 errors in admin routes."""
    flash('Admin resource not found.', 'error')
    return redirect(url_for('admin.dashboard'))
