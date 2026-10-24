"""Coherence checks shared by the commit-time edge resolvers.

The resolvers in ``state_edges`` and ``edge_spec`` pick a target for a free-text
description from a candidate pool (embedding shortlist, then a model select). The
review of NSPE case 24-1 (ProEthica case 8, October 2026) found that the picks
were never checked against what the graph already knows: the temporal order of
the happenings (``proeth:temporalSequence``), the causal chains, the extent of
each happening (instant or interval), the agent who performed an action, the
labels of the other extracted individuals, and the literals the individuals
carry. This module holds those checks as pure functions over an rdflib graph
and plain strings, so each resolver applies the same rule and each rule is
testable without a database or a model.

Groups:

  - sequence and extent readers for happenings (Action / Event individuals)
  - lexical helpers: normalization, token matching against extracted labels,
    agent naming, the named-target bound of a multi-select, duty-name detection
  - action modality (performed or prescribed), derived from the action record
  - Allen relation validation and the precedence (cycle) check
  - state-transition coherence over the committed fluent layer
  - cross-family guards: activation against defeasibility, scope against the
    active period

Every drop helper removes the edge together with the provenance node the
emitting family minted for it (``edge_resolution.remove_edge_prov``).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import TIME

from app.services.extraction.edge_resolution import remove_edge_prov

logger = logging.getLogger(__name__)

CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")

STATE_PROV_PREFIX = "state_edge_provenance_"
FLUENT_PROV_PREFIX = "fluent_edge_provenance_"

MODALITY_PERFORMED = "performed"
MODALITY_PRESCRIBED = "prescribed"


def _frag(iri) -> str:
    return str(iri).rsplit("#", 1)[-1]


# --- happenings: sequence, extent, labels ------------------------------------

def happenings(g: Graph) -> List[URIRef]:
    """The committed Action and Event individuals (direct core type)."""
    out: Set[URIRef] = set()
    for cat in (CORE.Action, CORE.Event):
        out.update(s for s in g.subjects(RDF.type, cat) if isinstance(s, URIRef))
    return sorted(out)


def happening_sequence(g: Graph, h) -> Optional[int]:
    """The ``proeth:temporalSequence`` ordinal of a happening, or None."""
    for o in g.objects(h, PROETH.temporalSequence):
        try:
            return int(str(o))
        except (TypeError, ValueError):
            continue
    return None


def happening_extent(g: Graph, h) -> Optional[str]:
    """``"instant"`` or ``"interval"`` from the ``proeth:temporalExtent`` literal, else
    from the type of the ``time:hasTime`` anchor; None when neither is recorded."""
    ext = g.value(h, PROETH.temporalExtent)
    if ext is not None:
        s = str(ext).strip().lower()
        if s in ("instant", "interval"):
            return s
    for t in g.objects(h, TIME.hasTime):
        if (t, RDF.type, TIME.ProperInterval) in g:
            return "interval"
        if (t, RDF.type, TIME.Instant) in g:
            return "instant"
    return None


def label_of(g: Graph, ind) -> str:
    for o in g.objects(ind, RDFS.label):
        return str(o)
    return _frag(ind)


def literal_by_local(g: Graph, s, local: str) -> str:
    """The first literal on ``s`` whose predicate local name is ``local``, in any
    namespace (the commit routes some literals to provenance predicates)."""
    for p, o in g.predicate_objects(s):
        if isinstance(o, Literal) and _frag(p) == local:
            return str(o)
    return ""


# --- lexical helpers ---------------------------------------------------------

_STOPWORDS = frozenset({
    "a", "an", "the", "of", "to", "in", "on", "at", "by", "for", "and", "or",
    "with", "about", "as", "from", "into", "under", "over", "during", "after",
    "before", "its", "his", "her", "their", "is", "was", "be", "been", "that",
    "this", "these", "those", "s", "per", "via", "regarding", "concerning",
})
GENERIC_DUTY_WORDS = frozenset({
    "obligation", "obligations", "duty", "duties", "responsibility",
    "responsibilities",
})
_GENERIC_STATE_WORDS = frozenset({"state", "condition", "status", "situation"})


def lexical_norm(s: Optional[str]) -> str:
    """Lowercase, CamelCase split, possessives dropped, hyphens joined
    (``non-disclosure`` and ``Nondisclosure`` normalize identically), punctuation
    removed, whitespace collapsed."""
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s or "")
    s = s.lower()
    s = re.sub(r"[’']s\b", "", s)
    s = s.replace("-", "")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _key(tok: str) -> str:
    # A 6-character prefix folds the common inflections (disclose/disclosure,
    # quantify/quantification, limits/limitations) without a stemmer.
    return tok[:6] if len(tok) > 6 else tok


def content_tokens(s: Optional[str], drop: Iterable[str] = ()) -> List[str]:
    """Normalized content-word keys of a phrase (stopwords and ``drop`` removed)."""
    dropset = set(drop)
    return [_key(t) for t in lexical_norm(s).split()
            if t not in _STOPWORDS and t not in dropset]


def lexical_candidates(desc: str, labels: Dict[URIRef, str],
                       drop: Iterable[str] = ()) -> List[URIRef]:
    """The individuals whose label and the description cover each other lexically:
    every content token of the label occurs in the description, or every content
    token of the description occurs in the label. Best overlap first. A one-token
    label must be at least four characters long."""
    dt = set(content_tokens(desc, drop))
    if not dt:
        return []
    scored: List[Tuple[int, str, URIRef]] = []
    for iri, label in labels.items():
        lt = set(content_tokens(label, drop))
        if not lt:
            continue
        if len(lt) == 1 and len(next(iter(lt))) < 4:
            continue
        if lt <= dt or dt <= lt:
            scored.append((len(lt & dt), str(iri), iri))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [iri for _n, _s, iri in scored]


def lexical_match(desc: str, labels: Dict[URIRef, str],
                  drop: Iterable[str] = ()) -> Optional[URIRef]:
    """The unique best lexical candidate, or None when there is none or the best
    overlap is shared (ambiguous: the caller falls through to the model)."""
    cands = lexical_candidates(desc, labels, drop)
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]
    dt = set(content_tokens(desc, drop))
    best = len(set(content_tokens(labels[cands[0]], drop)) & dt)
    second = len(set(content_tokens(labels[cands[1]], drop)) & dt)
    return cands[0] if best > second else None


def agents_named_in(desc: str, agents: Dict[URIRef, str]) -> List[URIRef]:
    """The agents whose label occurs as a phrase inside the description."""
    d = f" {lexical_norm(desc)} "
    out = []
    for iri, label in agents.items():
        nl = lexical_norm(label)
        if nl and f" {nl} " in d:
            out.append(iri)
    return out


def performers_of(g: Graph, h) -> Set[str]:
    """Normalized names of the agents who performed ``h``: the ``isPerformedBy``
    targets' labels plus the ``proeth:hasAgent`` literal (role parenthetical
    stripped). Empty for events and for actions without agent information."""
    names: Set[str] = set()
    for a in g.objects(h, CORE.isPerformedBy):
        nl = lexical_norm(label_of(g, a))
        if nl:
            names.add(nl)
    for lit in g.objects(h, PROETH.hasAgent):
        nl = lexical_norm(re.sub(r"\s*\([^)]*\)\s*$", "", str(lit)))
        if nl:
            names.add(nl)
    return names


def performed_by_other_agent(g: Graph, h, agent_label: str) -> bool:
    """True when ``h`` has performer information and none of it names
    ``agent_label`` (one contains the other after normalization)."""
    performers = performers_of(g, h)
    if not performers:
        return False
    a = lexical_norm(agent_label)
    return not any(a in p or p in a for p in performers)


_CONJUNCTION = re.compile(r"\s*;\s*|\s+(?:and|or|and/or|&|plus|as well as)\s+", re.I)


def named_target_bound(labels: Sequence[str]) -> int:
    """How many entities the source field names: one per label, more when a label
    lists several joined by a separator or a conjunction. Never below one. The
    bound on a multi-select: one description, at most one target unless the text
    lists several."""
    n = 0
    for lbl in labels:
        parts = [p for p in _CONJUNCTION.split(lbl or "") if p and p.strip()]
        n += max(1, len(parts))
    return max(n, 1)


_DUTY_HEAD = re.compile(r"^(?:duty|obligation|responsibility)\s+(?:to|of)\b", re.I)
_DUTY_TAIL = re.compile(r"\b(?:obligation|duty|responsibility)\s*$", re.I)


def names_duty(desc: str) -> bool:
    """True when the description is the NAME of a duty rather than a sentence about
    one: at most eight words, no sentence punctuation, title-cased, and headed or
    ended by a duty word. Such a description must match an extracted obligation
    lexically or resolve to nothing."""
    s = (desc or "").strip().rstrip(".")
    if not s or len(s.split()) > 8 or re.search(r"[.;:,!?]", s):
        return False
    if not (_DUTY_HEAD.match(s) or _DUTY_TAIL.search(s)):
        return False
    words = [w for w in s.split() if w.lower() not in _STOPWORDS]
    capitalized = sum(1 for w in words if w[:1].isupper())
    return bool(words) and capitalized / len(words) >= 0.7


def cites_state(text: str, state_label: str) -> bool:
    """True when ``text`` names the state: at least 60 percent of the state label's
    content tokens (generic state words dropped) occur in the text, and at least
    one token when the label has one content token, two otherwise."""
    st = set(content_tokens(state_label, drop=_GENERIC_STATE_WORDS))
    if not st:
        return False
    tt = set(content_tokens(text))
    hit = len(st & tt)
    need = 1 if len(st) == 1 else 2
    return hit >= need and hit / len(st) >= 0.6


# --- action modality ---------------------------------------------------------

PRESCRIBED_PHRASES = (
    "must not", "cannot ethically", "can not ethically", "would not be ethical",
    "unresolved endpoint", "would be unethical", "is not permitted to",
    "may not ethically", "ethically obligated to", "ethically required to",
    "should not have", "ought not",
)
_DEONTIC = re.compile(
    r"\b(?:must|should|shall|cannot|can not|ought|may not|required to|obligated to|would)\b",
    re.I)


def explicit_modality(value: Any) -> Optional[str]:
    """The stored modality (the ``proeth:modality`` of the action record, set at
    parse time by happening_checks.classify_action_modality from the verdict of the
    model and the Board-normative text references) when it is one of the two
    values, else None."""
    v = str(value or "").strip().lower()
    return v if v in (MODALITY_PERFORMED, MODALITY_PRESCRIBED) else None


def derive_action_modality(description: Optional[str], temporal_marker: Optional[str] = "",
                           source_section: Optional[str] = "", explicit: Any = None) -> str:
    """``performed`` or ``prescribed``. A stored modality (``explicit``) is taken as
    it stands, so the commit-time resolvers agree with the parse-time verdict.
    Without one (rows extracted before the field existed), an action is prescribed
    when its description or temporal marker carries one of the prescription
    phrases (the Board's conclusion restated as an action: "must not continue",
    "unresolved endpoint"), or when it was discovered in the discussion section
    and its text is deontic (must, should, cannot, ought, would). Everything else
    is performed."""
    stored = explicit_modality(explicit)
    if stored is not None:
        return stored
    text = f"{description or ''} {temporal_marker or ''}".lower()
    if any(p in text for p in PRESCRIBED_PHRASES):
        return MODALITY_PRESCRIBED
    if (source_section or "").strip().lower() == "discussion" and _DEONTIC.search(text):
        return MODALITY_PRESCRIBED
    return MODALITY_PERFORMED


def happening_description(g: Graph, h) -> str:
    """The description of a committed happening. The commit emitter writes the
    record's ``proeth:description`` as ``rdfs:comment``
    (ttl_emitters._add_temporal_fields); the ``proeth:description`` literal is read
    as well for graphs built another way."""
    for pred in (RDFS.comment, PROETH.description):
        v = g.value(h, pred)
        if v is not None and str(v).strip():
            return str(v)
    return ""


def happening_occurred(g: Graph, h) -> bool:
    """A happening occurred unless its committed record derives the prescribed
    modality (events are always occurrences). The committed ``proeth:modality``
    literal decides when present."""
    if (h, RDF.type, CORE.Event) in g and (h, RDF.type, CORE.Action) not in g:
        return True
    modality = derive_action_modality(
        happening_description(g, h),
        str(g.value(h, PROETH.temporalMarker) or ""),
        literal_by_local(g, h, "discoveredInSection"),
        explicit=g.value(h, PROETH.modality))
    return modality == MODALITY_PERFORMED


# --- Allen relations -----------------------------------------------------------

# The relations OWL-Time defines on proper intervals (the extent rule of the defect sweep and
# the case corrections): an instant endpoint makes them invalid. Overlaps and meets joined on
# 2026-10-24 (case 25-1 committed an intervalMeets with an instant endpoint).
TWO_INTERVAL_LOCALS = frozenset({
    "intervalEquals", "intervalDuring", "intervalContains", "intervalStarts",
    "intervalStartedBy", "intervalFinishes", "intervalFinishedBy",
    "intervalOverlaps", "intervalOverlappedBy", "intervalMeets", "intervalMetBy",
})
# +1: from precedes to (start order); -1: to precedes from.
ORDER_LOCALS = {
    "intervalBefore": 1, "before": 1, "intervalMeets": 1, "intervalOverlaps": 1,
    "intervalAfter": -1, "after": -1, "intervalMetBy": -1, "intervalOverlappedBy": -1,
}


def owl_time_local(owlprop: Optional[str]) -> str:
    return (owlprop or "").split(":")[-1].split("#")[-1].strip()


def evidence_is_verbatim(evidence: Optional[str], case_text: Optional[str]) -> bool:
    """True when the whole evidence quote (outer quotation marks and ellipses
    stripped) occurs verbatim in the case text, whitespace and case normalized.
    Reuses ``_check_quote_grounding`` from the causal extractor with the run length
    set past the quote length, so the whole span must match rather than any
    eight-word run of it. False when either text is empty."""
    from app.services.temporal_dynamics.extractors.causal_extractor import (
        _check_quote_grounding)
    ev = (evidence or "").strip().strip("\"'“”‘’").strip()
    ev = re.sub(r"^(?:\.\.\.|…)\s*|\s*(?:\.\.\.|…)$", "", ev).strip()
    if not ev or not (case_text or "").strip():
        return False
    probe = [{"causal_language": ev}]
    return _check_quote_grounding(probe, case_text, min_run_words=len(ev.split()) + 1) == 1


def precedence_graph(g: Graph) -> Dict[URIRef, Set[URIRef]]:
    """Adjacency ``u -> {v}`` meaning u precedes v, from the temporalSequence
    ordinals (every earlier happening precedes every later one) and the causal
    layer (a chain's cause precedes its effect, a causing action precedes its
    event)."""
    adj: Dict[URIRef, Set[URIRef]] = {}
    seqs = [(happening_sequence(g, h), h) for h in happenings(g)]
    seqs = [(s, h) for s, h in seqs if s is not None]
    for s1, h1 in seqs:
        for s2, h2 in seqs:
            if s1 < s2:
                adj.setdefault(h1, set()).add(h2)
    for chain in g.subjects(RDF.type, PROETH.CausalChain):
        for c in g.objects(chain, PROETH.cause):
            for e in g.objects(chain, PROETH.effect):
                if c != e:
                    adj.setdefault(c, set()).add(e)
    for ev, act in g.subject_objects(PROETH.causedByAction):
        if ev != act:
            adj.setdefault(act, set()).add(ev)
    return adj


def reaches(adj: Dict[URIRef, Set[URIRef]], u, v) -> bool:
    """True when ``v`` is reachable from ``u`` (u precedes v)."""
    seen: Set[Any] = set()
    stack = [u]
    while stack:
        n = stack.pop()
        if n == v:
            return True
        if n in seen:
            continue
        seen.add(n)
        stack.extend(adj.get(n, ()))
    return False


def allen_relation_problems(g: Graph, owlprop: Optional[str], from_iri, to_iri,
                            evidence: str = "", case_text: str = "",
                            adj: Optional[Dict[URIRef, Set[URIRef]]] = None) -> List[str]:
    """Why an Allen relation between two resolved endpoints must not be asserted.
    Empty when it may be. Checks: the relation's extent requirements (equals,
    during, contains, starts, finishes need two intervals), that both endpoints
    occurred, that the evidence is a verbatim span when case text is available,
    and that an ordering relation does not contradict the precedence graph (a
    cycle against temporalSequence or a causal chain). An endpoint that never
    resolved (None) is skipped; the relation is judged through the other one."""
    local = owl_time_local(owlprop)
    problems: List[str] = []
    ends = [end for end in (from_iri, to_iri) if end is not None]
    if local in TWO_INTERVAL_LOCALS:
        for end in ends:
            if happening_extent(g, end) == "instant":
                problems.append(f"{local} needs two intervals but {_frag(end)} is an instant")
    for end in ends:
        if not happening_occurred(g, end):
            problems.append(f"endpoint {_frag(end)} did not occur (prescribed, not performed)")
    if case_text and evidence and not evidence_is_verbatim(evidence, case_text):
        problems.append("evidence is not a verbatim span of the case text")
    direction = ORDER_LOCALS.get(local)
    if direction and adj is not None and len(ends) == 2:
        first, second = (from_iri, to_iri) if direction > 0 else (to_iri, from_iri)
        if reaches(adj, second, first):
            problems.append(f"{local} contradicts the temporalSequence or causal order "
                            f"({_frag(second)} precedes {_frag(first)})")
    return problems


# --- state transitions ----------------------------------------------------------

def _remove_transition_edge(g: Graph, case_id: int, state, h, pred) -> None:
    """Remove one start or end edge of a state together with its provenance node,
    in whichever direction the emitting family asserted it."""
    if pred in (CORE.initiates, CORE.terminates):
        g.remove((h, pred, state))
        remove_edge_prov(g, case_id, FLUENT_PROV_PREFIX, _frag(pred), h, state)
    else:
        g.remove((state, pred, h))
        remove_edge_prov(g, case_id, STATE_PROV_PREFIX, _frag(pred), state, h)


def state_transitions(g: Graph, state) -> List[Tuple[int, int, URIRef, List[URIRef]]]:
    """``(sequence, kind, happening, predicates)`` for every sequenced start (kind 0)
    or end (kind 1) of ``state``, one entry per (happening, kind) even when two
    families asserted the same transition, ordered by sequence then kind."""
    grouped: Dict[Tuple[URIRef, int], Tuple[int, List[URIRef]]] = {}

    def _add(h, kind, pred):
        s = happening_sequence(g, h)
        if s is None:
            return
        grouped.setdefault((h, kind), (s, []))[1].append(pred)

    for h in g.subjects(CORE.initiates, state):
        _add(h, 0, CORE.initiates)
    for h in g.objects(state, CORE.activatedByEvent):
        _add(h, 0, CORE.activatedByEvent)
    for h in g.subjects(CORE.terminates, state):
        _add(h, 1, CORE.terminates)
    for h in g.objects(state, CORE.terminatedByEvent):
        _add(h, 1, CORE.terminatedByEvent)
    out = [(s, kind, h, preds) for (h, kind), (s, preds) in grouped.items()]
    out.sort(key=lambda x: (x[0], x[1], str(x[2])))
    return out


def drop_fluent_reinitiation(g: Graph, case_id: int) -> int:
    """Cross-happening coherence of the fluent layer: walking each state's
    sequenced transitions in order, a start while the state already holds
    (re-initiation) and an end while it is already ended (terminated twice) are
    dropped with their provenance. The earliest transition of a run is kept.
    Returns the number of edges removed."""
    dropped = 0
    for state in sorted(set(g.subjects(RDF.type, CORE.State))):
        last: Optional[int] = None
        for seq, kind, h, preds in state_transitions(g, state):
            if kind == last:
                for pred in preds:
                    _remove_transition_edge(g, case_id, state, h, pred)
                    dropped += 1
                logger.info("Case %s: dropped %s of %s by %s (seq %s): the state is already %s",
                            case_id, "re-initiation" if kind == 0 else "second termination",
                            _frag(state), _frag(h), seq,
                            "holding" if kind == 0 else "ended")
                continue
            last = kind
    return dropped


def activation_precedes_trigger(g: Graph, happening, trigger) -> bool:
    """True when both are sequenced and the activating happening comes before the
    state's own trigger (an activation cannot precede its trigger)."""
    a, t = happening_sequence(g, happening), happening_sequence(g, trigger)
    return a is not None and t is not None and a < t


