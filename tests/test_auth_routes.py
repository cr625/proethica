import json
import pytest
from flask import url_for
from app.models.user import User


def test_login_page(client):
    """Test the login page loads correctly."""
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b'Login' in response.data
    assert b'Username' in response.data
    assert b'Password' in response.data


def test_register_page(client):
    """Test the registration page loads correctly."""
    response = client.get('/auth/register')
    assert response.status_code == 200
    assert b'Register' in response.data
    assert b'Username' in response.data
    assert b'Email' in response.data
    assert b'Password' in response.data
    assert b'Confirm Password' in response.data


def test_successful_registration(client):
    """Test successful user registration."""
    response = client.post('/auth/register', data={
        'username': 'newuser',
        'email': 'newuser@example.com',
        'password': 'password123',
        'confirm_password': 'password123',
        'submit': 'Register'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Login' in response.data
    
    # Verify user was created in the database
    user = User.query.filter_by(username='newuser').first()
    assert user is not None
    assert user.email == 'newuser@example.com'
    assert user.check_password('password123')


def test_registration_with_existing_username(client, create_test_user):
    """Test registration with an existing username."""
    # Create a user
    user = create_test_user(username='existinguser', email='existing@example.com')
    
    # Try to register with the same username
    response = client.post('/auth/register', data={
        'username': 'existinguser',
        'email': 'new@example.com',
        'password': 'password123',
        'confirm_password': 'password123',
        'submit': 'Register'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Username is already taken' in response.data


def test_registration_with_existing_email(client, create_test_user):
    """Test registration with an existing email."""
    # Create a user
    user = create_test_user(username='user1', email='existing@example.com')
    
    # Try to register with the same email
    response = client.post('/auth/register', data={
        'username': 'user2',
        'email': 'existing@example.com',
        'password': 'password123',
        'confirm_password': 'password123',
        'submit': 'Register'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Email is already registered' in response.data


def test_registration_with_mismatched_passwords(client):
    """Test registration with mismatched passwords."""
    response = client.post('/auth/register', data={
        'username': 'newuser',
        'email': 'newuser@example.com',
        'password': 'password123',
        'confirm_password': 'differentpassword',
        'submit': 'Register'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Passwords must match' in response.data


def test_successful_login(client, create_test_user):
    """Test successful login."""
    # Create a user
    user = create_test_user(username='testuser', email='test@example.com', password='password123')
    
    # Login
    response = client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'password123',
        'remember_me': False,
        'submit': 'Sign In'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Login successful!' in response.data


def test_login_with_invalid_username(client):
    """Test login with an invalid username."""
    response = client.post('/auth/login', data={
        'username': 'nonexistentuser',
        'password': 'password123',
        'remember_me': False,
        'submit': 'Sign In'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Invalid username or password' in response.data


def test_login_with_invalid_password(client, create_test_user):
    """Test login with an invalid password."""
    # Create a user
    user = create_test_user(username='testuser', email='test@example.com', password='password123')
    
    # Try to login with wrong password
    response = client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'wrongpassword',
        'remember_me': False,
        'submit': 'Sign In'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Invalid username or password' in response.data


def test_logout(auth_client):
    """Test logout functionality."""
    # The auth_client fixture logs in a user
    
    # Logout
    response = auth_client.get('/auth/logout', follow_redirects=True)
    
    assert response.status_code == 200
    assert b'You have been logged out' in response.data


def test_login_redirect(client, create_test_user):
    """Test that login redirects to the page the user was trying to access."""
    # Create a user
    user = create_test_user(username='testuser', email='test@example.com', password='password123')
    
    # Try to access a protected page
    response = client.get('/scenarios/new', follow_redirects=True)
    
    # Should be redirected to login page
    assert b'Login' in response.data
    
    # Login with next parameter
    response = client.post('/auth/login?next=/scenarios/new', data={
        'username': 'testuser',
        'password': 'password123',
        'remember_me': False,
        'submit': 'Sign In'
    }, follow_redirects=True)
    
    # Should be redirected to the protected page
    assert b'Create New Scenario' in response.data


def test_already_logged_in_redirect(auth_client):
    """Test that logged-in users are redirected from login and register pages."""
    # Try to access login page while logged in
    response = auth_client.get('/auth/login', follow_redirects=True)
    
    # Should be redirected to index
    assert response.status_code == 200
    assert b'Login' not in response.data
    
    # Try to access register page while logged in
    response = auth_client.get('/auth/register', follow_redirects=True)
    
    # Should be redirected to index
    assert response.status_code == 200
    assert b'Register' not in response.data
