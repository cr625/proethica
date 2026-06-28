"""Commit-time canonicalization: role+facet decomposition over the committed case TTL.

Runs at commit (alongside materialize_edges_on_ttl). For every individual typed to a compound role
class that the reference sheet marks do_not_mint with a decompose recipe, it rewrites the graph into the
BFO-correct canonical pattern (proven Pellet-consistent, see
docs-internal/reextraction/canonicalization-snapshots/20260624-bfo-pattern/):

  - retype the individual from the compound role class to the canonical Role class (reuse, not mint);
  - materialize the fused behavioral State as a separate proeth-core:State individual that `affects`
    the bearer Agent (an SDC depending on its bearer; never via hasRole/hasState), and
    `activatesObligation` where the recipe gives one;
  - materialize the recipe's Obligation (obligatedParty the Agent) where present;
  - drop the now-instance-free compound class declaration.

Deterministic (driven by the curated sheet recipes, not the LLM), domain-aware (all IRIs via the seam),
and idempotent enough to run once per commit. Class reuse for non-decomposed compounds is handled by the
matcher alias tier (entity_matcher); this module handles the structural role+facet split the matcher
cannot (it creates new State/Obligation individuals + edges).
"""
from __future__ import annotations

from rdflib import Graph, RDF, RDFS, OWL, URIRef, Literal, Namespace

try:
    from .domain_config import active_domain
    from .reference_sheet import get_sheet, norm
except ImportError:  # pragma: no cover - tooling path
    from domain_config import active_domain
    from reference_sheet import get_sheet, norm

PROV = Namespace("http://www.w3.org/ns/prov#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")


def _localname(uri) -> str:
    s = str(uri)
    return s.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _label_words(local: str) -> str:
    import re
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", local).replace("_", " ").strip()


def _via_prop(via: str, CORE: Namespace, PROETH: Namespace) -> URIRef:
    # recipe via like "core#affects" / "core#derivedFromPrinciple"; default affects.
    v = (via or "core#affects").strip()
    ns, _, local = v.partition("#")
    if not local:
        local = ns
        ns = "core"
    return (PROETH if ns.startswith("inter") else CORE)[local]


def canonicalize_ttl(case_id, ttl_path, write_back: bool = True) -> dict:
    cfg = active_domain()
    rs = get_sheet()
    CORE = Namespace(cfg.core_ns)
    PROETH = Namespace(cfg.intermediate_ns)

    g = Graph()
    g.parse(str(ttl_path), format="turtle")

    res = {"roles_decomposed": 0, "states_materialized": 0,
           "obligations_materialized": 0, "compound_classes_removed": 0}

    def _declare(cls_uri: URIRef, core_local: str):
        g.add((cls_uri, RDF.type, OWL.Class))
        g.add((cls_uri, RDFS.subClassOf, CORE[core_local]))

    def _mint_individual(frag: str, cls_uri: URIRef, category: str, label: str) -> URIRef:
        ind = URIRef(cfg.case_iri(case_id, frag))
        g.add((ind, RDF.type, cls_uri))
        g.add((ind, RDF.type, OWL.NamedIndividual))
        # Materialized direct type (CMT-1): the canonical core category as a direct
        # rdf:type proeth-core:<Category> (the type a reasoner infers from cls_uri's
        # subClassOf-core chain), replacing the retired proeth:conceptCategory literal.
        g.add((ind, RDF.type, CORE[category]))
        g.add((ind, RDFS.label, Literal(label)))
        g.add((ind, PROV.wasGeneratedBy, Literal("canonicalization: role+facet decomposition")))
        return ind

    # Each owl:Class whose normalized local-name matches a Role-component do_not_mint recipe.
    for cls in set(g.subjects(RDF.type, OWL.Class)):
        recipe = rs.recipes.get(norm(_localname(cls)))
        if not recipe or recipe.get("_component") != "Role":
            continue
        role_local = recipe.get("role")
        if not role_local or not isinstance(role_local, str) or " " in role_local:
            continue  # need a single canonical role class to retype to
        canon_role = PROETH[role_local]
        _declare(canon_role, "Role")

        instances = list(g.subjects(RDF.type, cls))
        if not instances:
            continue

        for ind in instances:
            agent = next(iter(g.subjects(CORE["hasRole"], ind)), None)
            # retype the individual to the canonical role
            g.remove((ind, RDF.type, cls))
            g.add((ind, RDF.type, canon_role))
            res["roles_decomposed"] += 1

            # --- materialize the fused State (the role+facet split) ---
            st = recipe.get("state")
            obl_iri_from_state = None
            if isinstance(st, dict) and st.get("iri"):
                st_local = st["iri"]
                st_cls = PROETH[st_local]
                _declare(st_cls, "State")
                st_ind = _mint_individual(f"{_localname(ind)}__{st_local}", st_cls,
                                          "State", _label_words(st_local))
                if agent is not None:
                    g.add((st_ind, _via_prop(st.get("via"), CORE, PROETH), agent))  # affects -> Agent
                res["states_materialized"] += 1

            # --- materialize the recipe Obligation, if any (obligatedParty -> Agent) ---
            ob = recipe.get("obligation")
            if isinstance(ob, dict) and ob.get("iri"):
                ob_local = ob["iri"]
                ob_cls = PROETH[ob_local]
                _declare(ob_cls, "Obligation")
                ob_ind = _mint_individual(f"{_localname(ind)}__{ob_local}", ob_cls,
                                          "Obligation", _label_words(ob_local))
                if agent is not None:
                    g.add((ob_ind, _via_prop(ob.get("via", "core#obligatedParty"), CORE, PROETH), agent))
                res["obligations_materialized"] += 1

        # the compound class now has no instances -> drop its declaration
        for _, p, o in list(g.triples((cls, None, None))):
            g.remove((cls, p, o))
        res["compound_classes_removed"] += 1

    if write_back and any(res.values()):
        g.serialize(destination=str(ttl_path), format="turtle")
    res["_graph"] = g
    return res
