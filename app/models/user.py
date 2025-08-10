from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import db

class User(UserMixin, db.Model):
    """User model for authentication."""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True, nullable=False)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    
    # New fields for enhanced user management
    role = db.Column(db.String(20), default='test_user')  # 'admin', 'test_user'
    last_login = db.Column(db.DateTime)
    login_count = db.Column(db.Integer, default=0)
    data_reset_count = db.Column(db.Integer, default=0)
    last_data_reset = db.Column(db.DateTime)

    def __init__(self, username, email, password, is_admin=False, role=None):
        self.username = username
        self.email = email
        self.set_password(password)
        self.is_admin = is_admin
        self.role = role or ('admin' if is_admin else 'test_user')

    def set_password(self, password):
        """Set the password hash from a plaintext password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if the provided password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Return a dictionary representation of the user."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'role': self.role,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'login_count': self.login_count,
            'data_reset_count': self.data_reset_count,
            'last_data_reset': self.last_data_reset.isoformat() if self.last_data_reset else None
        }

    def __repr__(self):
        return f'<User {self.username}>'
