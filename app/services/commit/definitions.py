"""
Deterministic definition composition for committed individuals (case-8 review, L1).

Fifty-nine committed individuals of case 8 carried neither ``skos:definition``
nor ``rdfs:comment``: the nine States (``StateIndividual`` has no description
field), the EthicalQuestion / EthicalConclusion / DecisionPoint analysis
records (their text lives in dedicated predicates and the generic definition
emitter skips those types), the CausalChain reifications and the timeline. The
case page resolver indexes only definition-bearing entries, so no state mention
could be linked in the case text, the defeasibility view hover on the licensing
state was empty, and OntServe cards showed a bare label.

``compose_definition`` builds a definition from the fields the individual
already carries, with no model call and no randomness, so a recommit yields
the same text. States compose as ``<subject>. Triggered when
<triggeringEvent>. Holds <activePeriod>.`` Questions and conclusions take their
question text and conclusion text. Decision points take the focus, else the
decision question. Causal chains take the cause-to-effect sentence plus the
causal language. The timeline takes its label and member counts. Temporal
relations, actions and events without a description take the label plus the
evidence or the temporal marker. Any other individual takes the first
narrative literal its row carries (caseInvolvement, obligationStatement,
constraintStatement, concreteExpression, interpretation).

An empty string means nothing deterministic can be said; the emitter then
leaves the individual as it was.
"""

from typing import Any, Dict, Optional

# Leading words of an activePeriod phrase that read as a lowercase continuation
# after "Holds" ("Holds from the setback onward"). Any other leading word is kept
# verbatim so proper names and acronyms are never lowercased.
_TEMPORAL_CONNECTIVES = frozenset({
    'from', 'during', 'until', 'after', 'before', 'while', 'throughout', 'since',
    'once', 'when', 'upon', 'at', 'in', 'for', 'as', 'between', 'following',
    'starting', 'beginning', 'over', 'through', 'till', 'to', 'the', 'a', 'an',
})

_NARRATIVE_FALLBACK_KEYS = (
    'caseInvolvement', 'obligationStatement', 'constraintStatement',
    'concreteExpression', 'interpretation', 'description',
)


def _first(source: Optional[Dict[str, Any]], *keys: str) -> str:
    """First non-empty value among ``keys`` in ``source`` (a list takes its
    first element), stripped, or ''."""
    if not isinstance(source, dict):
        return ''
    for key in keys:
        value = source.get(key)
        if isinstance(value, list):
            value = value[0] if value else None
        if value in (None, '', [], {}):
            continue
        if isinstance(value, dict):
            continue
        text = str(value).strip()
        if text:
            return text
    return ''


def _sentence(text: str) -> str:
    """Normalize whitespace and terminate the sentence with a period unless it
    already ends with terminal punctuation."""
    text = ' '.join(str(text or '').split()).strip()
    if not text:
        return ''
    while text and text[-1] in ',;:':
        text = text[:-1].rstrip()
    if not text:
        return ''
    if text[-1] in '.?!':
        return text
    return text + '.'


def _continuation(text: str) -> str:
    """Lowercase a leading temporal connective so the phrase continues a
    sentence ("From the setback onward" becomes "from the setback onward")."""
    text = ' '.join(str(text or '').split())
    if not text:
        return ''
    head, _, rest = text.partition(' ')
    if head.lower() in _TEMPORAL_CONNECTIVES and head[:1].isupper() and head[1:].islower():
        return head.lower() + (' ' + rest if rest else '')
    return text


def _state_definition(label: str, rdf_data: Dict[str, Any]) -> str:
    props = rdf_data.get('properties') if isinstance(rdf_data.get('properties'), dict) else {}
    subject = _first(props, 'subject') or _first(rdf_data, 'subject')
    trigger = (_first(props, 'triggeringEvent', 'triggering_event')
               or _first(rdf_data, 'triggeringEvent', 'triggering_event'))
    period = (_first(props, 'activePeriod', 'active_period')
              or _first(rdf_data, 'activePeriod', 'active_period'))
    parts = [_sentence(subject or label)]
    if trigger:
        parts.append(_sentence(f"Triggered when {trigger}"))
    if period:
        parts.append(_sentence(f"Holds {_continuation(period)}"))
    return ' '.join(p for p in parts if p)


