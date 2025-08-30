"""
Stub Ontology model - ARCHIVED functionality moved to OntServe.

This stub exists to prevent import errors during the transition period.
Real ontology management now happens in OntServe.
"""

from app.models import db
from datetime import datetime

class Ontology(db.Model):
    """
    STUB MODEL - Original functionality moved to OntServe
    
    This is a minimal stub to prevent import errors.
    For actual ontology operations, use OntServe at http://localhost:5003
    """
    __tablename__ = 'ontologies_stub'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    base_uri = db.Column(db.String(500))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Stub properties for backward compatibility
    @property
    def current_content(self):
        """STUB: Returns placeholder message"""
        return "# ARCHIVED: Ontology content moved to OntServe\n# Visit http://localhost:5003 for ontology management"
    
    @property
    def triple_count(self):
        """STUB: Returns 0"""
        return 0
    
    @property
    def class_count(self):
        """STUB: Returns 0"""
        return 0
    
    @property
    def property_count(self):
        """STUB: Returns 0"""
        return 0
    
    def to_dict(self):
        """STUB: Returns basic dictionary representation"""
        return {
            'id': self.id,
            'name': self.name,
            'base_uri': self.base_uri,
            'description': self.description,
            'message': 'ARCHIVED: This ontology has been moved to OntServe. Visit http://localhost:5003'
        }
    
    @staticmethod
    def query_stub_message():
        """Helper method to show migration message"""
        return "Ontology queries have been moved to OntServe. Please visit http://localhost:5003"

    def __repr__(self):
        return f'<OntologyStub {self.name}>'