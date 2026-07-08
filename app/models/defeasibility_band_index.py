"""Commit-time index of per-case resolved-tension patterns.

Populated from each case's committed TTL after edge materialization, so the
cross-case defeasibility band can rank comparable cases without scanning every
case TTL per request (ROADMAP Section A, 2026-06-05). One row per resolved
``prevailsOver`` (winner, loser) pair, carrying the licensing State context and
precomputed all-MiniLM-L6-v2 embeddings for similarity ranking.

2026-07-08 (defeasibility view review): the ranking became pairwise. A tension
is the PAIR of obligations, so the row now carries embeddings of both labels
plus one embedding of the joined context labels (exact-label Jaccard was
structurally inert across cases: context individuals are case-minted, so
labels almost never recur verbatim). ``fresh`` marks rows built from a
fresh-architecture TTL (detected by the ``proeth-prov:synthesisLiteral``
marker); the dynamic band only ranks fresh rows, excluding legacy
prior-extraction patterns until the 119-case rebuild re-commits them.

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
    # 384-dim label embeddings, precomputed so cross-case ranking embeds only the
    # anchor's labels per request rather than re-embedding every candidate.
    loser_embedding = db.Column(db.ARRAY(db.Float))
    winner_embedding = db.Column(db.ARRAY(db.Float))
    # One embedding of the joined (sorted, '; '-separated) context labels; None
    # when the pair carries no defeasibleUnder contexts.
    context_embedding = db.Column(db.ARRAY(db.Float))
    # Intermediate-class type local names of the pair's endpoints (e.g.
    # FaithfulAgentObligation), for TYPE-LEVEL recurrence display: exact match
    # across cases, no embedding (2026-07-08).
    winner_type = db.Column(db.String(255))
    loser_type = db.Column(db.String(255))
    # True when the source TTL is a fresh-architecture commit (carries the
    # proeth-prov:synthesisLiteral marker). Only fresh rows enter the dynamic band.
    fresh = db.Column(db.Boolean, nullable=False, default=False, server_default='false')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return (f"<DefeasibilityBandIndex case={self.case_id} "
                f"{self.winner_label!r} > {self.loser_label!r}>")
