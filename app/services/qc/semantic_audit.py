#!/usr/bin/env python3
"""
Semantic QC audit: do the committed answers make sense against the case text?

The structural audits (run_qc_audit V-checks, Pellet, SHACL conformance, the
watch metrics) verify shape; this protocol reads the COMMITTED artifacts back
against the source case and scores their fidelity. Built for the legacy-case
rebuild as the per-batch sampling gate (runbook step 3).

Checks (S-protocol; results land in case_verification_results like the
V-checks, protocol_version 'semantic-1.0'):

    S1  Precedent designator fidelity   CRITICAL   deterministic
        Every case number in the committed precedent layer appears in the
        case text (hallucination catch), and every number the discussion
        cites appears in the committed layer (loss catch -- the case-143
        dedup class).
    S2  Agent roster grounding          WARNING    deterministic
        Every participant Agent label is textually grounded in the case
        (phantom-actor catch, post-hoc).
    S3  Board question fidelity         CRITICAL   deterministic
        Committed board_explicit questions align with the question section
        (token-overlap floor).
    S4  Conclusion fidelity             CRITICAL   LLM-judged
        Board conclusions faithful to the conclusion section; the detected
        boardConclusionType matches the holding; answersQuestion links
        sensible.
    S5  Obligation attribution          WARNING    LLM-judged
        Committed obligation individuals belong to the right party and are
        asserted or clearly implied by the case.
    S6  Defeasibility sanity            WARNING    LLM-judged
        The committed competesWith/prevailsOver/defeasibleUnder structure
        (or its absence) matches the board's holding under the
        specification-vs-defeat rubric; a prevailsOver winner must match
        the holding.
    S7  Decision point sanity           WARNING    LLM-judged
        Decision points are real choices faced in the case and their
        boardResolution matches the actual holding.

Usage:
    python -m app.services.qc.semantic_audit 143                # one case
    python -m app.services.qc.semantic_audit --batch 143 113 97 # several
    python -m app.services.qc.semantic_audit --batch-file rebuild-batches/batch2.txt --sample 5
    ... --dry-run   (no DB write)   -v (full per-check output)

Sampling pins any ids passed via --pin (repaired or watch-flagged cases)
then stratifies the rest: the min- and max-entity-count cases plus random
fill, seeded for reproducibility.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from rdflib import Graph, Namespace, RDF, RDFS

PROTOCOL_VERSION = "semantic-1.0"
ONT_DIR = "/home/chris/onto/OntServe/ontologies"

CORE = Namespace("http://proethica.org/ontology/core#")
CASES = Namespace("http://proethica.org/ontology/cases#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")

_CASE_NUM_RE = re.compile(r"\b\d{2}-\d{1,2}\b")
_STOPWORDS = frozenset(
    "the a an of in to and or for by with on at as is was were be been this that".split())


# --- data loading ------------------------------------------------------------

def _sections(case_id: int) -> Dict[str, str]:
    from app.models import Document
    from app import db
    case = db.session.get(Document, case_id)
    out = {}
    for key, val in ((case.doc_metadata or {}).get("sections_dual") or {}).items():
        out[key] = (val.get("text", "") if isinstance(val, dict) else str(val)) or ""
    return out


def _graph(case_id: int) -> Optional[Graph]:
    from pathlib import Path
    ttl = Path(ONT_DIR) / f"proethica-case-{case_id}.ttl"
    if not ttl.exists():
        return None
    g = Graph()
    g.parse(str(ttl), format="turtle")
    return g


def _rows(case_id: int, extraction_type: str) -> list:
    from app.models.temporary_rdf_storage import TemporaryRDFStorage
    return (TemporaryRDFStorage.query
            .filter_by(case_id=case_id, extraction_type=extraction_type,
                       is_published=True)
            .order_by(TemporaryRDFStorage.id).all())


# --- LLM plumbing ------------------------------------------------------------

def _judge(prompt: str) -> Optional[dict]:
    """One structured judgment on the default tier. Returns the parsed dict or
    None on any failure (the check then reports 'judge_unavailable')."""
    try:
        from app.utils.llm_utils import (
            get_llm_client, direct_call_params, extract_json_from_response)
        from model_config import ModelConfig
        client = get_llm_client()
        model = ModelConfig.get_claude_model("default")
        chunks: List[str] = []
        with client.messages.stream(
            **direct_call_params(model, max_tokens=4000),
            system=("You audit knowledge extracted from professional-ethics "
                    "cases for fidelity to the source text. Judge strictly "
                    "from the provided text; quote evidence verbatim. Output "
                    "strict JSON only."),
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for t in stream.text_stream:
                chunks.append(t)
        data = extract_json_from_response("".join(chunks))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _check(name, severity, status, detail) -> dict:
    return {"check": name, "severity": severity, "status": status, "detail": detail}


# --- S1-S3: deterministic ----------------------------------------------------

def s1_precedent_designators(case_id, g, sections) -> dict:
    text = " ".join(sections.get(k, "") for k in
                    ("facts", "discussion", "question", "conclusion"))
    from app.models import Document
    from app import db
    doc = db.session.get(Document, case_id)
    own = _CASE_NUM_RE.findall(
        str((doc.doc_metadata or {}).get("case_number") or ""))
    text_nums = set(_CASE_NUM_RE.findall(text)) - set(own)
    graph_nums = set()
    for cls in (CASES.PrecedentCaseReference,):
        for s in g.subjects(RDF.type, cls):
            lbl = str(g.value(s, RDFS.label) or "")
            graph_nums.update(_CASE_NUM_RE.findall(lbl))
            for o in g.objects(s, CASES.citedCaseNumber):
                graph_nums.update(_CASE_NUM_RE.findall(str(o)))
    # resources typed as precedents carry numbers in labels too
    for s, o in g.subject_objects(RDFS.label):
        if "BER Case" in str(o):
            graph_nums.update(_CASE_NUM_RE.findall(str(o)))
    hallucinated = sorted(graph_nums - text_nums - set(own))
    lost = sorted(text_nums - graph_nums)
    status = "pass"
    if hallucinated:
        status = "critical"
    elif lost:
        status = "warning"  # text cites it, graph lacks it (may be recap-only)
    return _check("S1_precedent_designators", "critical", status, {
        "in_graph": sorted(graph_nums), "in_text_only": lost,
        "in_graph_only_HALLUCINATION": hallucinated})


def s2_agent_grounding(case_id, g, sections) -> dict:
    text = " ".join(sections.values()).lower()
    ungrounded = []
    for agent in set(g.subjects(RDF.type, CORE.Agent)):
        if (agent, RDF.type, CASES.DeliberativeBody) in g:
            continue
        lbl = str(g.value(agent, RDFS.label) or "")
        tokens = [t for t in re.split(r"[^a-z0-9]+", lbl.lower())
                  if len(t) > 2 and t not in _STOPWORDS]
        if tokens and not any(t in text for t in tokens):
            ungrounded.append(lbl)
    return _check("S2_agent_grounding", "warning",
                  "warning" if ungrounded else "pass",
                  {"ungrounded_agents": ungrounded})


def s3_board_questions(case_id, sections) -> dict:
    qsec = (sections.get("question") or sections.get("questions") or "").lower()
    rows = [r for r in _rows(case_id, "ethical_question")
            if (r.rdf_json_ld or {}).get("questionType") == "board_explicit"]
    misaligned = []
    for r in rows:
        qtext = ((r.rdf_json_ld or {}).get("questionText") or "").lower()
        tokens = [t for t in re.split(r"[^a-z0-9]+", qtext)
                  if len(t) > 3 and t not in _STOPWORDS]
        if not tokens:
            continue
        overlap = sum(1 for t in tokens if t in qsec) / len(tokens)
        if overlap < 0.5:
            misaligned.append({"question": qtext[:120], "overlap": round(overlap, 2)})
    status = "pass" if not misaligned else ("critical" if not qsec else "warning")
    if not rows:
        status, misaligned = ("warning", [{"note": "no board_explicit questions stored"}]) \
            if qsec.strip() else ("pass", [])
    return _check("S3_board_questions", "critical", status,
                  {"board_questions": len(rows), "misaligned": misaligned})


# --- S4-S7: LLM-judged --------------------------------------------------------

def _fmt_rows(rows, keys, cap=12):
    out = []
    for r in rows[:cap]:
        d = r.rdf_json_ld or {}
        out.append({k: d.get(k) for k in keys if d.get(k) not in (None, "", [])})
    return json.dumps(out, indent=1)[:6000]


def s4_conclusions(case_id, sections) -> dict:
    rows = _rows(case_id, "ethical_conclusion")
    csec = sections.get("conclusion") or sections.get("conclusions") or ""
    if not rows or not csec.strip():
        return _check("S4_conclusion_fidelity", "critical",
                      "warning" if csec.strip() else "pass",
                      {"note": "no conclusions stored" if csec.strip()
                       else "case has no conclusion section"})
    verdict = _judge(f"""CASE CONCLUSION SECTION:
{csec[:6000]}

