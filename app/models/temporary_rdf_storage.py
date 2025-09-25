"""
Temporary RDF Storage Model

Database model for storing temporary RDF triples from LLM extractions
before they are committed to the permanent ontologies.
"""

from datetime import datetime
from app.models import db


class TemporaryRDFStorage(db.Model):
    """
    Store temporary RDF triples for review before committing to ontologies.

    This model stores both new classes (for proethica-intermediate) and
    new individuals (for case-specific ontologies) as RDF triples.
    """

    __tablename__ = 'temporary_rdf_storage'

    id = db.Column(db.Integer, primary_key=True)

    # Case and extraction context
    case_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    extraction_session_id = db.Column(db.String(100), nullable=False, index=True)
    extraction_type = db.Column(db.String(50))  # 'roles', 'states', etc.

    # RDF storage type
    storage_type = db.Column(db.String(20), nullable=False)  # 'class' or 'individual'
    ontology_target = db.Column(db.String(100))  # 'proethica-intermediate' or 'proethica-case-N'

    # RDF content
    rdf_turtle = db.Column(db.Text)  # Turtle serialization of the RDF graph
    rdf_json_ld = db.Column(db.JSON)  # JSON-LD representation for easier manipulation

    # Extracted entity information for display
    entity_label = db.Column(db.String(255), index=True)
    entity_uri = db.Column(db.String(500))
    entity_type = db.Column(db.String(100))  # Role, State, etc.
    entity_definition = db.Column(db.Text)

    # Review status
    is_selected = db.Column(db.Boolean, default=False)
    is_reviewed = db.Column(db.Boolean, default=False)
    is_committed = db.Column(db.Boolean, default=False)
    review_notes = db.Column(db.Text)

    # Provenance
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))
    extraction_model = db.Column(db.String(100))  # Which LLM model was used

    # Statistics
    triple_count = db.Column(db.Integer, default=0)
    property_count = db.Column(db.Integer, default=0)
    relationship_count = db.Column(db.Integer, default=0)

    # Relationships
    case = db.relationship('Document', backref='temporary_rdf_entities', lazy=True)

    def __repr__(self):
        return f'<TemporaryRDFStorage {self.entity_label} ({self.storage_type}) for case {self.case_id}>'

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'extraction_session_id': self.extraction_session_id,
            'extraction_type': self.extraction_type,
            'storage_type': self.storage_type,
            'ontology_target': self.ontology_target,
            'entity_label': self.entity_label,
            'entity_uri': self.entity_uri,
            'entity_type': self.entity_type,
            'entity_definition': self.entity_definition,
            'is_selected': self.is_selected,
            'is_reviewed': self.is_reviewed,
            'is_committed': self.is_committed,
            'review_notes': self.review_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'extraction_model': self.extraction_model,
            'triple_count': self.triple_count,
            'property_count': self.property_count,
            'relationship_count': self.relationship_count,
            'rdf_json_ld': self.rdf_json_ld
        }

    @classmethod
    def clear_case_session(cls, case_id: int, extraction_session_id: str = None):
        """
        Clear temporary RDF storage for a case or specific session.

        Args:
            case_id: The case ID to clear
            extraction_session_id: Optional specific session to clear
        """
        query = cls.query.filter_by(case_id=case_id, is_committed=False)

        if extraction_session_id:
            query = query.filter_by(extraction_session_id=extraction_session_id)

        count = query.count()
        query.delete()
        db.session.commit()

        return count

    @classmethod
    def get_case_entities(cls, case_id: int, storage_type: str = None, is_selected: bool = None):
        """
        Get temporary RDF entities for a case.

        Args:
            case_id: The case ID
            storage_type: Optional filter for 'class' or 'individual'
            is_selected: Optional filter for selected entities

        Returns:
            List of TemporaryRDFStorage objects
        """
        query = cls.query.filter_by(case_id=case_id, is_committed=False)

        if storage_type:
            query = query.filter_by(storage_type=storage_type)

        if is_selected is not None:
            query = query.filter_by(is_selected=is_selected)

        return query.order_by(cls.created_at.desc()).all()

    @classmethod
    def store_extraction_results(cls, case_id: int, extraction_session_id: str,
                                extraction_type: str, rdf_data: dict,
                                extraction_model: str = None):
        """
        Store RDF extraction results from the converter.

        Args:
            case_id: The case ID
            extraction_session_id: Unique session identifier
            extraction_type: Type of extraction (roles, states, etc.)
            rdf_data: Dictionary containing classes and individuals from RDF converter
            extraction_model: LLM model used for extraction

        Returns:
            List of created TemporaryRDFStorage objects
        """
        created_entities = []

        # Clear any existing temporary entities for this case and extraction type
        # (as per requirement to replace old temporary ones of the same type)
        cls.query.filter_by(
            case_id=case_id,
            extraction_type=extraction_type,
            is_committed=False
        ).delete()

        # Store new classes
        for class_info in rdf_data.get('new_classes', []):
            # Clean the class_info to ensure all values are JSON-serializable
            clean_class_info = cls._clean_json_data(class_info)

            entity = cls(
                case_id=case_id,
                extraction_session_id=extraction_session_id,
                extraction_type=extraction_type,
                storage_type='class',
                ontology_target='proethica-intermediate',
                entity_label=class_info['label'],
                entity_uri=class_info['uri'],
                entity_type=extraction_type.capitalize(),
                entity_definition=class_info.get('definition', ''),
                rdf_json_ld=clean_class_info,
                extraction_model=extraction_model,
                triple_count=len(class_info.get('properties', {})) + 4,  # Basic triples
                property_count=len(class_info.get('properties', {}))
            )
            db.session.add(entity)
            created_entities.append(entity)

        # Store individuals
        for indiv_info in rdf_data.get('new_individuals', []):
            # Clean the indiv_info to ensure all values are JSON-serializable
            clean_indiv_info = cls._clean_json_data(indiv_info)

            entity = cls(
                case_id=case_id,
                extraction_session_id=extraction_session_id,
                extraction_type=extraction_type,
                storage_type='individual',
                ontology_target=f'proethica-case-{case_id}',
                entity_label=indiv_info['label'],
                entity_uri=indiv_info['uri'],
                entity_type=extraction_type.capitalize(),
                entity_definition='',  # Individuals don't have definitions
                rdf_json_ld=clean_indiv_info,
                extraction_model=extraction_model,
                triple_count=len(indiv_info.get('properties', {})) + len(indiv_info.get('relationships', [])) + 2,
                property_count=len(indiv_info.get('properties', {})),
                relationship_count=len(indiv_info.get('relationships', []))
            )
            db.session.add(entity)
            created_entities.append(entity)

        db.session.commit()
        return created_entities

    @classmethod
    def _clean_json_data(cls, data):
        """Clean data to ensure it's JSON-serializable.

        Removes any callable methods or non-serializable objects that might
        have accidentally been included in the data.
        """
        import json

        def clean_value(value):
            """Recursively clean a value for JSON serialization."""
            if callable(value):
                # Skip callable objects (methods, functions)
                return None
            elif isinstance(value, dict):
                # Recursively clean dictionary
                return {k: clean_value(v) for k, v in value.items() if clean_value(v) is not None}
            elif isinstance(value, (list, tuple)):
                # Recursively clean list/tuple
                cleaned = [clean_value(v) for v in value]
                return [v for v in cleaned if v is not None]
            elif isinstance(value, (str, int, float, bool, type(None))):
                # These types are JSON-serializable
                return value
            else:
                # Try to convert to string for other types
                try:
                    # Check if it's a built-in method or similar
                    str_val = str(value)
                    if 'built-in method' in str_val or 'method' in str_val:
                        return None
                    return str_val
                except:
                    return None

        return clean_value(data)