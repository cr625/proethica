"""
R -> P -> O dependency-chain edge extractor (KI2026 §3 materialization).

Asserts the three Role/Principle/Obligation object properties between
already-extracted typed individuals:

  - proeth-core:hasObligation       Role -> Obligation
  - proeth-core:adheresToPrinciple  Role -> Principle
  - proeth:derivedFromPrinciple     Obligation -> Principle

These were declared in the ontology but never materialized in the per-case
TTLs (the link lived only in narrative datatype fields). This module makes the
R->P->O chain SPARQL-traversable per case, with PROV-O provenance attaching
each edge to the verbatim narrative text that justifies it.

Design mirrors defeasibility_edges.py: streaming LLM call, IRI validation
against the supplied entity lists, dedupe. CRITICAL ADDITION: endpoints are
validated by conceptCategory (subject/object must be the property's
rdfs:domain/range category) so edges cannot force an individual into a
disjoint core class -- this preserves the OWL-DL consistency restored in the
KI2026 corpus repair.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from rdflib import Graph, Literal, RDF, RDFS, URIRef, Namespace

logger = logging.getLogger(__name__)

PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROETH_CORE = Namespace("http://proethica.org/ontology/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")

HAS_OBLIGATION = PROETH_CORE.hasObligation
ADHERES_TO = PROETH_CORE.adheresToPrinciple
DERIVED_FROM = PROETH.derivedFromPrinciple

# predicate -> (subject category, object category)
_PRED_CATEGORY = {
    "hasObligation": ("Role", "Obligation"),
    "adheresToPrinciple": ("Role", "Principle"),
    "derivedFromPrinciple": ("Obligation", "Principle"),
}
_PRED_URI = {
    "hasObligation": HAS_OBLIGATION,
    "adheresToPrinciple": ADHERES_TO,
    "derivedFromPrinciple": DERIVED_FROM,
}

PROPERTY_AXIOMS = """\
proeth-core:hasObligation a owl:ObjectProperty ;
    rdfs:domain proeth-core:Role ; rdfs:range proeth-core:Obligation ;
    rdfs:comment "Relates a role to its professional obligations."@en .
proeth-core:adheresToPrinciple a owl:ObjectProperty ;
    rdfs:domain proeth-core:Role ; rdfs:range proeth-core:Principle ;
    rdfs:comment "Relates a role to principles that guide its conduct."@en .
proeth:derivedFromPrinciple a owl:ObjectProperty ;
    rdfs:domain proeth-core:Obligation ; rdfs:range proeth-core:Principle ;
    rdfs:comment "Links obligation to the principle(s) it operationalizes."@en .\
