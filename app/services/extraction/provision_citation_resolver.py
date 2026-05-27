"""Resolve NSPE provision citation literals to nspe: CodeProvision IRIs.

Case ontologies carry board-conclusion citations as bare literals on
``proeth:citedProvision1..N`` (e.g. "II.4.a." or "I.6."). The NSPE Code of
Ethics ontology (OntServe id 246) declares each provision as a
``proeth-core:CodeProvision`` individual ``nspe:<frag>`` (dots -> underscores).
This module maps the dotted-code literals onto those IRIs and materializes a
``proeth-core:citesProvision`` object-property edge, so case reasoning can
traverse conclusion -> provision -> established Principle/Obligation/Constraint.

Only well-formed dotted codes that match an existing nspe node are mapped.
Verbose ("NSPE Code of Ethics Section 2"), Model-Law, and BER-case-precedent
literals are intentionally skipped (they are not NSPE code provisions or are
ambiguous). Deterministic, no LLM.
"""
from __future__ import annotations

import re
from typing import Optional, Set

NSPE_NS = "http://proethica.org/ontology/nspe#"
INTERMEDIATE_NS = "http://proethica.org/ontology/intermediate#"
CORE_CITES_PROVISION = "http://proethica.org/ontology/core#citesProvision"

# Roman-numeral section, optional dotted numeric subsections, optional single
# lowercase letter: I, I.1, II.1, II.1.a, III.9.d
_DOTTED = re.compile(r"^[IVX]+(\.[0-9]+)*(\.[a-z])?$")


def _frag(code: str) -> str:
    return code.replace(".", "_")


def _ancestors(code: str):
    parts = code.split(".")
    return [".".join(parts[: i + 1]) for i in range(len(parts))]


def normalize_citation(literal: str) -> Optional[str]:
    """A citation literal -> nspe fragment (e.g. 'II.4.a.' -> 'II_4_a'), or None
    if it is not a well-formed dotted NSPE code."""
    s = (literal or "").strip().rstrip(".").strip()
    if not s or not _DOTTED.match(s):
        return None
    return _frag(s)


def valid_fragments_from_codes(codes) -> Set[str]:
    """Valid nspe node fragments = every dotted ancestor of the given section
    codes (matches the nodes the NSPE ontology generator materializes)."""
    frags: Set[str] = set()
    for code in codes:
        for anc in _ancestors(code):
            frags.add(_frag(anc))
    return frags


def load_valid_fragments(conn) -> Set[str]:
    """Load valid fragments from a psycopg2 connection to ai_ethical_dm."""
    cur = conn.cursor()
    cur.execute("SELECT section_code FROM guideline_sections WHERE guideline_id = 1")
    return valid_fragments_from_codes(code for (code,) in cur.fetchall())


class ProvisionCitationResolver:
    def __init__(self, valid_fragments: Set[str]):
        self.valid = valid_fragments

    def resolve(self, literal: str) -> Optional[str]:
        frag = normalize_citation(literal)
        if frag and frag in self.valid:
            return NSPE_NS + frag
        return None


def _is_cited_provision_pred(p) -> bool:
    local = str(p).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return local.startswith("citedProvision")


def apply_cites_provision_edges(g, resolver: ProvisionCitationResolver) -> int:
    """Add ``proeth-core:citesProvision nspe:<frag>`` for each resolvable
    ``citedProvisionN`` literal in graph ``g``. Returns the number of new edges.
    Idempotent: skips edges already present.
    """
    from rdflib import URIRef, Literal

    cites = URIRef(CORE_CITES_PROVISION)
    new_edges = set()
    for s, p, o in g:
        if isinstance(o, Literal) and _is_cited_provision_pred(p):
            iri = resolver.resolve(str(o))
            if iri:
                edge = (s, cites, URIRef(iri))
                if edge not in g:
                    new_edges.add(edge)
    for e in new_edges:
        g.add(e)
    return len(new_edges)


def apply_cites_provision_on_ttl(ttl_path) -> int:
    """Resolve citedProvisionN literals to nspe: IRIs on one case TTL and add
    proeth-core:citesProvision edges, writing back when any are added.

    Deterministic (no LLM). Loads valid NSPE fragments from the live
    ai_ethical_dm guideline_sections via the active SQLAlchemy session. Returns
    the number of edges added. Raises on DB/parse errors -- callers that must
    not fail a commit should wrap this.
    """
    from pathlib import Path
    from rdflib import Graph
    from sqlalchemy import text
    from app.models import db

    codes = [r[0] for r in db.session.execute(
        text("SELECT section_code FROM guideline_sections WHERE guideline_id = 1")
    ).fetchall()]
    if not codes:
        return 0
    resolver = ProvisionCitationResolver(valid_fragments_from_codes(codes))

    ttl_path = Path(ttl_path)
    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    added = apply_cites_provision_edges(g, resolver)
    if added:
        g.serialize(destination=str(ttl_path), format="turtle")
    return added
