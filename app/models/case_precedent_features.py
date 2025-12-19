"""
Case Precedent Features Model

Stores pre-computed features for precedent discovery and matching.
Populated by Step 4 synthesis and used by PrecedentDiscoveryService.

References:
- CBR-RAG (Wiratunga et al., 2024): Case-based reasoning for RAG
- NS-LCR (Sun et al., 2024): Logic rules for legal case retrieval
"""

from datetime import datetime
from app.models import db

try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False
    Vector = None


class CasePrecedentFeatures(db.Model):
    """
    Pre-computed features for efficient precedent matching.

    Populated from:
    - Case ingestion (provisions, tags, outcome)
    - Step 4 Phase 2 (transformation classification)
    - Step 4 Phase 4 (principle tensions, obligation conflicts)
    """
    __tablename__ = 'case_precedent_features'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('documents.id', ondelete='CASCADE'), unique=True)

    # Outcome classification
    outcome_type = db.Column(db.String(50))  # 'ethical', 'unethical', 'mixed', 'unclear'
    outcome_confidence = db.Column(db.Float)
    outcome_reasoning = db.Column(db.Text)

    # NSPE Code provision references
    provisions_cited = db.Column(db.ARRAY(db.String))  # ['I.1', 'II.1.a', 'III.2.b']
    provision_count = db.Column(db.Integer)

    # Subject tags from NSPE website
    subject_tags = db.Column(db.ARRAY(db.String))

    # From Step 4 analysis
    principle_tensions = db.Column(db.JSON)  # [{"principle1": "...", "principle2": "...", "tension_type": "..."}]
    obligation_conflicts = db.Column(db.JSON)  # [{"obligation1": "...", "obligation2": "...", "conflict_type": "..."}]

    # Transformation classification from Step 4
    transformation_type = db.Column(db.String(50))  # 'transfer', 'stalemate', 'oscillation', 'phase_lag'
    transformation_pattern = db.Column(db.Text)

    # Cited cases (for precedent chain tracking)
    cited_case_numbers = db.Column(db.ARRAY(db.String))  # ['Case 92-1', 'Case 88-4']
    cited_case_ids = db.Column(db.ARRAY(db.Integer))  # Resolved document IDs

    # Metadata
    features_version = db.Column(db.Integer, default=1)
    extracted_at = db.Column(db.DateTime, default=datetime.utcnow)
    extraction_method = db.Column(db.String(50))  # 'automatic', 'manual', 'llm_enhanced'
    llm_model_used = db.Column(db.String(100))
    extraction_metadata = db.Column(db.JSON)

    # Relationship to Document
    case = db.relationship('Document', backref=db.backref('precedent_features', uselist=False))

    def __repr__(self):
        return f'<CasePrecedentFeatures case_id={self.case_id} transformation={self.transformation_type}>'

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'outcome_type': self.outcome_type,
            'outcome_confidence': self.outcome_confidence,
            'provisions_cited': self.provisions_cited or [],
            'provision_count': self.provision_count,
            'subject_tags': self.subject_tags or [],
            'principle_tensions': self.principle_tensions or [],
            'obligation_conflicts': self.obligation_conflicts or [],
            'transformation_type': self.transformation_type,
            'cited_case_numbers': self.cited_case_numbers or [],
            'cited_case_ids': self.cited_case_ids or [],
            'extracted_at': self.extracted_at.isoformat() if self.extracted_at else None,
            'extraction_method': self.extraction_method
        }


# Note: Vector columns are defined in the migration (015_create_precedent_features.sql)
# and accessed via raw SQL for similarity queries. SQLAlchemy model provides
# convenient access to non-vector columns.
