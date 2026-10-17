"""Post-parse checks on extracted ROLE individuals (case-8 review, lesson L9).

Two deterministic repairs the roles prompt states as rules but the parser did not enforce:

* ``reject_unsupported_professional``: role_kind professional is rejected (set to None, the
  unstated three-state value) for an individual that names no obligation the role generates
  (the D-TELEO rule: a professional role generates at least one obligation; if none can be named
  the role is participant, not professional). Case 8 typed the Board role professional with no
  obligation named.
* ``fold_duplicate_relational_facets``: a second RELATIONAL facet of an actor whose relationship
  targets are all counterparties an existing facet of the same actor already links to is folded
  into that facet (its relationships and role_category carried over), never kept as a new facet.
  Case 8 minted a faithful-agent facet beside the design-engineer facet that already carried
  hasClient to the same client. The occupational facets of an actor are never touched.

The checks operate on the Pydantic RoleIndividual models (or dicts with the same keys) and
return a small report; they are wired into UnifiedDualExtractor.extract behind apply_filters.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# A role class whose label names a relational standing toward a counterparty rather than an
# occupation. Matched on the normalized (lowercased, de-camelCased) label.
_RELATIONAL_FACET_TERMS = (
    'faithful agent', 'fiduciary', 'trustee', 'provider client', 'professional peer',
    'employer relationship', 'public responsibility', 'agent of', 'client agent',
)


def _norm(s: Any) -> str:
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', str(s or ''))
    return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()


def _get(obj: Any, name: str, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _set(obj: Any, name: str, value) -> None:
    if isinstance(obj, dict):
        obj[name] = value
    else:
        setattr(obj, name, value)


def _kind_value(v: Any) -> str:
    return str(getattr(v, 'value', v) or '').lower()


def _rel_pairs(ind: Any) -> List[Tuple[str, str, Any]]:
    """(normalized type, normalized target, the relationship object) for each relationship."""
    out = []
    for r in _get(ind, 'relationships', None) or []:
        rtype = _get(r, 'type', '')
        target = _get(r, 'target', '')
        if target:
            out.append((_norm(rtype), _norm(target), r))
    return out


def is_relational_facet(ind: Any) -> bool:
    """True when the individual's role class names a relational standing (see
    _RELATIONAL_FACET_TERMS) rather than an occupation."""
    label = _norm(_get(ind, 'role_class', ''))
    return any(term in label for term in _RELATIONAL_FACET_TERMS)


def reject_unsupported_professional(individuals: List[Any]) -> List[str]:
    """Set role_kind to None on every individual typed professional that names no obligation in
    generates_obligations. Returns the identifiers changed."""
    changed = []
    for ind in individuals:
        if _kind_value(_get(ind, 'role_kind')) != 'professional':
            continue
        named = [o for o in (_get(ind, 'generates_obligations', None) or []) if str(o).strip()]
        if named:
            continue
        ident = _get(ind, 'identifier', '') or _get(ind, 'name', '') or '?'
        logger.info("role_checks: %r typed professional but names no obligation; role_kind "
                    "rejected (left unstated)", ident)
        _set(ind, 'role_kind', None)
        changed.append(str(ident))
    return changed


def fold_duplicate_relational_facets(individuals: List[Any]) -> Tuple[List[Any], List[Dict[str, str]]]:
    """Fold a relational facet into the earlier facet of the same actor that already links the
    same counterparties. Returns (kept individuals, [{dropped, into}])."""
    kept: List[Any] = []
    folded: List[Dict[str, str]] = []
    for ind in individuals:
        actor = _norm(_get(ind, 'actor', ''))
        pairs = _rel_pairs(ind)
        host = None
        if actor and pairs and is_relational_facet(ind):
            targets = {t for _, t, _r in pairs}
            for prior in kept:
                if _norm(_get(prior, 'actor', '')) != actor or prior is ind:
                    continue
                prior_targets = {t for _, t, _r in _rel_pairs(prior)}
                if targets and targets <= prior_targets:
                    host = prior
                    break
        if host is None:
            kept.append(ind)
            continue
        # Carry the relational standing onto the existing facet: new (type, target) pairs,
        # the overflow relationships, and the role_category when the host has none.
        host_pairs = {(t, g) for t, g, _r in _rel_pairs(host)}
        host_rels = list(_get(host, 'relationships', None) or [])
        for t, g, r in pairs:
            if (t, g) not in host_pairs:
                host_rels.append(r)
                host_pairs.add((t, g))
        _set(host, 'relationships', host_rels)
        extra = list(_get(host, 'additional_relationships', None) or [])
        extra.extend(_get(ind, 'additional_relationships', None) or [])
        if extra:
            _set(host, 'additional_relationships', extra)
        if not _get(host, 'role_category') and _get(ind, 'role_category'):
            _set(host, 'role_category', _get(ind, 'role_category'))
        dropped = str(_get(ind, 'identifier', '') or _get(ind, 'name', '') or '?')
        into = str(_get(host, 'identifier', '') or _get(host, 'name', '') or '?')
        logger.info("role_checks: relational facet %r folded into %r (same actor, counterparties "
                    "already linked)", dropped, into)
        folded.append({'dropped': dropped, 'into': into})
    return kept, folded


def apply_role_checks(individuals: List[Any]) -> Tuple[List[Any], Dict[str, Any]]:
    """Run both checks. Returns (individuals, report)."""
    downgraded = reject_unsupported_professional(individuals)
    kept, folded = fold_duplicate_relational_facets(individuals)
    return kept, {'professional_rejected': downgraded, 'facets_folded': folded}