COMMITTED CONCLUSIONS (extracted knowledge under audit):
{_fmt_rows(rows, ['conclusionNumber', 'conclusionText', 'conclusionType', 'boardConclusionType', 'answersQuestions'])}

For the committed board_explicit conclusions, judge: (a) is each conclusionText
faithful to the section (not invented, not materially altered)? (b) does each
boardConclusionType (violation/no_violation/compliance/recommendation/
interpretation) match the actual holding? (c) any section holding MISSING from
the committed set? Output JSON:
{{"faithful": true/false, "type_errors": [{{"conclusion": n, "stored": "...", "should_be": "...", "evidence": "verbatim quote"}}], "missing_holdings": ["..."], "notes": "one sentence"}}""")
    if verdict is None:
        return _check("S4_conclusion_fidelity", "critical", "judge_unavailable", {})
    bad = (not verdict.get("faithful", True)) or verdict.get("type_errors") \
        or verdict.get("missing_holdings")
    return _check("S4_conclusion_fidelity", "critical",
                  "critical" if bad else "pass", verdict)


def s5_obligations(case_id, g, sections) -> dict:
    obligations = []
    for s in set(g.subjects(RDF.type, CORE.Obligation)):
        party_node = g.value(s, CORE.obligatedParty)
        obligations.append({
            "label": str(g.value(s, RDFS.label) or ""),
            "party": str(g.value(party_node, RDFS.label) or "") if party_node else None})
    if not obligations:
        return _check("S5_obligation_attribution", "warning", "pass",
                      {"note": "no obligation individuals"})
    text = " ".join(sections.get(k, "") for k in ("facts", "discussion", "conclusion"))
    verdict = _judge(f"""CASE TEXT (facts + discussion + conclusion):
{text[:9000]}