def later_happening_citing_state(g: Graph, state, terminator) -> Optional[URIRef]:
    """A happening sequenced after ``terminator`` whose description or label names
    the state (the state still holds there), or None."""
    t = happening_sequence(g, terminator)
    if t is None:
        return None
    label = label_of(g, state)
    for h in happenings(g):
        s = happening_sequence(g, h)
        if s is None or s <= t:
            continue
        text = f"{label_of(g, h)} {happening_description(g, h)}"
        if cites_state(text, label):
            return h
    return None


# --- cross-family guards -----------------------------------------------------

def drop_activation_defeasibility_conflicts(g: Graph, case_id: int) -> int:
    """No (S activatesObligation O) may coexist with (O defeasibleUnder S): a state
    cannot both bring a duty into force and be the context under which the duty
    yields. The defeasibility edge carries a verbatim-quoted derivation, so the
    embedding-resolved activation is the one dropped."""
    dropped = 0
    for s, o in list(g.subject_objects(CORE.activatesObligation)):
        if (o, CORE.defeasibleUnder, s) in g:
            g.remove((s, CORE.activatesObligation, o))
            remove_edge_prov(g, case_id, STATE_PROV_PREFIX, "activatesObligation", s, o)
            dropped += 1
            logger.info("Case %s: dropped activatesObligation(%s, %s): the obligation is "
                        "defeasibleUnder the same state", case_id, _frag(s), _frag(o))
    return dropped


