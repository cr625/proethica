"""
Reconciliation Run and Decision models.

Persists reconciliation state so page reloads don't lose results,
and tracks user decisions vs LLM recommendations for learning.
"""

from app.models import db


class ReconciliationRun(db.Model):
    """A single reconciliation run for a case.

    Stores the full candidate list from LLM evaluation so results
    survive page reloads. One run per case (unique constraint).
    """
    __tablename__ = 'reconciliation_runs'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False, unique=True)
    candidates_json = db.Column(db.JSON, nullable=False)
    auto_merged = db.Column(db.Integer, default=0)
    errors_json = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    decisions = db.relationship(
        'ReconciliationDecision',
        backref='run',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )

    def __repr__(self):
        return f'<ReconciliationRun case={self.case_id} candidates={len(self.candidates_json or [])}>'


class ReconciliationDecision(db.Model):
    """A user decision on a single reconciliation candidate pair.

    Records both the LLM recommendation and the user's actual decision,
    enabling analysis of agreement patterns across cases.
    """
    __tablename__ = 'reconciliation_decisions'

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('reconciliation_runs.id'), nullable=False)
    entity_a_id = db.Column(db.Integer, nullable=False)
    entity_b_id = db.Column(db.Integer, nullable=False)
    entity_a_label = db.Column(db.String(500))
    entity_b_label = db.Column(db.String(500))
    llm_recommendation = db.Column(db.String(20))
    llm_reason = db.Column(db.Text)
    user_decision = db.Column(db.String(20))
    merge_snapshots_json = db.Column(db.JSON)
    similarity = db.Column(db.Float)
    entity_a_context = db.Column(db.JSON)
    entity_b_context = db.Column(db.JSON)
    decided_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=db.func.now())

    def __repr__(self):
        return (
            f'<ReconciliationDecision {self.entity_a_label} vs {self.entity_b_label} '
            f'llm={self.llm_recommendation} user={self.user_decision}>'
        )
