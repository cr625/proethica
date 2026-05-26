"""Auto-generate code_provision_reference rows from conclusion citations (NO LLM).

Single source of truth shared by:
  * the live Step-4 pipeline hook (`run_step4_task`, study-corrections A8), and
  * the corpus backfill driver (`docs-internal/scripts/backfill_cited_provisions.py`, B3).

An `ethical_conclusion` row carries `citedProvisions` (a list of NSPE code
strings, e.g. "II.1.d."). Each cited code should have a companion
`code_provision_reference` row carrying the canonical provision text. This pass
closes coverage gaps deterministically: for every cited code that has no
reference row, it pulls the canonical text from `guideline_sections` (NSPE =
guideline_id 1, `section_code` stored WITHOUT a trailing dot) and inserts a
reference row tagged provenance `source='auto_generated_from_citation'`.

Codes that do not resolve to a `guideline_sections` leaf (e.g. a section-level
citation "II.5" where only II.5.a / II.5.b exist, or pre-2007 historical
vocabulary) are SKIPPED, never synthesized -- the locked decision is canonical
text only, no LLM gloss. Those are left for a bucket-C historical crosswalk.

Idempotent: codes already covered by a reference row (including ones this pass
inserted) are not re-inserted.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

NSPE_GUIDELINE_ID = 1
PROVENANCE_SOURCE = "auto_generated_from_citation"
DEFAULT_SESSION_ID = "cited-provision-autogen"


def normalize(code: str) -> str:
    """Strip surrounding whitespace and trailing dots for cross-source matching.

    "II.1.a." -> "II.1.a"; " II.5. " -> "II.5"; "I.1" -> "I.1".
    """
    return (code or "").strip().rstrip(".").strip()


def label_form(code_norm: str) -> str:
    """Reference rows store the code WITH a trailing dot (e.g. "II.1.a.")."""
    return f"{code_norm}."


def load_canonical() -> Dict[str, Tuple[str, str]]:
    """normalized section_code -> (raw section_code, section_text) for NSPE."""
    from app.models.guideline_section import GuidelineSection
    rows = (
        GuidelineSection.query
        .filter_by(guideline_id=NSPE_GUIDELINE_ID)
        .with_entities(GuidelineSection.section_code, GuidelineSection.section_text)
        .all()
    )
    return {normalize(code): (code, text) for code, text in rows}


def _cited_codes_for_case(case_id: int) -> Dict[str, List[str]]:
    """normalized cited code -> conclusion entity_labels that cite it."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage
    rows = (
        TemporaryRDFStorage.query
        .filter_by(case_id=case_id, extraction_type="ethical_conclusion")
        .all()
    )
    cited: Dict[str, List[str]] = {}
    for r in rows:
        provisions = (r.rdf_json_ld or {}).get("citedProvisions") or []
        if not isinstance(provisions, list):
            continue
        for raw in provisions:
            n = normalize(raw)
            if n:
                cited.setdefault(n, []).append(r.entity_label)
    return cited


def _existing_ref_codes(case_id: int) -> set:
    """normalized codeProvision codes already covered by reference rows."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage
    rows = (
        TemporaryRDFStorage.query
        .filter_by(case_id=case_id, extraction_type="code_provision_reference")
        .all()
    )
    return {
        normalize((r.rdf_json_ld or {}).get("codeProvision"))
        for r in rows
        if (r.rdf_json_ld or {}).get("codeProvision")
    }


def _build_row(case_id: int, code_norm: str, canonical: Tuple[str, str],
               citing_labels: List[str], session_id: str):
    from app.models.temporary_rdf_storage import TemporaryRDFStorage
    raw_code, text = canonical
    code_dotted = label_form(code_norm)
    return TemporaryRDFStorage(
        case_id=case_id,
        extraction_session_id=session_id,
        extraction_type="code_provision_reference",
        storage_type="individual",
        ontology_target="",
        entity_label=code_dotted,
        entity_uri="",
        entity_type="provisions",
        entity_definition=text,
        is_selected=True,
        is_reviewed=False,
        is_published=True,
        created_by=session_id,
        extraction_model="",
        triple_count=0,
        property_count=0,
        relationship_count=0,
        rdf_json_ld={
            "@type": "proeth-case:CodeProvisionReference",
            "codeProvision": code_dotted,
            "provisionText": text,
            "relevantExcerpts": [],
            "appliesTo": [],
        },
        provenance_metadata={
            "source": PROVENANCE_SOURCE,
            "generated_by": session_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "canonical_section_code": raw_code,
            "cited_in_conclusions": sorted(set(citing_labels)),
        },
    )


def apply_cited_provisions(
    case_id: int,
    canonical: Optional[Dict[str, Tuple[str, str]]] = None,
    dry_run: bool = False,
    session_id: str = DEFAULT_SESSION_ID,
) -> Dict:
    """Insert a code_provision_reference row for each cited code lacking one.

    Returns: {case_id, status (ok|dry_run|no_gaps), inserted, skipped,
    skipped_codes}. `canonical` may be preloaded once and passed in when
    looping over many cases.
    """
    from app.models import db

    if canonical is None:
        canonical = load_canonical()

    cited = _cited_codes_for_case(case_id)
    existing = _existing_ref_codes(case_id)
    missing = {c: labels for c, labels in cited.items() if c not in existing}

    if not missing:
        return {"case_id": case_id, "status": "no_gaps", "inserted": 0,
                "skipped": 0, "skipped_codes": []}

    insertable: List[Tuple[str, List[str]]] = []
    skipped_codes: List[str] = []
    for code_norm, labels in sorted(missing.items()):
        if code_norm in canonical:
            insertable.append((code_norm, labels))
        else:
            skipped_codes.append(code_norm)

    if dry_run:
        return {"case_id": case_id, "status": "dry_run", "inserted": 0,
                "skipped": len(skipped_codes), "skipped_codes": skipped_codes}

    for code_norm, labels in insertable:
        db.session.add(_build_row(case_id, code_norm, canonical[code_norm], labels, session_id))
    db.session.commit()

    if insertable or skipped_codes:
        logger.info("case %s: cited-provision auto-gen +%d rows, %d skipped (no canonical leaf)",
                    case_id, len(insertable), len(skipped_codes))
    return {"case_id": case_id, "status": "ok", "inserted": len(insertable),
            "skipped": len(skipped_codes), "skipped_codes": skipped_codes}
