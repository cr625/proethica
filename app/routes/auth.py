from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from app import db
from app.models.user import User
from app.forms import LoginForm, RegistrationForm

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

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
            login_user(user, remember=form.remember_me.data)
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
    """Handle user registration."""
    # Redirect if user is already logged in
    if current_user.is_authenticated:
        return redirect(url_for('index.index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Create new user
        user = User(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data
        )
        
        # Add user to database
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index.index'))
