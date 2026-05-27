#!/usr/bin/env python3
"""Build the gold-pair set for canonicalization cosine-threshold calibration.

ROADMAP Section A (post-iccbr-canonicalization Issue 3). Produces
``data/calibration/match_gold_pairs.csv`` from a hand-curated list of
within-component-type class pairs, fetching the REAL extracted definitions from
``ai_ethical_dm.temporary_rdf_storage`` (``storage_type='class'``).

Band semantics (analyst judgement, recorded per pair with a rationale):
  same       -- the two labels denote the same underlying concept; the matcher
                SHOULD link them (canonicalization target).
  variant    -- same component type and topic, but a genuinely distinct
                sub-concept; the gray zone the review band exists for.
  unrelated  -- same component type, different topic; the matcher must NOT link.

Refinement over the original plan: cross-COMPONENT pairs are deliberately
excluded. The live matcher (`auto_commit_service._check_duplicate`) applies a
category guard (URI marker filter) BEFORE the cosine threshold, so a candidate
can only ever be compared against same-type classes. The cosine threshold's job
is to separate same/variant/unrelated WITHIN a type; cross-type separation is the
guard's job, not the threshold's. Calibrating on within-type pairs therefore
measures exactly what the threshold controls.

Usage:
    python scripts/calibration/build_match_gold_pairs.py            # write CSV
    python scripts/calibration/build_match_gold_pairs.py --print    # also dump defs
"""
from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "data" / "calibration" / "match_gold_pairs.csv"
DB_ENV = {"PGPASSWORD": "PASS", "PATH": "/usr/bin:/bin"}

# (component_type, candidate_label, target_label, band, rationale)
# component_type is the temporary_rdf_storage.extraction_type for BOTH labels.
PAIRS = [
    # ------------------------------------------------------------------ same
    ("obligations",
     "Adversarial Circumstance Non-Justification for Selective Reporting Obligation",
     "Adversarial Context Report Completeness and Non-Selectivity Obligation",
     "same", "Both: in an adversarial proceeding the engineer must report completely and not selectively."),
    ("obligations",
     "AI-Assisted Design Comprehensive Verification Obligation",
     "AI-Generated Work Product Competence Verification Obligation",
     "same", "Both: duty to competently verify AI-generated engineering work product before relying on it."),
    ("obligations",
     "Active Project Declination During Employment Before Independent Departure Obligation",
     "Active-Employment Private Contract Conclusion Prohibition Obligation",
     "same", "Both: do not secure/conclude private work while still employed by the current employer."),
    ("capabilities",
     "AI Disclosure and Transparency Capability",
     "AI Tool Scope Calibration Capability",
     "same", "PLACEHOLDER-VERIFY: both about governing appropriate AI-tool use disclosure/scope."),
    ("constraints",
     "AI Attribution and Credit Disclosure Constraint",
     "AI-Generated Work Product Disclosure Constraint",
     "same", "Both: constraint requiring disclosure of AI involvement in the work product."),
    ("obligations",
     "ADA-Protected Condition Non-Disclosure Non-Deception Compliance Obligation",
     "ADA-Protected Condition Non-Discrimination Employer Dignity Obligation",
     "variant", "Same ADA-protected-condition topic; one is non-deception, the other non-discrimination/dignity."),
    ("roles",
     "Affected Property Owner Stakeholder",
     "Adjacent Third-Party Property Owner Stakeholder",
     "same", "Both: a property-owner stakeholder affected by the engineer's work."),
    ("resources",
     "AI Software Usage Disclosure Standard",
     "As-Built Drawing Disclosure Standard",
     "variant", "Both disclosure standards, but different subject matter (AI usage vs as-built drawings)."),
    # --------------------------------------------------------------- variant
    ("obligations",
     "AI Tool Disclosure Obligation",
     "AI Tool Attribution and Citation Obligation",
     "variant", "Same AI-tool transparency family; disclosure of use vs attribution/citation are distinct duties."),
    ("capabilities",
     "AI Attribution and Citation Capability",
     "AI Disclosure and Transparency Capability",
     "variant", "Same AI-tool family; attribution vs disclosure are distinct competencies."),
    ("capabilities",
     "AI Output Verification Capability",
     "AI Tool Competence Assessment Capability",
     "variant", "Both AI-competence family; verifying output vs assessing one's own tool competence."),
    ("constraints",
     "AI Tool Competence Boundary Constraint",
     "AI Tool Direction and Control Constraint",
     "variant", "Same AI-tool-governance family; competence boundary vs direction/control are distinct limits."),
    ("constraints",
     "ADA-Protected Condition Ethics Code Deception Non-Application Constraint",
     "ADA-Protected Condition Voluntary Disclosure Non-Compulsion Constraint",
     "variant", "Same ADA topic; non-application-of-deception vs non-compulsion-of-disclosure are distinct."),
    ("obligations",
     "Active Project Declination During Employment Before Independent Departure Obligation",
     "AE Firm Incumbent Advantage Non-Exploitation Obligation",
     "variant", "Both conflict-of-interest/loyalty family; pre-departure declination vs incumbent-advantage exploitation."),
    ("principles",
     "Adversarial Context Non-Exemption from Professional Standards",
     "Adversarial Engagement Objectivity Obligation",
     "variant", "Same adversarial-engagement family; non-exemption-from-standards vs objectivity duty."),
    ("obligations",
     "Adjacent Third-Party Property Safety Disclosure Obligation",
     "Actionable Bracing Remedial Guidance to Building Owner Obligation",
     "variant", "Both third-party safety family; disclosure to adjacent owner vs remedial bracing guidance."),
    # ------------------------------------------------------------- unrelated
    ("obligations",
     "AI Tool Disclosure Obligation",
     "100-Year Storm Surge Design Standard Recommendation Obligation",
     "unrelated", "AI-tool transparency vs storm-surge design standard: different topics."),
    ("obligations",
     "Adversarial Context Report Completeness and Non-Selectivity Obligation",
     "Adjacent Third-Party Property Safety Disclosure Obligation",
     "unrelated", "Adversarial reporting completeness vs adjacent-property safety disclosure: different topics."),
    ("obligations",
     "AI Tool Attribution and Citation Obligation",
     "Absolute Loyalty Non-Extension to Former Client Adverse Engagement Obligation",
     "unrelated", "AI attribution vs former-client loyalty: different topics."),
    ("capabilities",
     "AI Output Verification Capability",
     "ADA Non-Discrimination Dignity Provision Application Capability",
     "unrelated", "AI output verification vs ADA non-discrimination application: different topics."),
    ("constraints",
     "AI Tool Direction and Control Constraint",
     "ADA-Protected Condition Voluntary Disclosure Non-Compulsion Constraint",
     "unrelated", "AI tool control vs ADA disclosure non-compulsion: different topics."),
    ("obligations",
     "100-Year Storm Surge Design Standard Recommendation Obligation",
     "Active-Employment Private Contract Conclusion Prohibition Obligation",
     "unrelated", "Storm-surge design standard vs employment-period private-contract prohibition: different topics."),
    ("obligations",
     "ADA-Protected Condition Non-Discrimination Employer Dignity Obligation",
     "Accelerated Timeline Public Health Risk Objection Obligation",
     "unrelated", "ADA non-discrimination vs accelerated-timeline public-health-risk objection: different topics."),
    ("capabilities",
     "AI Tool Competence Assessment Capability",
     "ADA-Protected Condition Non-Disclosure Non-Deception Distinction Capability",
     "unrelated", "AI tool competence vs ADA non-deception distinction: different topics."),
]


