"""
Temporary RDF Storage Model

Database model for storing temporary RDF triples from LLM extractions
before they are published to the permanent ontologies.

Draft/Publish Workflow (2025-12-10):
- Entities start as drafts (is_published=False)
- Published to OntServe at end of Step 4 (core entities) or Step 6 (analysis)
- Re-extraction clears unpublished entities of same type
"""

import hashlib
import logging
from datetime import datetime, timezone
from app.models import db

logger = logging.getLogger(__name__)


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
    is_selected = db.Column(db.Boolean, default=True)
    is_reviewed = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=False)  # Renamed from is_published (2025-12-10)
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

    # IAO Document References (Phase 1 - Added 2025-10-07)
    iao_document_uri = db.Column(db.String(500))  # URI of IAO document (iao:0000300 or iao:0000310)
    iao_document_label = db.Column(db.String(500))  # Human-readable label (e.g., "NSPE Code Section II.4.a")
    iao_document_type = db.Column(db.String(50))  # 'document' or 'document_part'
    cited_by_role = db.Column(db.String(200))  # Which role cited this (for References section)
    available_to_role = db.Column(db.String(200))  # Which role has access (for case context)

    # PROV-O Provenance Metadata (Added 2025-10-12)
    provenance_metadata = db.Column(db.JSON)  # Provenance tracking (activity_id, section_type, match_reasoning, etc.)

    # OntServe Class Matching (Added 2025-12-01 for Entity-Ontology Linking)
    matched_ontology_uri = db.Column(db.String(500))  # URI of matched OntServe class
    matched_ontology_label = db.Column(db.String(255))  # Label of matched OntServe class
    match_confidence = db.Column(db.Float)  # Confidence score 0.0-1.0
    match_method = db.Column(db.String(50))  # 'llm', 'embedding', 'exact_label', 'user_override'
    match_reasoning = db.Column(db.Text)  # Explanation of why this match was made

    # Entity Versioning / Shepard's Signals (Added 2026-03-08)
    content_hash = db.Column(db.String(64))  # SHA-256 of uri|label|definition at commit time
    committed_at = db.Column(db.DateTime(timezone=True))  # When committed to OntServe
    shepard_signal = db.Column(db.String(20))  # current, superseded, distinguished, deprecated
    signal_checked_at = db.Column(db.DateTime(timezone=True))  # Last signal check time

    # Relationships
    case = db.relationship('Document', backref='temporary_rdf_entities', lazy=True)

    @staticmethod
    def compute_content_hash(uri: str, label: str = None, definition: str = None) -> str:
        """Compute SHA-256 content hash for entity version comparison.

        Must produce identical output to OntologyEntity.compute_content_hash
        in OntServe's web/models.py.
        """
        raw = f"{uri}|{label or ''}|{definition or ''}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def __repr__(self):
        return f'<TemporaryRDFStorage {self.entity_label} ({self.storage_type}) for case {self.case_id}>'

    def to_dict(self):
        """Convert to dictionary for API responses"""
        # Clean the rdf_json_ld data to ensure it's properly serializable
        clean_rdf = self._ensure_serializable(self.rdf_json_ld) if self.rdf_json_ld else None

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
            'is_published': self.is_published,
            'review_notes': self.review_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'extraction_model': self.extraction_model,
            'triple_count': self.triple_count,
            'property_count': self.property_count,
            'relationship_count': self.relationship_count,
            'rdf_json_ld': clean_rdf,
            # IAO document references
            'iao_document_uri': self.iao_document_uri,
            'iao_document_label': self.iao_document_label,
            'iao_document_type': self.iao_document_type,
            'cited_by_role': self.cited_by_role,
            'available_to_role': self.available_to_role,
            # PROV-O provenance metadata
            'provenance_metadata': self.provenance_metadata,
            # OntServe class matching
            'matched_ontology_uri': self.matched_ontology_uri,
            'matched_ontology_label': self.matched_ontology_label,
            'match_confidence': self.match_confidence,
            'match_method': self.match_method,
            'match_reasoning': self.match_reasoning
        }

    def _ensure_serializable(self, data):
        """Ensure data is JSON serializable, converting dict_values and similar objects."""
        if isinstance(data, dict):
            return {k: self._ensure_serializable(v) for k, v in data.items()}
        elif isinstance(data, (list, tuple)):
            return [self._ensure_serializable(item) for item in data]
        elif hasattr(data, '__iter__') and not isinstance(data, (str, bytes)):
            # This catches dict_values, dict_keys, etc.
            try:
                return list(data)
            except Exception:
                logger.debug("Failed to convert iterable to list, using str()", exc_info=True)
                return str(data)
        else:
            return data

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
        query = cls.query.filter_by(case_id=case_id, is_published=False)

        if storage_type:
            query = query.filter_by(storage_type=storage_type)

        if is_selected is not None:
            query = query.filter_by(is_selected=is_selected)

        return query.order_by(cls.created_at.desc()).all()

    @classmethod
    def store_extraction_results(cls, case_id, extraction_session_id,
                                extraction_type, rdf_data,
                                extraction_model=None, provenance_data=None):
        """Delegate to rdf_storage_service. Commits for backward compatibility."""
        from app.services.rdf_storage_service import store_extraction_results as _store
        result = _store(
            case_id=case_id,
            extraction_session_id=extraction_session_id,
            extraction_type=extraction_type,
            rdf_data=rdf_data,
            extraction_model=extraction_model,
            provenance_data=provenance_data,
        )
        db.session.commit()
        return result