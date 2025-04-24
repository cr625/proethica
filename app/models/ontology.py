from app import db
from datetime import datetime
import json

class Ontology(db.Model):
    """
    Database model for storing ontologies.
    """
    __tablename__ = 'ontologies'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    domain_id = db.Column(db.String(100), nullable=False, unique=True)
    content = db.Column(db.Text)  # Store the actual TTL content in the database
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    worlds = db.relationship('World', backref='ontology_obj', lazy=True)
    
    def __repr__(self):
        return f'<Ontology {self.name}>'
        
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'domain_id': self.domain_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
