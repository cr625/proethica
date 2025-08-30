"""
Stub OntologyImport model - ARCHIVED functionality moved to OntServe.

This stub exists to prevent import errors during the transition period.
Real ontology importing now happens in OntServe.
"""

from app.models import db
from datetime import datetime

class OntologyImport(db.Model):
    """
    STUB MODEL - Original functionality moved to OntServe
    
    This is a minimal stub to prevent import errors.
    For actual ontology importing, use OntServe at http://localhost:5003
    """
    __tablename__ = 'ontology_imports_stub'
    
    id = db.Column(db.Integer, primary_key=True)
    source_url = db.Column(db.String(500))
    source_type = db.Column(db.String(50))  # 'url', 'file', 'text'
    import_status = db.Column(db.String(50), default='archived')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """STUB: Returns basic dictionary representation"""
        return {
            'id': self.id,
            'source_url': self.source_url,
            'source_type': self.source_type,
            'import_status': 'archived',
            'message': 'ARCHIVED: Ontology importing moved to OntServe. Visit http://localhost:5003/import'
        }
    
    def __repr__(self):
        return f'<OntologyImportStub {self.id}>'