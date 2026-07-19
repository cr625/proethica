"""
Decision-point / CPR / question / conclusion TTL enrichment helpers.

Extracted verbatim from the tail of ontserve_commit_service.py (god-file
split, Item 1 Step 1.2). These were already module-level functions there;
names are unchanged. ontserve_commit_service.py re-exports them so existing
imports keep working.

PROETHICA is redeclared here (rather than imported back from
ontserve_commit_service, which imports this module) to avoid a circular
import; rdflib Namespace equality is string-based, so this is behaviorally
identical to the shared constant in ontserve_commit_service.py.
"""

from rdflib import Graph, Literal, Namespace, URIRef, XSD

PROETHICA = Namespace("http://proethica.org/ontology/intermediate#")


def emit_decision_point_enrichment(g: Graph, uri: URIRef, rdf_data: dict) -> None:
    """DecisionPoint analytic literals (the Chapter-3 spec fields the Phase-3
    synthesis persists): the Toulmin summary slots, the board-resolution
    narrative, the two ranking scores (xsd:decimal), the provision
    designations, the numbered options, and the board-chosen option.

    Module-level with REPLACE semantics -- every owned predicate is cleared
    before re-emission -- so the live commit serializer and the gold-15
    backfill share one idempotent implementation and cannot drift."""
    d = rdf_data or {}
    toulmin = d.get('toulmin') or {}
    for pred in ('boardResolution', 'intensityScore', 'qcAlignmentScore',
                 'toulminClaim', 'toulminData', 'toulminWarrant',
                 'toulminRebuttal', 'toulminQualifier', 'boardChosenOption',
                 'citedProvision', 'option'):
        g.remove((uri, PROETHICA[pred], None))
    if d.get('board_resolution'):
        g.add((uri, PROETHICA['boardResolution'], Literal(d['board_resolution'])))
    for key, pred in (('intensity_score', 'intensityScore'),
                      ('qc_alignment_score', 'qcAlignmentScore')):
        v = d.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            g.add((uri, PROETHICA[pred], Literal(str(v), datatype=XSD.decimal)))
    for key, pred in (('claim', 'toulminClaim'),
                      ('data_summary', 'toulminData'),
                      ('warrants_summary', 'toulminWarrant'),
                      ('rebuttals_summary', 'toulminRebuttal'),
                      ('qualifier', 'toulminQualifier')):
        if toulmin.get(key):
            g.add((uri, PROETHICA[pred], Literal(toulmin[key])))
    # One designation set: the Toulmin backing when carried, else the row's
    # provision_labels (the two are the same list in practice; emitting both
    # would double every code). Same citedProvision predicate the conclusion
    # emission uses.
    for code in (toulmin.get('backing_provisions')
                 or d.get('provision_labels') or []):
        if code:
            g.add((uri, PROETHICA['citedProvision'], Literal(str(code))))
    for i, opt in enumerate(d.get('options') or []):
        if not (isinstance(opt, dict) and opt.get('description')):
            continue
        label = (opt.get('label') or '').strip()
        text = (f"{i + 1}. {label}: {opt['description']}" if label
                else f"{i + 1}. {opt['description']}")
        g.add((uri, PROETHICA['option'], Literal(text)))
        if opt.get('is_board_choice') and label:
            g.add((uri, PROETHICA['boardChosenOption'], Literal(label)))


def emit_cpr_enrichment(g: Graph, uri: URIRef, rdf_data: dict) -> None:
    """CodeProvisionReference relevantExcerpt literals ('[section] text', one
    per excerpt). REPLACE semantics; shared by the serializer and the gold-15
    backfill. The appliesTo dicts are deliberately NOT flattened here -- they
    become object edges via the analysis-record edge applier, which carries
    each application's reasoning on the provenance derivation."""
    g.remove((uri, PROETHICA['relevantExcerpt'], None))
    for ex in ((rdf_data or {}).get('relevantExcerpts') or []):
        if isinstance(ex, dict) and ex.get('text'):
            sec = (ex.get('section') or '').strip()
            text = f"[{sec}] {ex['text']}" if sec else str(ex['text'])
            g.add((uri, PROETHICA['relevantExcerpt'], Literal(text)))


_Q_TYPE_NAMES = {'board_explicit': 'Board question', 'implicit': 'Implicit question',
                 'principle_tension': 'Principle-tension question',
                 'theoretical': 'Theoretical question', 'counterfactual': 'Counterfactual question'}


def _readable_question_label(rdf_data: dict) -> str:
    """Human-readable rdfs:label for a committed EthicalQuestion: the decoded
    category and within-category number plus a snippet of the question text
    ('Implicit question 2: If Engineer T sincerely believed ...'). The URI
    fragment keeps the stable Question_<n> form; only the label changes."""
    try:
        n = int(rdf_data.get('questionNumber'))
    except (TypeError, ValueError):
        return ''
    qtype = rdf_data.get('questionType') or 'board_explicit'
    kind = _Q_TYPE_NAMES.get(qtype, 'Question')
    ordinal = n if n < 100 else n % 100
    text = (rdf_data.get('questionText') or '').strip()
    snippet = (text[:57].rstrip() + '...') if len(text) > 60 else text
    return f"{kind} {ordinal}: {snippet}" if snippet else f"{kind} {ordinal}"


def _readable_conclusion_label(rdf_data: dict) -> str:
    """Human-readable rdfs:label for a committed EthicalConclusion, mirroring
    _readable_question_label: board conclusions are numbered 1-9, analytical
    conclusion families use 100-offset numbering."""
    try:
        n = int(rdf_data.get('conclusionNumber'))
    except (TypeError, ValueError):
        return ''
    kind = 'Board conclusion' if n < 100 else 'Analytical conclusion'
    ordinal = n if n < 100 else n % 100
    text = (rdf_data.get('conclusionText') or '').strip()
    snippet = (text[:57].rstrip() + '...') if len(text) > 60 else text
    return f"{kind} {ordinal}: {snippet}" if snippet else f"{kind} {ordinal}"
