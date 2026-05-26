"""Backfill missing board-question conclusions for a case.

Single source of truth shared by:
  * the live Step-4 pipeline hook (`run_step4_task`, study-corrections A2), and
  * the corpus backfill driver (`docs-internal/scripts/backfill_board_conclusions.py`).

Each NSPE case poses numbered board questions; Step-4 synthesis should emit one
primary `ethical_conclusion` answering each. When a board-explicit Question
(`Question_N`, N in 1-9) has no primary conclusion (a `Conclusion_N` with a
short suffix whose first answered question is N), this pass asks the
BoardConclusionExtractor to synthesize the missing conclusion from the
discussion/conclusion text. New rows are deduplicated against existing
conclusion labels so re-running never double-inserts.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DISCUSSION_MAX_CHARS = 12000


def _section_text(case_id: int, section_type: str) -> str:
    from app.models.document_section import DocumentSection
    sec = DocumentSection.query.filter_by(
        document_id=case_id, section_type=section_type
    ).first()
    if not sec or not sec.content:
        return ""
    return sec.content


def _case_title(case_id: int) -> str:
    from app.models.document import Document
    doc = Document.query.get(case_id)
    return doc.title if doc else f"Case {case_id}"


def _identify_gaps(case_id: int) -> Dict[str, Any]:
    """Return board-question gaps and the existing conclusion-label set.

    A gap is a board_explicit Question (entity_label Question_N, N in 1-9)
    for which no Conclusion with suffix length <= 2 has primary_q == N.
    """
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    questions = (
        TemporaryRDFStorage.query
        .filter_by(case_id=case_id, extraction_type="ethical_question", is_published=True)
        .all()
    )
    conclusions = (
        TemporaryRDFStorage.query
        .filter_by(case_id=case_id, extraction_type="ethical_conclusion", is_published=True)
        .all()
    )

    board_qs = []
    for q in questions:
        if (q.rdf_json_ld or {}).get("questionType") != "board_explicit":
            continue
        m = re.match(r"Question_(\d+)$", q.entity_label or "")
        if not m:
            continue
        n = int(m.group(1))
        if n >= 100:  # safety: only true board questions
            continue
        board_qs.append({"number": n, "label": q.entity_label, "text": q.entity_definition})

    primary_board_targets = set()
    existing_labels = set()
    for c in conclusions:
        existing_labels.add(c.entity_label)
        answers = (c.rdf_json_ld or {}).get("answersQuestions", []) or []
        if not answers:
            continue
        m = re.match(r"Conclusion_(\d+)$", c.entity_label or "")
        if not m:
            continue
        if len(m.group(1)) > 2:
            continue
        if isinstance(answers[0], int):
            primary_board_targets.add(answers[0])

    gaps = [bq for bq in board_qs if bq["number"] not in primary_board_targets]
    return {
        "case_id": case_id,
        "board_question_count": len(board_qs),
        "gaps": gaps,
        "existing_labels": existing_labels,
    }


def apply_board_conclusions(
    case_id: int,
    extractor: Optional[Any] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Synthesize and insert conclusions for unanswered board questions.

    Returns a status dict: ``status`` in {ok, dry_run, no_gaps, no_discussion_text}.
    Constructs a default BoardConclusionExtractor when none is supplied.
    """
    from app.models import db
    from app.models.temporary_rdf_storage import TemporaryRDFStorage
    from app.services.extraction.board_conclusions import BoardQuestionGap

    audit = _identify_gaps(case_id)
    gaps = audit["gaps"]
    existing_labels = audit["existing_labels"]

    if not gaps:
        return {"case_id": case_id, "status": "no_gaps"}

    if dry_run:
        return {
            "case_id": case_id,
            "status": "dry_run",
            "gap_count": len(gaps),
            "gap_questions": [g["number"] for g in gaps],
        }

    discussion = _section_text(case_id, "discussion")[:DISCUSSION_MAX_CHARS]
    conclusion_section = _section_text(case_id, "conclusion") or _section_text(case_id, "conclusions")
    if not discussion:
        return {"case_id": case_id, "status": "no_discussion_text"}

    if extractor is None:
        from app.services.extraction.board_conclusions import BoardConclusionExtractor
        extractor = BoardConclusionExtractor()

    gap_inputs = [
        BoardQuestionGap(question_number=g["number"], question_text=g["text"])
        for g in gaps
    ]
    result = extractor.extract(
        case_id=case_id,
        case_title=_case_title(case_id),
        gaps=gap_inputs,
        discussion_text=discussion,
        conclusion_text=conclusion_section,
    )

    # Tie new rows to the case's existing conclusion batch when possible.
    existing_session_id = (
        db.session.query(TemporaryRDFStorage.extraction_session_id)
        .filter_by(case_id=case_id, extraction_type="ethical_conclusion")
        .first()
    )
    extraction_session_id = (
        existing_session_id[0]
        if existing_session_id and existing_session_id[0]
        else f"board-conclusion-backfill-{case_id}"
    )

    rows_inserted = 0
    skipped_label_collisions: List[str] = []
    for c in result.conclusions:
        label = f"Conclusion_{c.question_number}"
        if label in existing_labels:
            skipped_label_collisions.append(label)
            continue
        row = TemporaryRDFStorage(
            case_id=case_id,
            extraction_type="ethical_conclusion",
            extraction_session_id=extraction_session_id,
            storage_type="individual",
            entity_label=label,
            entity_definition=c.conclusion_text,
            is_published=True,
            rdf_json_ld={
                "@type": "proeth-scenario:EthicalConclusion",
                "@id": f"http://proethica.org/case/{case_id}#{label}",
                "rdfs:label": label,
                "answersQuestions": [c.question_number],
                "citedProvisions": list(c.cited_provisions),
                "extractionPass": "board_conclusion_backfill",
            },
        )
        db.session.add(row)
        existing_labels.add(label)  # guard against intra-batch duplicate question numbers
        rows_inserted += 1

    db.session.commit()

    return {
        "case_id": case_id,
        "status": "ok",
        "gap_count": len(gaps),
        "rows_inserted": rows_inserted,
        "skipped_label_collisions": skipped_label_collisions,
    }
