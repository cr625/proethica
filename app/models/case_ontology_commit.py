"""
Case Ontology Commit Model

Records which OntServe ontology version was current when a case's entities
were committed. Used for Shepard's signal version binding -- determines
which version to link to for superseded/deprecated entities.
"""

from datetime import datetime, timezone
from app.models import db


class CaseOntologyCommit(db.Model):
    """Tracks ontology version state at the time of case entity commits."""

    __tablename__ = 'case_ontology_commits'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False, index=True)
    ontology_name = db.Column(db.String(100), nullable=False)  # e.g. 'proethica-intermediate'
    ontserve_version_id = db.Column(db.Integer)  # OntServe ontology_versions.id at commit time
    version_tag = db.Column(db.String(50))  # Version tag if one existed (e.g. 'v1.0.0')
    committed_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    entity_count = db.Column(db.Integer, default=0)  # Number of entities committed

    # Relationships
    case = db.relationship('Document', backref='ontology_commits', lazy=True)

    __table_args__ = (
        db.Index('idx_case_ontology_commit', 'case_id', 'ontology_name'),
    )

    def __repr__(self):
        return f'<CaseOntologyCommit case={self.case_id} ontology={self.ontology_name} tag={self.version_tag}>'
