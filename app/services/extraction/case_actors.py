"""Present-case actor identification, shared across the extraction, temporal, and narrative
passes.

NSPE opinions name the case's own engineers by letter in the facts/question/conclusion
sections; engineers from cited precedents appear only in the discussion section. The set of
present-case engineer letters is the input to the foreign-actor contamination rule
(``precedent_filter.is_foreign_actor_entity``). This module owns the DB load so the pure
detection logic in ``precedent_filter`` stays import-light and unit-testable.
"""
from __future__ import annotations

import logging

from app.services.extraction.precedent_filter import present_case_actor_letters

logger = logging.getLogger(__name__)

# Present-case sections only -- the discussion is excluded because it is the one section that
# recaps prior BER cases (and so carries foreign precedent engineer letters). Both singular and
# plural section-type spellings are accepted across the corpus.
_PRESENT_CASE_SECTIONS = ("facts", "question", "questions", "conclusion", "conclusions")


def present_case_engineer_letters(case_id: int) -> frozenset:
    """The engineer letters named in this case's present-case sections, e.g. ``{"L"}`` for a
    case whose protagonist is Engineer L. Returns an empty frozenset on any load failure (the
    caller then skips the actor rule, never over-dropping)."""
    from app import db
    from sqlalchemy import text as sql_text
    try:
        rows = db.session.execute(
            sql_text(
                "SELECT content FROM document_sections "
                "WHERE document_id = :cid AND section_type = ANY(:types)"
            ),
            {"cid": case_id, "types": list(_PRESENT_CASE_SECTIONS)},
        ).fetchall()
        text = "\n".join(r[0] for r in rows if r and r[0])
        return present_case_actor_letters(text)
    except Exception:
        logger.debug("present-case actor load failed for case %s", case_id, exc_info=True)
        return frozenset()