def psql(query: str) -> str:
    r = subprocess.run(
        ["psql", "-h", "localhost", "-U", "postgres", "-d", "ai_ethical_dm",
         "-t", "-A", "-c", query],
        capture_output=True, text=True, env=DB_ENV,
    )
    return r.stdout.strip()


def fetch_definition(component_type: str, label: str) -> str:
    safe = label.replace("'", "''")
    q = (
        "SELECT entity_definition FROM temporary_rdf_storage "
        f"WHERE storage_type='class' AND extraction_type='{component_type}' "
        f"AND entity_label='{safe}' AND entity_definition IS NOT NULL "
        "ORDER BY length(entity_definition) DESC LIMIT 1;"
    )
    out = psql(q)
    return " ".join(out.split())  # collapse whitespace/newlines


def main() -> int:
    show = "--print" in sys.argv
    rows = []
    misses = []
    for i, (ctype, cand, targ, band, rationale) in enumerate(PAIRS, 1):
        cdef = fetch_definition(ctype, cand)
        tdef = fetch_definition(ctype, targ)
        if not cdef:
            misses.append((ctype, cand))
        if not tdef:
            misses.append((ctype, targ))
        rows.append({
            "pair_id": i, "component_type": ctype,
            "candidate_label": cand, "candidate_definition": cdef,
            "target_label": targ, "target_definition": tdef,
            "expected_band": band, "rationale": rationale,
        })
        if show:
            print(f"[{i:02d}] {band.upper():9s} ({ctype})")
            print(f"   C: {cand}\n      {cdef[:160]}")
            print(f"   T: {targ}\n      {tdef[:160]}\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    bands = Counter(r["expected_band"] for r in rows)
    print(f"Wrote {len(rows)} pairs -> {OUT}")
    print(f"Bands: {dict(bands)}")
    if misses:
        print(f"WARNING: {len(misses)} label(s) had no definition (label/type mismatch):")
        for ct, lb in misses:
            print(f"  - [{ct}] {lb}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