def _causal_chain_definition(label: str, rdf_data: Dict[str, Any]) -> str:
    cause = _first(rdf_data, 'proeth:cause', 'cause')
    effect = _first(rdf_data, 'proeth:effect', 'effect')
    language = _first(rdf_data, 'proeth:causalLanguage', 'causalLanguage')
    if cause and effect:
        head = _sentence(f"Causal chain in which {cause} leads to {effect}")
    else:
        head = _sentence(f"Causal chain {label}") if label else ''
    tail = _sentence(language) if language else ''
    return ' '.join(p for p in (head, tail) if p)


def _timeline_definition(label: str, rdf_data: Dict[str, Any]) -> str:
    actions = _first(rdf_data, 'proeth:actionCount', 'actionCount')
    events = _first(rdf_data, 'proeth:eventCount', 'eventCount')
    total = _first(rdf_data, 'proeth:totalElements', 'totalElements')
    name = label or 'Case timeline'
    if actions and events:
        detail = f"{actions} actions and {events} events"
        if total:
            detail += f" ({total} elements)"
        return _sentence(f"{name}: the ordered sequence of {detail} extracted from the case record")
    return _sentence(f"{name}: the ordered sequence of actions and events extracted from the case record")


def _temporal_definition(label: str, rdf_data: Dict[str, Any]) -> str:
    """Allen relations, actions and events that arrived without a description."""
    description = _first(rdf_data, 'proeth:description', 'description')
    if description:
        return _sentence(description)
    evidence = _first(rdf_data, 'proeth:evidence', 'evidence')
    marker = _first(rdf_data, 'proeth:temporalMarker', 'temporalMarker')
    if not label:
        return ''
    if evidence:
        return ' '.join(p for p in (_sentence(label), _sentence(f"Evidence: {evidence}")) if p)
    if marker:
        return _sentence(f"{label}, {_continuation(marker)}")
    return _sentence(label)


def compose_definition(extraction_type: Optional[str], label: Optional[str],
                       rdf_data: Optional[Dict[str, Any]]) -> str:
    """Compose a definition for an individual that carries none.

    ``extraction_type`` is the working-store row type (``states``,
    ``ethical_question``, ``canonical_decision_point``,
    ``temporal_dynamics_enhanced``, ...), ``label`` the committed rdfs:label and
    ``rdf_data`` the row's ``rdf_json_ld``. Returns '' when the row carries no
    field a deterministic definition can be built from.
    """
    et = (extraction_type or '').lower()
    label = ' '.join(str(label or '').split())
    d = rdf_data if isinstance(rdf_data, dict) else {}

    if et == 'states':
        return _state_definition(label, d)
    if et in ('ethical_question', 'question_generated'):
        return _sentence(_first(d, 'questionText', 'question_text')) or _sentence(label)
    if et == 'ethical_conclusion':
        return _sentence(_first(d, 'conclusionText', 'conclusion_text')) or _sentence(label)
    if et == 'canonical_decision_point':
        focus = _first(d, 'description', 'focus')
        question = _first(d, 'decision_question', 'decisionQuestion')
        return _sentence(focus or question) or _sentence(label)

    at_type = str(d.get('@type') or '')
    if 'CausalChain' in at_type:
        return _causal_chain_definition(label, d)
    if at_type == 'time:TemporalEntity' or at_type.endswith('TemporalEntity'):
        return _timeline_definition(label, d)
    if 'temporal_dynamics' in et or at_type:
        return _temporal_definition(label, d)

    props = d.get('properties') if isinstance(d.get('properties'), dict) else {}
    narrative = _first(props, *_NARRATIVE_FALLBACK_KEYS) or _first(d, *_NARRATIVE_FALLBACK_KEYS)
    return _sentence(narrative) if narrative else ''
