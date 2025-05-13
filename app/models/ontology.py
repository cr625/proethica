from app.models import db
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
    
    # New fields for ontology type and editing control
    is_base = db.Column(db.Boolean, default=False)  # True for BFO, intermediate ontologies
    is_editable = db.Column(db.Boolean, default=True)  # False for base ontologies
    base_uri = db.Column(db.String(255), nullable=True)  # URI defining the ontology
    
    # Relationships
    worlds = db.relationship('World', backref='ontology_obj', lazy=True)
    
    # Importing relationships managed through OntologyImport model
    imports = db.relationship('OntologyImport',
                             foreign_keys='OntologyImport.importing_ontology_id',
                             backref='importing_ontology',
                             lazy='dynamic',
                             cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Ontology {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'domain_id': self.domain_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_base': self.is_base,
            'is_editable': self.is_editable,
            'base_uri': self.base_uri
        }
    
    def get_imported_ontologies(self):
        """
        Get all ontologies imported by this ontology.
        """
        return [import_rel.imported_ontology for import_rel in self.imports]
    
    def add_import(self, imported_ontology):
        """
        Add an import relationship to another ontology.
        
        Args:
            imported_ontology: The ontology to import
        """
        from app.models.ontology_import import OntologyImport
        
        # Check if import already exists
        for import_rel in self.imports:
            if import_rel.imported_ontology_id == imported_ontology.id:
                return  # Already imported
        
        # Create new import relationship
        import_rel = OntologyImport(
            importing_ontology=self,
            imported_ontology=imported_ontology
        )
        db.session.add(import_rel)