def state_active_end(g: Graph, state) -> Optional[int]:
    """The latest sequence at which the state ends (terminates / terminatedByEvent),
    or None when no sequenced terminator is known."""
    ends = [s for s, kind, _h, _p in state_transitions(g, state) if kind == 1]
    return max(ends) if ends else None


_SCOPE_AFTER = re.compile(
    r"^\s*(?:after|following|once|upon|from|since|beginning with|starting with|subsequent to)"
    r"\b[\s,:-]*(.*)$", re.I | re.S)


def scope_start_sequence(g: Graph, obligation,
                         happening_labels: Optional[Dict[URIRef, str]] = None) -> Optional[int]:
    """The sequence at which an obligation's ``proeth:temporalScope`` begins, when
    the scope opens with "after"/"following"/"once"/... and the rest of it names
    one extracted happening lexically. None otherwise."""
    scope = str(g.value(obligation, PROETH.temporalScope) or "")
    m = _SCOPE_AFTER.match(scope)
    if not m:
        return None
    if happening_labels is None:
        happening_labels = {h: label_of(g, h) for h in happenings(g)}
    target = lexical_match(m.group(1), happening_labels)
    return happening_sequence(g, target) if target is not None else None


def drop_scope_postdating_activations(g: Graph, case_id: int) -> int:
    """Drop an activation whose target obligation's temporalScope begins after the
    state's active period ended (the state cannot activate a duty that comes into
    force only later)."""
    dropped = 0
    labels = {h: label_of(g, h) for h in happenings(g)}
    for s, o in list(g.subject_objects(CORE.activatesObligation)):
        end = state_active_end(g, s)
        if end is None:
            continue
        start = scope_start_sequence(g, o, labels)
        if start is not None and start > end:
            g.remove((s, CORE.activatesObligation, o))
            remove_edge_prov(g, case_id, STATE_PROV_PREFIX, "activatesObligation", s, o)
            dropped += 1
            logger.info("Case %s: dropped activatesObligation(%s, %s): the obligation's "
                        "temporalScope begins at seq %s, after the state ended at seq %s",
                        case_id, _frag(s), _frag(o), start, end)
    return dropped
