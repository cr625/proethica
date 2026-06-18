"""Commit-time index of per-case defeated-obligation patterns.

Populated from each case's committed TTL after edge materialization, so the
cross-case defeasibility band can rank comparable cases without scanning every
case TTL per request (ROADMAP Section A, 2026-06-05). One row per resolved
``prevailsOver`` (winner, loser) pair, carrying the licensing State context and
a precomputed all-MiniLM-L6-v2 embedding of the loser-obligation label for
similarity ranking.

The table is a derived cache: it can be rebuilt at any time from the committed
TTLs by ``docs-internal/scripts/backfill_defeasibility_band_index.py``.
"""
from datetime import datetime

from app.models import db


class DefeasibilityBandIndex(db.Model):
    __tablename__ = 'defeasibility_band_index'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(
        db.Integer,
        db.ForeignKey('documents.id', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    # The resolved conflict: winner prevailsOver loser; loser defeasibleUnder contexts.
    winner_label = db.Column(db.String(512))
    loser_label = db.Column(db.String(512))
    context_labels = db.Column(db.ARRAY(db.String))
    # 384-dim loser_label embedding, precomputed so cross-case ranking embeds only the
    # anchor label per request rather than re-embedding every candidate.
    loser_embedding = db.Column(db.ARRAY(db.Float))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return (f"<DefeasibilityBandIndex case={self.case_id} "
                f"{self.winner_label!r} > {self.loser_label!r}>")
