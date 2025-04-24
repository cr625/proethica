from app import db
from datetime import datetime

class OntologyVersion(db.Model):
    """
    Database model for storing ontology versions.
    """
    __tablename__ = 'ontology_versions'
    
    id = db.Column(db.Integer, primary_key=True)
    ontology_id = db.Column(db.Integer, db.ForeignKey('ontologies.id', ondelete='CASCADE'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text)  # Store the actual TTL content of this version
    commit_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with the parent ontology
    ontology = db.relationship('Ontology', backref=db.backref('versions', lazy=True, cascade="all, delete-orphan"))
    
    def __repr__(self):
        return f'<OntologyVersion {self.ontology_id}:v{self.version_number}>'
        
    def to_dict(self):
        return {
            'id': self.id,
            'ontology_id': self.ontology_id,
            'version_number': self.version_number, 
            'commit_message': self.commit_message,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
