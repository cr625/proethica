"""Grounding context for decision-point parsing (case 8 review, lessons L1, L3, L4).

The refinement parser used to trust two proxies for entity categories: a
URI naming prefix (``#Action_`` / ``#Event_``) for the action slot, and the
slot the model put a URI in for the obligation and constraint slots. Case 8
(NSPE 24-1) broke both: its committed actions carry label-minted URIs
(``case-8#Work_Suspension_Request``), so every decision point lost its
actions, and the model placed the Obligation "Engineer L Faithful Agent
Duty" in the constraint slot, where the commit-time type check dropped it.

This module reads the categories from the record itself: the committed case
graph (``rdf:type proeth-core:<Category>``, the materialized direct type every
commit asserts), falling back to the stored Step-3 temporal rows for the
Action/Event individuals when no committed TTL exists yet, plus the
algorithmic candidates (whose slots E1-E3 typed by construction). It also
carries the committed ``competesWith`` / ``prevailsOver`` edges, so a
decision point's competing pair can be derived from the graph instead of
from the model's slot assignment, and the case's cited provision set for the
backing-provision check. No LLM, no network.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set

logger = logging.getLogger(__name__)

CORE_NS = "http://proethica.org/ontology/core#"
CASE_NS_TEMPLATE = "http://proethica.org/ontology/case/{case_id}#"

NINE_CATEGORIES = ("Role", "Principle", "Obligation", "State", "Resource",
                   "Action", "Event", "Capability", "Constraint")
COMPETITION_PREDICATES = ("competesWith", "prevailsOver")


def frag(uri: Optional[str]) -> str:
    """Local name of a URI in either the short (``case-8#X``) or the full
    committed form; '' when the value carries no fragment."""
    if not uri or "#" not in str(uri):
        return ""
    return str(uri).rsplit("#", 1)[1]


@dataclass
class DPGroundingContext:
    """What the parser may trust about the case's individuals."""
    case_id: Optional[int] = None
    source: str = "none"                       # committed_graph | stored_rows | candidates | none
    label_to_uri: Dict[str, str] = field(default_factory=dict)   # lowercase label -> uri
    label_of: Dict[str, str] = field(default_factory=dict)       # uri -> label
    category_of: Dict[str, str] = field(default_factory=dict)    # full uri -> category
    category_by_frag: Dict[str, str] = field(default_factory=dict)
    competitors: Dict[str, List[str]] = field(default_factory=dict)  # frag -> competitor uris
    cited_provision_codes: Set[str] = field(default_factory=set)     # normalized codes
    allowed_action_uris: Set[str] = field(default_factory=set)       # candidate option actions

    # -- registration -------------------------------------------------------
    def register(self, uri: str, category: Optional[str], label: Optional[str] = None) -> None:
        if not uri:
            return
        uri = str(uri)
        if category:
            self.category_of.setdefault(uri, category)
            f = frag(uri)
            if f:
                self.category_by_frag.setdefault(f, category)
        if label:
            self.label_of.setdefault(uri, label)
            self.label_to_uri.setdefault(label.lower(), uri)

    def add_competition(self, a: str, b: str) -> None:
        for x, y in ((a, b), (b, a)):
            fx = frag(x) or str(x)
            lst = self.competitors.setdefault(fx, [])
            if str(y) not in lst:
                lst.append(str(y))

    # -- lookups ------------------------------------------------------------
    @property
    def known_uris(self) -> Set[str]:
        return set(self.category_of) | set(self.label_of) | set(self.label_to_uri.values())

    def knows(self, uri: Optional[str]) -> bool:
        if not uri:
            return False
        uri = str(uri)
        return uri in self.known_uris or (frag(uri) in self.category_by_frag if frag(uri) else False)

    def category_for(self, uri: Optional[str]) -> Optional[str]:
        """Category of a URI by exact match, then by fragment (the short
        ``case-N#X`` form the synthesis store carries resolves to the
        committed ``.../case/N#X`` individual by fragment, as analysis_edges
        does at commit)."""
        if not uri:
            return None
        uri = str(uri)
        if uri in self.category_of:
            return self.category_of[uri]
        return self.category_by_frag.get(frag(uri))

    def is_timeline_individual(self, uri: Optional[str]) -> bool:
        if uri and str(uri) in self.allowed_action_uris:
            return True
        return self.category_for(uri) in ("Action", "Event")

    def competitors_of(self, uri: Optional[str]) -> List[str]:
        if not uri:
            return []
        return sorted(self.competitors.get(frag(uri) or str(uri), []))

    def label_for(self, uri: Optional[str]) -> Optional[str]:
        if not uri:
            return None
        uri = str(uri)
        if uri in self.label_of:
            return self.label_of[uri]
        f = frag(uri)
        for u, lbl in self.label_of.items():
            if f and frag(u) == f:
                return lbl
        return None

    def resolve(self, label: Optional[str], llm_uri: Optional[str]) -> str:
        """Label -> URI through the known labels; an LLM-echoed URI is kept
        only when the record knows it (full form or fragment)."""
        if label:
            hit = self.label_to_uri.get(str(label).lower())
            if hit:
                return hit
        if llm_uri and self.knows(llm_uri):
            return str(llm_uri)
        return ""


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------

def context_from_graph(g, case_id: Optional[int] = None) -> DPGroundingContext:
    """Categories, labels and competition edges from a committed case graph."""
    from rdflib import RDF, RDFS, Namespace, URIRef
    core = Namespace(CORE_NS)
    ctx = DPGroundingContext(case_id=case_id, source="committed_graph")
    labels = {}
    for s, o in g.subject_objects(RDFS.label):
        labels.setdefault(str(s), str(o))
    for cat in NINE_CATEGORIES:
        for s in g.subjects(RDF.type, core[cat]):
            ctx.register(str(s), cat, labels.get(str(s)))
    # Agents (the decidedByAgent slot) sit outside the nine categories.
    for s in g.subjects(RDF.type, core["Agent"]):
        ctx.register(str(s), "Agent", labels.get(str(s)))
    # Every labelled individual stays resolvable by label even without a
    # materialized category (the pre-context behaviour of the parser).
    for s, lbl in labels.items():
        ctx.register(s, None, lbl)
    for pred in COMPETITION_PREDICATES:
        for a, b in g.subject_objects(URIRef(CORE_NS + pred)):
            ctx.add_competition(str(a), str(b))
    return ctx


def add_temporal_rows(ctx: DPGroundingContext, rows: Iterable, case_id: int) -> None:
    """Action/Event individuals from the stored Step-3 temporal rows (the
    fallback when no committed TTL exists). Both the converter's ``@id`` and
    the commit-time label-minted URI are registered, since either may be
    echoed by the model."""
    from app.services.commit.naming import safe_label
    case_ns = CASE_NS_TEMPLATE.format(case_id=case_id)
    for r in rows or []:
        rdf = getattr(r, "rdf_json_ld", None) or {}
        jtype = str(rdf.get("@type", "") or "")
        etype = str(getattr(r, "entity_type", "") or "").lower()
        if "Action" in jtype or "action" in etype:
            cat = "Action"
        elif "Event" in jtype or "event" in etype:
            cat = "Event"
        else:
            continue
        label = getattr(r, "entity_label", None) or rdf.get("rdfs:label")
        for uri in (rdf.get("@id"), getattr(r, "entity_uri", None),
                    f"{case_ns}{safe_label(label)}" if label else None):
            if uri:
                ctx.register(str(uri), cat, label)
    if ctx.source == "none":
        ctx.source = "stored_rows"


def add_candidates(ctx: DPGroundingContext, top_candidates) -> None:
    """Slot-typed URIs from the algorithmic candidates (E3 composed the role,
    obligation and constraint slots from the typed extraction, so they are
    trusted as such) plus the option actions as an action allowlist."""
    for item in top_candidates or []:
        candidate = item[0] if isinstance(item, tuple) else item
        g = getattr(candidate, "grounding", None)
        if g is not None:
            if getattr(g, "role_uri", None):
                ctx.register(g.role_uri, "Role", getattr(g, "role_label", None))
            if getattr(g, "obligation_uri", None):
                ctx.register(g.obligation_uri, "Obligation", getattr(g, "obligation_label", None))
            if getattr(g, "constraint_uri", None):
                ctx.register(g.constraint_uri, "Constraint", getattr(g, "constraint_label", None))
        for opt in getattr(candidate, "options", None) or []:
            a_uri = getattr(opt, "action_uri", None)
            if a_uri:
                ctx.allowed_action_uris.add(str(a_uri))
                ctx.register(str(a_uri), "Action", getattr(opt, "action_label", None))
    if ctx.source == "none" and top_candidates:
        ctx.source = "candidates"


def add_cited_provisions(ctx: DPGroundingContext, codes: Iterable, conclusions: Iterable = ()) -> None:
    """The case's cited provision set: the References-section codes plus the
    codes the Board conclusions cite, normalized."""
    from app.utils.provision_codes import normalize_provision_code
    from app.services.step4_synthesis.qc_refs import is_board_explicit
    for raw in codes or []:
        n = normalize_provision_code(raw)
        if n:
            ctx.cited_provision_codes.add(n)
    for c in conclusions or []:
        if not isinstance(c, dict) or not is_board_explicit(c, "C"):
            continue
        for raw in (c.get("cited_provisions") or c.get("citedProvisions") or []):
            n = normalize_provision_code(raw)
            if n:
                ctx.cited_provision_codes.add(n)


def filter_backing_provisions(codes: List[str], ctx: DPGroundingContext, focus_id: str = "") -> List[str]:
    """Drop backing provisions the case never cites (case 8 DP3 cited II.1.f
    and DP4 cited II.2.a, provisions absent from the opinion). An empty cited
    set disables the check: nothing to validate against."""
    from app.utils.provision_codes import normalize_provision_code
    if not ctx.cited_provision_codes:
        return list(codes)
    kept = []
    for raw in codes:
        n = normalize_provision_code(raw)
        if n and n in ctx.cited_provision_codes:
            kept.append(raw)
        else:
            logger.info("decision point %s: backing provision %r is not cited by the case "
                        "(cited set %s); dropped", focus_id or "?", raw,
                        sorted(ctx.cited_provision_codes))
    return kept
