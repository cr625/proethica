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


def test_register_redirects_to_login(client):
    """Test that registration page redirects to login (registration disabled)."""
    response = client.get('/auth/register')
    assert response.status_code == 302


def test_register_shows_closed_message(client):
    """Test that registration shows closed message when following redirect."""
    response = client.get('/auth/register', follow_redirects=True)
    assert response.status_code == 200
    assert b'Registration is currently closed' in response.data


def test_successful_login(client, create_test_user):
    """Test successful login."""
    user = create_test_user(username='testuser', email='test@example.com', password='password123')

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
    user = create_test_user(username='testuser', email='test@example.com', password='password123')

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
    response = auth_client.get('/auth/logout', follow_redirects=True)

    assert response.status_code == 200
    assert b'You have been logged out' in response.data