COMMITTED OBLIGATION INDIVIDUALS (label + obligated party):
{json.dumps(obligations, indent=1)[:3000]}

MODELING CONVENTION: duties are minted PER ACTOR -- a duty the case places on
'Engineers A and B' jointly is correctly stored as separate per-actor
individuals ('Engineer A X Duty', 'Engineer B X Duty'); a per-actor slice of a
joint duty is NOT a misattribution. Flag only a duty attributed to an actor
the case does NOT place it on. Judge each: (a) does the case assert or
clearly imply this duty? (b) is it attributed to a WRONG party? Output JSON:
{{"unsupported": [{{"label": "...", "why": "...", }}], "misattributed": [{{"label": "...", "stored_party": "...", "should_be": "...", "evidence": "quote"}}], "notes": "one sentence"}}""")
    if verdict is None:
        return _check("S5_obligation_attribution", "warning", "judge_unavailable", {})
    bad = verdict.get("unsupported") or verdict.get("misattributed")
    return _check("S5_obligation_attribution", "warning",
                  "warning" if bad else "pass", verdict)


def s6_defeasibility(case_id, g, sections) -> dict:
    def edge_list(pred):
        return [(str(g.value(s, RDFS.label) or ""), str(g.value(o, RDFS.label) or ""))
                for s, o in g.subject_objects(CORE[pred])]
    trio = {p: edge_list(p) for p in ("competesWith", "prevailsOver", "defeasibleUnder")}
    csec = sections.get("conclusion") or sections.get("conclusions") or ""
    verdict = _judge(f"""BOARD HOLDING (conclusion section):
{csec[:4000]}

