"""A small, coherent rule abstraction for text/label pattern filters.

Extraction has several deterministic checks that inspect an entity's *text* -- its label, its
supporting quotes, the present-case actor set -- and decide drop/keep (precedent-citation markers,
generic placeholders, foreign present-case actors). Written as standalone functions they drift
into scattered, per-filter custom code. This module gives them one home: each check is a named
``Rule`` (a predicate plus a human-readable description), and a ``RuleSet`` applies them uniformly,
reporting which rule fired so the decision is inspectable. Adding a new pattern filter is then one
``Rule`` declaration, not a new bespoke function and call site.

Scope note: this is the TEXT-pattern layer. Graph/ontology rules (disjointness, subClassOf chains,
property domains) are declarative SHACL shapes in OntServe, a separate and more appropriate layer
for RDF structure. Keep the two distinct: regex over labels belongs here; reasoning over the graph
belongs in SHACL.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Generic, List, Optional, Tuple, TypeVar

T = TypeVar("T")
C = TypeVar("C")  # the per-item context a RuleSet's rules inspect


@dataclass(frozen=True)
class Rule(Generic[C]):
    """A named text-pattern check. ``test(context)`` returns True when the rule MATCHES
    (i.e. the item should be dropped/flagged)."""
    name: str
    description: str
    test: Callable[[C], bool]


@dataclass(frozen=True)
class RuleHit:
    """The outcome for a dropped item: which rule fired and the item's label."""
    rule: str
    label: str


@dataclass
class RuleSet(Generic[C]):
    """An ordered set of rules over a shared context type. ``evaluate`` returns the name of the
    first matching rule (rules are independent; order only sets which name is reported when more
    than one would match). ``partition`` splits a list of items into (kept, hits)."""
    name: str
    rules: List[Rule[C]] = field(default_factory=list)

    def evaluate(self, context: C) -> Optional[str]:
        for rule in self.rules:
            if rule.test(context):
                return rule.name
        return None

    def matches(self, context: C) -> bool:
        return self.evaluate(context) is not None

    def partition(
        self,
        items: List[T],
        to_context: Callable[[T], C],
        get_label: Callable[[T], Optional[str]] | None = None,
    ) -> Tuple[List[T], List[RuleHit]]:
        """Partition items into (kept, dropped_hits). ``to_context`` builds the context a rule
        inspects from each item; ``get_label`` (optional) labels the hit for reporting."""
        kept: List[T] = []
        hits: List[RuleHit] = []
        for item in items:
            fired = self.evaluate(to_context(item))
            if fired:
                lbl = (get_label(item) if get_label else None) or ""
                hits.append(RuleHit(rule=fired, label=lbl))
            else:
                kept.append(item)
        return kept, hits
