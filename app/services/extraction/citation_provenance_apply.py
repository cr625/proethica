"""Annotate non-resolvable conclusion citations with provenance (NO LLM).

Single source of truth shared by:
  * the live Step-4 pipeline hook (`run_step4_task`, study-corrections Phase 4), and
  * the corpus driver (`docs-internal/scripts/annotate_historical_citations.py`).

Companion to `cited_provisions_apply` (A8): A8 creates a `code_provision_reference`
row for every cited code that DOES resolve to a `guideline_sections` leaf. This pass
handles the complement -- citations that do NOT resolve (pre-2007 NSPE numbered
vocabulary, BER case precedents, external laws, leaked synthesized standard labels,
or modern section-level codes whose only leaves are sub-points). Per the locked
decision (2026-05-26), those are ANNOTATED as unmapped, never crosswalked (the
1960s/70s NSPE code has no defensible 1:1 modern equivalent) and never dropped.

For each `ethical_conclusion` row with one or more non-resolvable citations, a
`proeth:citationProvenance` field is added classifying each unmapped citation by
category. `citedProvisions` is never modified. Idempotent: rows already carrying
`proeth:citationProvenance` are skipped.

Resolution uses the SAME canonical key set as `cited_provisions_apply` so this pass
can never disagree with the pipeline about what "resolves".
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.services.extraction.cited_provisions_apply import normalize, load_canonical
from app.services.extraction.rules import Rule, RuleSet

logger = logging.getLogger(__name__)

CATEGORY_NOTES = {
    "nspe_pre_2007_numbered":
        "Pre-2007 NSPE numbered Canons/Rules/Sections vocabulary. The modern "
        "I/II/III NSPE Code has no clean 1:1 equivalent; retained verbatim, "
        "deliberately not crosswalked.",
    "ber_cross_case_precedent":
        "Citation of another BER case as precedent, not a code provision. Not a "
        "guideline_sections leaf; retained verbatim.",
    "external_law_or_regulation":
        "External statute/regulation (federal or state), not an NSPE code "
        "provision. No guideline_sections leaf; retained verbatim.",
    "synthesized_standard_label":
        "Synthesized standard/framework/norm label emitted by extraction, not a "
        "literal code citation. No guideline_sections leaf; retained verbatim.",
    "generic_nspe_no_leaf":
        "Generic reference to the NSPE Code with no specific section leaf. "
        "Not resolvable to a guideline_sections row; retained verbatim.",
    "modern_section_no_leaf":
        "Modern NSPE Code section-level citation (I/II/III format) that does not "
        "match a single guideline_sections leaf because only its sub-points exist "
        "(e.g. II.4.a / II.4.b). NOT historical; retained verbatim, not pinned to a "
        "specific leaf.",
    "other_unmapped":
        "Citation does not resolve to any guideline_sections leaf and matches no "
        "known historical pattern; retained verbatim, not crosswalked.",
}


@dataclass(frozen=True)
class _CitationCtx:
    """The normalized views of a non-resolvable citation that the category rules inspect.

    ``s`` is the stripped raw text (case preserved); ``low`` is its lowercase form; ``low_sp``
    additionally collapses hyphen/underscore runs to a single space. NOTE: because ``low_sp``
    has no hyphens, a hyphen-bearing pattern (``\\b\\d{2}-\\d``) can only ever match against the
    OTHER views -- this quirk is part of the preserved precedence (e.g. bare "92-1" -> other)."""
    s: str
    low: str
    low_sp: str


# The unmapped-citation category cascade as a classifying rule set (see
# app.services.extraction.rules). Declaration order IS the precedence: modern-section >
# BER-precedent > external-law > pre-2007-numbered > synthesized-label > generic-NSPE. Each
# rule's payload is the category it assigns; classify() resolves "is this a modern leaf?"
# first (returning None) and otherwise delegates to RULESET.classify(ctx, default=...). The
# branch predicates and their byte-identical regexes are unchanged from the prior cascade.
CITATION_RULES: RuleSet[_CitationCtx] = RuleSet("citation_provenance", [
    Rule("modern_section_no_leaf",
         "modern I/II/III section-level citation that did not resolve to a leaf",
         lambda c: bool(re.match(r"^(i{1,3}|iv|v)\.\d", c.low)),
         payload="modern_section_no_leaf"),
    Rule("ber_cross_case_precedent",
         "cites another BER case as precedent ('BER', 'Case ... N', or 'NN-N')",
         lambda c: bool(re.search(r"\bber\b", c.low_sp) or re.search(r"\bcase\b.*\d", c.low_sp)
                        or re.search(r"\b\d{2}-\d", c.low_sp)),
         payload="ber_cross_case_precedent"),
    Rule("external_law_or_regulation",
         "external statute/regulation keyword (Brooks Act, EPA, model law, ...)",
         lambda c: any(k in c.low_sp for k in ["brooks act", "epa ", "model law", "state law",
                                               "registration law", "federal register", "qbs"]),
         payload="external_law_or_regulation"),
    Rule("nspe_pre_2007_numbered",
         "pre-2007 NSPE Canon/Rule/Section numbered vocabulary",
         lambda c: bool(re.search(r"section[\s_\-]*\d", c.low) or "canon" in c.low_sp
                        or re.search(r"rule[\s_\-]*\d", c.low)
                        or re.search(r"^\d+(\([a-z]\))?$", c.s)
                        or c.low.startswith("section ")),
         payload="nspe_pre_2007_numbered"),
    Rule("synthesized_standard_label",
         "a synthesized standard/framework/norm label, not a literal code citation",
         lambda c: bool(re.search(r"(standard|framework|norm|obligation|distinction|clause|"
                                  r"policy|requirement|directive)", c.low_sp)),
         payload="synthesized_standard_label"),
    Rule("generic_nspe_no_leaf",
         "generic reference to the NSPE Code with no specific section leaf",
         lambda c: "nspe" in c.low_sp or "code of ethics" in c.low_sp
                   or "rules of professional conduct" in c.low_sp,
         payload="generic_nspe_no_leaf"),
])


def classify(raw: str, canonical_norms: set) -> Optional[str]:
    """Return None if the citation resolves to a modern leaf; else a category.

    Resolution is checked first (``normalize(raw)`` in the canonical set -> None). Otherwise
    the category is the payload of the first matching CITATION_RULES rule, defaulting to
    ``other_unmapped`` when none match. Backed by CITATION_RULES so the cascade is one
    inspectable registry; precedence and the per-branch predicates are unchanged."""
    if normalize(raw) in canonical_norms:
        return None
    s = (raw or "").strip()
    low = s.lower()
    low_sp = re.sub(r"[-_]+", " ", low)  # treat hyphen/underscore as space
    return CITATION_RULES.classify(_CitationCtx(s=s, low=low, low_sp=low_sp),
                                   default="other_unmapped")


def apply_citation_provenance(
    case_id: int,
    canonical: Optional[Dict[str, Tuple[str, str]]] = None,
    dry_run: bool = False,
) -> Dict:
    """Annotate `ethical_conclusion` rows of a case with citation provenance.

    Returns: {case_id, status (ok|dry_run|no_unmapped), annotated, categories}.
    `canonical` may be preloaded once and passed in when looping over many cases.
    """
    from app.models import db
    from app.models.temporary_rdf_storage import TemporaryRDFStorage
    from sqlalchemy.orm.attributes import flag_modified

    if canonical is None:
        canonical = load_canonical()
    canonical_norms = set(canonical.keys())

    rows = (
        TemporaryRDFStorage.query
        .filter_by(case_id=case_id, extraction_type="ethical_conclusion")
        .order_by(TemporaryRDFStorage.id)
        .all()
    )

    pending: List[Tuple[object, List[Dict[str, str]], List[str]]] = []
    categories: Dict[str, int] = {}
    for r in rows:
        rdf = r.rdf_json_ld or {}
        if rdf.get("proeth:citationProvenance"):
            continue  # idempotent
        provisions = rdf.get("citedProvisions") or []
        if not isinstance(provisions, list) or not provisions:
            continue
        unmapped: List[Dict[str, str]] = []
        resolvable: List[str] = []
        for raw in provisions:
            cat = classify(raw, canonical_norms)
            if cat is None:
                resolvable.append(raw)
            else:
                unmapped.append({"citation": raw, "category": cat})
                categories[cat] = categories.get(cat, 0) + 1
        if unmapped:
            pending.append((r, unmapped, resolvable))

    if not pending:
        return {"case_id": case_id, "status": "no_unmapped", "annotated": 0, "categories": {}}

    if dry_run:
        return {"case_id": case_id, "status": "dry_run", "annotated": len(pending),
                "categories": categories}

    ts = datetime.utcnow().isoformat() + "Z"
    for (r, unmapped, resolvable) in pending:
        new_rdf = dict(r.rdf_json_ld or {})
        new_rdf["proeth:citationProvenance"] = {
            "annotated_at": ts,
            "method": "historical_unmapped_classification",
            "decision": "annotate_historical_unmapped (no crosswalk, no drop)",
            "unmapped": unmapped,
            "resolvable": resolvable,
            "category_notes": {u["category"]: CATEGORY_NOTES[u["category"]] for u in unmapped},
        }
        r.rdf_json_ld = new_rdf
        flag_modified(r, "rdf_json_ld")
        prov = dict(r.provenance_metadata or {})
        prov["phase4_citation_annotation"] = {"at": ts}
        r.provenance_metadata = prov
        flag_modified(r, "provenance_metadata")
    db.session.commit()

    logger.info("case %s: citation-provenance annotated %d conclusion rows (%s)",
                case_id, len(pending), categories)
    return {"case_id": case_id, "status": "ok", "annotated": len(pending),
            "categories": categories}
