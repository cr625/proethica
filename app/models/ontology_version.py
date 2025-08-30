"""
Stub OntologyVersion model - ARCHIVED functionality moved to OntServe.

This stub exists to prevent import errors during the transition period.
Real ontology versioning now happens in OntServe.
"""

from app.models import db
from datetime import datetime

class OntologyVersion(db.Model):
    """
    STUB MODEL - Original functionality moved to OntServe
    
    This is a minimal stub to prevent import errors.
    For actual ontology versioning, use OntServe at http://localhost:5003
    """
    __tablename__ = 'ontology_versions_stub'
    
    id = db.Column(db.Integer, primary_key=True)
    ontology_id = db.Column(db.Integer, db.ForeignKey('ontologies_stub.id'))
    version_number = db.Column(db.Integer, nullable=False)
    version_tag = db.Column(db.String(100))
    content = db.Column(db.Text)
    change_summary = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))
    is_current = db.Column(db.Boolean, default=False)
    is_draft = db.Column(db.Boolean, default=True)
    workflow_status = db.Column(db.String(50), default='draft')
    
    # Stub relationships
    ontology = db.relationship('Ontology', backref='versions_stub')
    
    def to_dict(self):
        """STUB: Returns basic dictionary representation"""
        return {
            'id': self.id,
            'version_number': self.version_number,
            'version_tag': self.version_tag,
            'change_summary': self.change_summary,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by,
            'is_current': self.is_current,
            'message': 'ARCHIVED: Ontology versioning moved to OntServe. Visit http://localhost:5003'
        }
    
    def __repr__(self):
        return f'<OntologyVersionStub {self.ontology_id}:v{self.version_number}>'