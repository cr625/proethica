from datetime import datetime, timezone
from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from app import db
from app.models.user import User
from app.forms import LoginForm, RegistrationForm

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def _log_auth_activity(action: str, user_id: int = None, username: str = None):
    """Log authentication activity."""
    try:
        from app.utils.activity_tracker import log_activity
        log_activity(
            action=action,
            category='auth',
            user_id=user_id,
            username=username,
            path=request.path,
            method=request.method,
            remote_addr=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')
        )
    except Exception:
        pass  # Don't break auth flow for logging

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    # Redirect if user is already logged in
    if current_user.is_authenticated:
        return redirect(url_for('index.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # Find the user by username or email
        login_input = form.username.data
        user = User.query.filter(
            (User.username == login_input) | (User.email == login_input)
        ).first()
        
        # Check if user exists and password is correct
        if user and user.check_password(form.password.data):
            # Update login tracking
            user.last_login = datetime.now(timezone.utc)
            user.login_count = (user.login_count or 0) + 1
            db.session.commit()

            login_user(user, remember=form.remember_me.data)
            _log_auth_activity('Login', user_id=user.id, username=user.username)
            flash('Login successful!', 'success')
            
            # Redirect to the page the user was trying to access
            next_page = request.args.get('next')
            if next_page:
                # Handle full URLs by extracting just the path
                parsed = urlparse(next_page)
                # Security: only allow relative URLs (same host)
                if parsed.netloc and parsed.netloc != request.host:
                    next_page = None
                elif parsed.path:
                    # Use path with query string if present
                    next_page = parsed.path
                    if parsed.query:
                        next_page += '?' + parsed.query
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('index.index')
            return redirect(next_page)
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registration is disabled - accounts are created by admin."""
    flash('Registration is currently closed. Please contact the administrator for an account.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    _log_auth_activity('Logout', user_id=current_user.id, username=current_user.username)
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index.index'))