DISCUSSION (tail):
{(sections.get('discussion') or '')[-4000:]}

COMMITTED OBLIGATION-COMPETITION STRUCTURE:
{json.dumps(trio, indent=1)[:2500]}

Rubric: scope-specification and dissolution resolutions (duty met / no error /
enumerated non-competing duties) warrant NO edges; a genuine conflict the board
RESOLVES warrants prevailsOver with the winner matching the holding; a conflict
the board leaves unresolved warrants competesWith without prevailsOver. Judge
whether the committed structure (including emptiness) matches this case's
holding. Output JSON: {{"structure_matches_holding": true/false, "why": "one
sentence with a verbatim holding quote", "wrong_winner": null or {{"stored": "...",
"holding_favors": "..."}}}}""")
    if verdict is None:
        return _check("S6_defeasibility_sanity", "warning", "judge_unavailable",
                      {"trio": {k: len(v) for k, v in trio.items()}})
    bad = (not verdict.get("structure_matches_holding", True)) or verdict.get("wrong_winner")
    verdict["trio_counts"] = {k: len(v) for k, v in trio.items()}
    return _check("S6_defeasibility_sanity", "warning",
                  "warning" if bad else "pass", verdict)


def s7_decision_points(case_id, sections) -> dict:
    rows = _rows(case_id, "canonical_decision_point")
    if not rows:
        return _check("S7_decision_points", "warning", "warning",
                      {"note": "no decision points stored"})
    verdict = _judge(f"""CASE FACTS:
{(sections.get('facts') or '')[:4000]}

BOARD HOLDING (conclusion section):
{(sections.get('conclusion') or sections.get('conclusions') or '')[:3000]}

COMMITTED DECISION POINTS:
{_fmt_rows(rows, ['focus', 'decision_question', 'boardResolution', 'boardChosenOption'], cap=6)}