"""

SYSTEM_PROMPT = (
    "You are an R->P->O dependency-chain extractor for the ProEthica D-tuple model. "
    "You link previously extracted Role, Principle, and Obligation individuals using "
    "exactly three proethica object properties. You must NOT invent classes, individuals, "
    "IRIs, or property names. Output STRICT JSON only -- no prose, no markdown fences.\n\n"
    "Property axioms (verbatim from the ontology):\n\n" + PROPERTY_AXIOMS + "\n\n"
    "Hard constraints:\n"
    "  1. predicate is exactly one of: hasObligation, adheresToPrinciple, derivedFromPrinciple.\n"
    "  2. hasObligation: subject is a ROLE iri, object is an OBLIGATION iri.\n"
    "  3. adheresToPrinciple: subject is a ROLE iri, object is a PRINCIPLE iri.\n"
    "  4. derivedFromPrinciple: subject is an OBLIGATION iri, object is a PRINCIPLE iri.\n"
    "  5. subject_iri and object_iri must each appear verbatim in the supplied lists. "
    "Copy them character-for-character.\n"
    "  6. Every edge must be supported by a verbatim source_text drawn from one of the "
    "narrative fields supplied (e.g. an obligation's obligatedparty/obligationstatement, "
    "a principle's invokedby, a role's relationships). Set source_text to that quote.\n"
    "  7. Only assert an edge when the narrative genuinely supports it. Omit speculative links."
)


@dataclass
class Indiv:
    iri: str
    label: str
    fields: Dict[str, str]


def _individuals_in_category(g: Graph, category: str) -> List[URIRef]:
    out = []
    for s, _, _ in g.triples((None, PROETH.conceptCategory, Literal(category))):
        out.append(s)
    return out


def _fields(g: Graph, ind: URIRef, names: List[str]) -> Dict[str, str]:
    d = {}
    for n in names:
        vals = [str(o) for o in g.objects(ind, PROETH[n])]
        if vals:
            d[n] = vals[0]
    return d


def gather(g: Graph) -> Tuple[List[Indiv], List[Indiv], List[Indiv]]:
    def mk(ind, names):
        lbl = g.value(ind, RDFS.label)
        return Indiv(str(ind), str(lbl) if lbl else str(ind).split("#")[-1], _fields(g, ind, names))
    roles = [mk(r, ["roleclass", "casecontext", "relationships"]) for r in _individuals_in_category(g, "Role")]
    principles = [mk(p, ["principleclass", "invokedby", "appliedto", "concreteexpression"])
                  for p in _individuals_in_category(g, "Principle")]
    obligations = [mk(o, ["obligationclass", "obligatedparty", "obligationstatement"])
                   for o in _individuals_in_category(g, "Obligation")]
    return roles, principles, obligations


def _fmt(items: List[Indiv]) -> str:
    if not items:
        return "(none)"
    out = []
    for it in items:
        block = [f"- IRI: <{it.iri}>", f"  label: {it.label}"]
        for k, v in it.fields.items():
            block.append(f"  {k}: {v[:240]}")
        out.append("\n".join(block))
    return "\n\n".join(out)


def build_prompt(roles, principles, obligations, case_id) -> str:
    return (
        f"Extract R->P->O dependency edges for case {case_id}.\n\n"
        f"ROLES (subject of hasObligation / adheresToPrinciple):\n{_fmt(roles)}\n\n"
        f"PRINCIPLES (object of adheresToPrinciple / derivedFromPrinciple):\n{_fmt(principles)}\n\n"
        f"OBLIGATIONS (object of hasObligation; subject of derivedFromPrinciple):\n{_fmt(obligations)}\n\n"
        "TASK: Assert hasObligation (which role bears which obligation), adheresToPrinciple "
        "(which role is guided by which principle), and derivedFromPrinciple (which obligation "
        "operationalizes which principle), using the narrative fields as evidence. "
        "If no edge is warranted, return an empty edges array.\n\n"
        'OUTPUT (strict JSON): {"edges": [{"predicate": "...", "subject_iri": "...", '
        '"object_iri": "...", "source_text": "...", "confidence": 0.9}]}'
    )


class RPOEdgeExtractor:
    def __init__(self, llm_client=None, model=None, temperature=0.1, max_tokens=32000):
        self._llm_client = llm_client
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def _client(self):
        if self._llm_client is None:
            from app.utils.llm_utils import get_llm_client
            self._llm_client = get_llm_client()
        return self._llm_client

    def _resolve_model(self):
        if self.model:
            return self.model
        from model_config import ModelConfig
        return ModelConfig.get_default_model()

    def _call(self, prompt) -> Optional[str]:
        client = self._client()
        model = self._resolve_model()
        if not (hasattr(client, "messages") and hasattr(client.messages, "stream")):
            logger.error("RPOEdgeExtractor requires an Anthropic streaming client")
            return None
        chunks: List[str] = []
        with client.messages.stream(
            model=model, max_tokens=self.max_tokens, temperature=self.temperature,
            system=SYSTEM_PROMPT, messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for t in stream.text_stream:
                chunks.append(t)
            final_msg = stream.get_final_message()
        if getattr(final_msg, "stop_reason", None) == "max_tokens":
            logger.warning(
                "R->P->O hit max_tokens (%d); response truncated, "
                "partial recovery will be attempted", self.max_tokens,
            )
        return "".join(chunks)

    @staticmethod
    def _recover_partial_edges(raw: str) -> List[Dict[str, Any]]:
        """Salvage edge objects from a truncated JSON response.

        R->P->O edges are flat objects (no nested braces in values), so each
        complete edge is a `{ ... }` block with no inner braces. Scanning for
        such blocks recovers every edge that landed before the max_tokens
        cutoff even when the enclosing array was never closed. Mirrors
        DefeasibilityEdgeExtractor._recover_partial_edges.
        """
        import json as _json
        import re as _re

        out: List[Dict[str, Any]] = []
        for m in _re.finditer(r"\{[^{}]*\}", raw):
            try:
                obj = _json.loads(m.group(0))
            except Exception:
                continue
            if isinstance(obj, dict) and "predicate" in obj and "subject_iri" in obj:
                out.append(obj)
        if out:
            logger.info("R->P->O partial-recovery salvaged %d edge(s)", len(out))
        return out

    def extract(self, case_id, roles, principles, obligations) -> List[Dict[str, Any]]:
        if not roles or (not obligations and not principles):
            return []
        raw = self._call(build_prompt(roles, principles, obligations, case_id))
        if not raw:
            return []
        from app.utils.llm_utils import extract_json_from_response
        try:
            data = extract_json_from_response(raw)
            edges = data.get("edges", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        except Exception as e:
            logger.warning(
                "Case %s: R->P->O full-JSON parse failed (%s); attempting "
                "per-edge recovery from possibly truncated response", case_id, e,
            )
            edges = self._recover_partial_edges(raw)

        role_iris = {r.iri for r in roles}
        principle_iris = {p.iri for p in principles}
        obligation_iris = {o.iri for o in obligations}
        cat_iris = {"Role": role_iris, "Principle": principle_iris, "Obligation": obligation_iris}

        valid: List[Dict[str, Any]] = []
        seen: Set[Tuple[str, str, str]] = set()
        def _clean(iri):
            # LLMs frequently echo IRIs wrapped in angle brackets / whitespace.
            return (iri or "").strip().lstrip("<").rstrip(">").strip()

        for e in edges:
            pred = e.get("predicate")
            s = _clean(e.get("subject_iri"))
            o = _clean(e.get("object_iri"))
            if pred not in _PRED_CATEGORY or not s or not o:
                continue
            scat, ocat = _PRED_CATEGORY[pred]
            # endpoint-category validation -- prevents disjoint-class clashes
            if s not in cat_iris[scat] or o not in cat_iris[ocat]:
                logger.info("Case %s: dropped %s edge (endpoint category/IRI mismatch)", case_id, pred)
                continue
            key = (pred, s, o)
            if key in seen:
                continue
            seen.add(key)
            valid.append({"predicate": pred, "subject_iri": s, "object_iri": o,
                          "source_text": (e.get("source_text") or "")[:500],
                          "confidence": float(e.get("confidence", 0.7))})
        logger.info("Case %s: R->P->O emitted %d edges", case_id, len(valid))
        return valid


def add_edges_to_graph(g: Graph, edges: List[Dict[str, Any]], case_id: int) -> int:
    case_ns = Namespace(f"http://proethica.org/ontology/case/{case_id}#")
    added = 0
    for i, e in enumerate(edges):
        s = URIRef(e["subject_iri"]); o = URIRef(e["object_iri"]); pred = _PRED_URI[e["predicate"]]
        if (s, pred, o) in g:
            continue
        g.add((s, pred, o))
        added += 1
        prov = case_ns[f"rpo_edge_provenance_{e['predicate']}_{i}"]
        g.add((prov, RDF.type, PROV.Derivation))
        g.add((prov, PROV.wasDerivedFrom, s))
        g.add((prov, PROV.wasDerivedFrom, o))
        if e.get("source_text"):
            g.add((prov, PROV.value, Literal(e["source_text"])))
        g.add((prov, RDFS.label, Literal(f"R->P->O edge: {e['predicate']}")))
    return added
