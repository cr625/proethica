from app import db
from datetime import datetime

class OntologyImport(db.Model):
    """
    Database model for storing ontology import relationships.
    
    This model represents import relationships between ontologies,
    where one ontology imports/extends another.
    """
    __tablename__ = 'ontology_imports'

    id = db.Column(db.Integer, primary_key=True)
    importing_ontology_id = db.Column(db.Integer, db.ForeignKey('ontologies.id', ondelete='CASCADE'), nullable=False)
    imported_ontology_id = db.Column(db.Integer, db.ForeignKey('ontologies.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship with the imported ontology
    imported_ontology = db.relationship('Ontology', 
                                        foreign_keys=[imported_ontology_id],
                                        backref=db.backref('imported_by', lazy=True))

    def __repr__(self):
        return f'<OntologyImport {self.importing_ontology_id} imports {self.imported_ontology_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'importing_ontology_id': self.importing_ontology_id,
            'imported_ontology_id': self.imported_ontology_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