MODELING CONVENTION: decision points are ANALYTICAL CONSTRUCTIONS -- the
synthesis frames the case's real tensions as explicit choices, so a decision
point need not be quoted from the text; that is by design, not invention.
Flag as invented ONLY a point whose choice belongs to a cited precedent's
actors or contradicts the facts of this case. Judge each decision point:
(a) is its underlying tension real in THIS case? (b) does boardResolution
match the actual holding? Output JSON: {{"invented": ["focus ..."], "resolution_mismatches":
[{{"focus": "...", "stored": "...", "holding_says": "...", "evidence": "quote"}}],
"notes": "one sentence"}}""")
    if verdict is None:
        return _check("S7_decision_points", "warning", "judge_unavailable", {})
    bad = verdict.get("invented") or verdict.get("resolution_mismatches")
    return _check("S7_decision_points", "warning",
                  "warning" if bad else "pass", verdict)


# --- driver -------------------------------------------------------------------

def audit_case(case_id: int) -> dict:
    sections = _sections(case_id)
    g = _graph(case_id)
    if g is None:
        return {"case_id": case_id, "overall_status": "critical",
                "checks": [_check("S0_graph_exists", "critical", "critical",
                                  {"note": "no committed TTL"})]}
    checks = [
        s1_precedent_designators(case_id, g, sections),
        s2_agent_grounding(case_id, g, sections),
        s3_board_questions(case_id, sections),
        s4_conclusions(case_id, sections),
        s5_obligations(case_id, g, sections),
        s6_defeasibility(case_id, g, sections),
        s7_decision_points(case_id, sections),
    ]
    crit = sum(1 for c in checks if c["status"] == "critical")
    warn = sum(1 for c in checks
               if c["status"] in ("warning", "judge_unavailable"))
    overall = "critical" if crit else ("warning" if warn else "pass")
    return {"case_id": case_id, "overall_status": overall,
            "critical_count": crit, "warning_count": warn, "checks": checks}


def store_result(result: dict) -> None:
    from app import db
    from sqlalchemy import text as sql
    db.session.execute(sql(
        "INSERT INTO case_verification_results "
        "(case_id, verification_date, protocol_version, overall_status, "
        " critical_count, warning_count, info_count, check_results, notes) "
        "VALUES (:c, :d, :p, :s, :cc, :wc, 0, :r, :n)"),
        {"c": result["case_id"], "d": datetime.now(timezone.utc),
         "p": PROTOCOL_VERSION, "s": result["overall_status"],
         "cc": result.get("critical_count", 0), "wc": result.get("warning_count", 0),
         "r": json.dumps(result["checks"], default=str),
         "n": "semantic sampling audit (rebuild per-batch gate)"})
    db.session.commit()


def _sample_ids(batch_file: str, n: int, pins: List[int]) -> List[int]:
    ids = []
    for line in open(batch_file):
        line = line.split("#")[0].strip()
        if line:
            ids.append(int(line))
    from app.models.temporary_rdf_storage import TemporaryRDFStorage
    from sqlalchemy import func
    from app import db
    counts = dict(db.session.query(
        TemporaryRDFStorage.case_id, func.count())
        .filter(TemporaryRDFStorage.case_id.in_(ids),
                TemporaryRDFStorage.is_published.is_(True))
        .group_by(TemporaryRDFStorage.case_id).all())
    chosen = [i for i in pins if i in ids]
    ranked = sorted((i for i in ids if i not in chosen), key=lambda i: counts.get(i, 0))
    for pick in (ranked[0], ranked[-1]):  # min and max entity count
        if pick not in chosen:
            chosen.append(pick)
    rng = random.Random(20260712)
    pool = [i for i in ids if i not in chosen]
    rng.shuffle(pool)
    chosen.extend(pool[: max(0, n - len(chosen))])
    return chosen[:max(n, len([p for p in pins if p in ids]))]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("case_id", nargs="?", type=int)
    ap.add_argument("--batch", nargs="+", type=int)
    ap.add_argument("--batch-file")
    ap.add_argument("--sample", type=int, default=5)
    ap.add_argument("--pin", nargs="+", type=int, default=[])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    from app import create_app
    app = create_app()
    with app.app_context():
        if args.batch_file:
            ids = _sample_ids(args.batch_file, args.sample, args.pin)
        elif args.batch:
            ids = args.batch
        elif args.case_id:
            ids = [args.case_id]
        else:
            ap.error("give a case id, --batch, or --batch-file")
        print(f"semantic audit ({PROTOCOL_VERSION}) over cases: {ids}")
        worst = "pass"
        for cid in ids:
            result = audit_case(cid)
            if not args.dry_run:
                store_result(result)
            print(f"case {cid}: {result['overall_status'].upper()} "
                  f"(critical {result.get('critical_count', 0)}, "
                  f"warnings {result.get('warning_count', 0)})")
            for c in result["checks"]:
                if args.verbose or c["status"] != "pass":
                    print(f"  [{c['status']:<17}] {c['check']}: "
                          f"{json.dumps(c['detail'], default=str)[:400]}")
            order = {"pass": 0, "warning": 1, "critical": 2}
            if order[result["overall_status"]] > order[worst]:
                worst = result["overall_status"]
        print(f"batch semantic verdict: {worst.upper()}")
        return {"pass": 0, "warning": 0, "critical": 2}[worst]


if __name__ == "__main__":
    sys.exit(main())
