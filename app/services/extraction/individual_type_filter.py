"""Multi-purpose individual/type filter for extracted entities.

A recurring extraction defect, seen first on resources, is a TYPE emitted as an
INDIVIDUAL: an abstract concept dressed up as an instance, usually a relabeling of
its own class with a generic suffix ("Peer Review Conduct Standard Instance"
instance_of "Peer Review Conduct Standard"). Prompt rules alone are gamed by
re-suffixing, so this filter removes them mechanically. It is NOT resource-specific:
the same shape (an individual that is really its own class, or content that belongs
to a different component) can occur for any of the nine components.

The pattern is one shared mechanism plus per-component DATA:

  Tier 1 (deterministic, universal): flag an individual whose label, after stripping
    generic type words, is the same concept as its declared class. This "self-instance"
    is the component-agnostic signal that a type was emitted as an instance.
  Triage: a self-instance with no instance marker is a CLEAR DROP; an individual with
    a concrete instance marker that is not a self-instance is a CLEAR KEEP; everything
    else is AMBIGUOUS.
  Tier 2 (LLM judge, batched): ONE call over the ambiguous remainder only (skipped when
    empty), prompted with the component's criteria. The LLM is the final judge, so a
    real artifact that happens to share its class name is kept and a subtle type is
    dropped.

What a valid individual IS for each component lives in CRITERIA as data, not code.
Reapplying the filter to another extraction is adding a CRITERIA entry. Best-effort:
failures are logged and the input is returned unchanged; without the LLM only Tier-1
self-instances drop. Every drop is logged (no silent drops).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from app.services.extraction.rules import Rule

logger = logging.getLogger(__name__)

# Generic type words stripped before comparing an individual label to its class:
# the words a type label carries ("Standard", "Norm") and the words the model
# appends to manufacture a pseudo-instance ("Instance", "Practice").
_GENERIC_WORDS = {
    "instance", "instances", "standard", "standards", "norm", "norms",
    "obligation", "obligations", "principle", "principles", "constraint",
    "constraints", "requirement", "requirements", "practice", "practices",
    "framework", "frameworks", "policy", "policies", "guideline", "guidelines",
    "rule", "rules", "provision", "provisions", "doctrine", "clause", "type",
    "the", "a", "an", "of", "for", "to", "and", "in", "on",
}


@dataclass(frozen=True)
class FilterCriteria:
    """Per-component DATA describing what a valid INDIVIDUAL is (the only
    component-specific part of the filter)."""
    component: str          # extraction type, e.g. "resources"
    unit: str               # what an individual of this component is
    keep_examples: str      # concrete examples of valid individuals
    drop_kinds: str         # what to drop (the type / wrong-component cases)
    instance_marker: Optional[str] = None  # regex; a match argues "real instance"
    # Fields whose presence shows the case tied the individual to an actor (an actor relied on
    # it or cited it): a populated one is a Tier-1 KEEP signal for a non-self-instance, the same
    # way a concrete marker is (lesson L4: "Local Environmental Standards", used_by Engineer L,
    # was judged ambiguous and dropped by the model judge).
    reliance_fields: tuple = ()


# Per-component fields handed to the Tier-2 judge as the item's DETAIL, in display order (lesson
# L4: the extractor used to read used_in_context / description, which the Rs individual lacks, so
# the judge saw an empty detail). Components without a CRITERIA row still get a detail here, so
# the same builder serves every component.
DETAIL_FIELDS: Dict[str, tuple] = {
    "resources": ("topic", "document_title", "used_by", "cited_by", "provision_codes"),
    "roles": ("case_involvement", "actor"),
    "states": ("subject", "triggering_event", "active_period"),
    "principles": ("concrete_expression", "interpretation"),
    "obligations": ("obligation_statement", "obligated_party"),
    "constraints": ("constraint_statement", "constrained_entity"),
    "capabilities": ("case_context", "possessed_by"),
}

# Fields on an individual that NAME another extracted entity it rests on. An individual whose
# label appears in such a field of a sibling is depended on and is never dropped.
_REFERENCE_FIELDS = ("source", "required_for_obligations", "resource", "relies_on", "depends_on")


# Registry of per-component criteria. Add a component by adding a row here (data),
# not by writing new filter code. Resources is the first entry.
CRITERIA: Dict[str, FilterCriteria] = {
    "resources": FilterCriteria(
        component="resources",
        unit=("a concrete, separately citable knowledge ARTIFACT: a named document, "
              "a numbered code provision, a specific precedent, a specific "
              "published standard, or the regulations, statutes, or standards the case "
              "says an actor relied on or had to follow (named generically or not)"),
        keep_examples=('"NSPE Code of Ethics", "NSPE Code Section III.7.a", "BER Case 92-6", "ASCE 7-22", '
                       '"Local Environmental Standards" (the standards the facts say Engineer L relied on)'),
        drop_kinds=("a TYPE (an abstract norm/standard/practice stated only in general "
                    "terms, which is a class not an instance, including a relabeling of "
                    "its own class with a generic suffix like \"Instance\"/\"Practice\"); "
                    "or WRONG COMPONENT (an obligation, principle, duty, or constraint, "
                    "which belong to other components, not resources). A regulation or "
                    "standard the facts say a named actor relied on, used, or was bound by is an "
                    "INSTANCE (keep), even when the case does not name its publisher or number; "
                    "so is a resource that other extracted entities of the case rest on"),
        instance_marker=r"(\b\d|\b(section|case|no|number|part|article|clause)\b)",
        reliance_fields=("used_by", "cited_by"),
    ),
}


# --- deterministic core (component-agnostic) -----------------------------------

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().replace("_", " ").replace("-", " ")).strip()


def _strip_generic(label: str) -> str:
    toks = re.sub(r"[^a-z0-9 ]", " ", _norm(label)).split()
    return " ".join(t for t in toks if t not in _GENERIC_WORDS)


def self_instance_flag(label: str, class_ref: str) -> bool:
    """The individual is a self-instance of its class: after stripping generic type
    words the two name the same concept. Universal across components."""
    a, b = _strip_generic(label), _strip_generic(class_ref)
    if not a or not b:
        return False
    if a == b:
        return True
    aset, bset = set(a.split()), set(b.split())
    if aset and bset and (aset <= bset or bset <= aset):
        return True
    return False


@dataclass(frozen=True)
class _SelfInstanceCtx:
    """The (label, declared-class) pair the Tier-1 self-instance rule inspects."""
    label: str
    class_ref: str


# Tier-1 deterministic check as a named, inspectable Rule (see app.services.extraction.rules).
# It is the single component-agnostic signal that a TYPE was emitted as an INDIVIDUAL: the
# label, after generic type words are stripped, names the same concept as its declared class.
# A match here (with no concrete instance marker) is the CLEAR DROP in _triage.
SELF_INSTANCE_RULE: Rule[_SelfInstanceCtx] = Rule(
    "self_instance",
    "individual label equals its declared class after stripping generic type words",
    lambda c: self_instance_flag(c.label, c.class_ref),
)


def _has_marker(label: str, marker: Optional[str]) -> bool:
    return bool(marker) and re.search(marker, _norm(label)) is not None


def _class_ref(it: Dict[str, Any]) -> str:
    """The individual's declared class/type, across the per-component field names."""
    for k in ("resource_class", "instance_of", "state_class", "role_class",
              "principle_class", "obligation_class", "constraint_class",
              "capability_class", "class", "type"):
        v = it.get(k)
        if v:
            return str(v)
    return ""


def _relied_on(it: Dict[str, Any], reliance_fields) -> bool:
    """True when a reliance field (used_by / cited_by for resources) names an actor."""
    for k in reliance_fields or ():
        v = it.get(k)
        if isinstance(v, list):
            v = next((x for x in v if x), None)
        if v and str(v).strip():
            return True
    return False


def compute_flags(individuals: List[Dict[str, Any]], marker: Optional[str],
                  reliance_fields=()) -> List[Dict[str, Any]]:
    out = []
    for it in individuals:
        label = it.get("label") or it.get("identifier") or ""
        out.append({
            "self_instance": SELF_INSTANCE_RULE.test(_SelfInstanceCtx(label, _class_ref(it))),
            "marker": _has_marker(label, marker),
            "relied": _relied_on(it, reliance_fields),
        })
    return out


def _triage(flags):
    """A self-instance with no instance signal is a CLEAR DROP; a non-self-instance with a concrete
    marker OR a reliance signal (an actor relied on it or cited it) is a CLEAR KEEP; the rest is
    AMBIGUOUS (the Tier-2 judge). The reliance signal is the lesson-L4 addition."""
    clear_keep, clear_drop, ambiguous = [], [], []
    for i, fl in enumerate(flags):
        signal = fl["marker"] or fl.get("relied", False)
        if fl["self_instance"] and not signal:
            clear_drop.append(i)
        elif signal and not fl["self_instance"]:
            clear_keep.append(i)
        else:
            ambiguous.append(i)
    return clear_keep, clear_drop, ambiguous


def judge_dict(individual: Any, concept_type: str) -> Dict[str, Any]:
    """The plain dict the filter inspects for one extracted individual (a Pydantic model or a
    dict): label, its declared class, a per-component DETAIL built from DETAIL_FIELDS (topic,
    used_by, the statement, ...), the first verbatim quote, and the reliance and reference fields
    themselves, so both the deterministic tier and the Tier-2 judge see what the case says about
    the individual rather than an empty description (lesson L4)."""
    def _get(name):
        if isinstance(individual, dict):
            return individual.get(name)
        return getattr(individual, name, None)

    cls = ''
    for k in ('resource_class', 'instance_of', 'state_class', 'role_class',
              'principle_class', 'obligation_class', 'constraint_class',
              'capability_class'):
        v = _get(k)
        if v:
            cls = str(v)
            break
    parts = []
    for field in DETAIL_FIELDS.get((concept_type or '').lower(), ()):
        v = _get(field)
        if isinstance(v, list):
            v = ', '.join(str(x) for x in v if x)
        if v and str(v).strip():
            parts.append(f"{field}: {str(v).strip()}")
    for fallback in ('used_in_context', 'description'):
        v = _get(fallback)
        if v and str(v).strip():
            parts.append(str(v).strip())
    refs = _get('text_references') or []
    if not isinstance(refs, list):
        refs = [refs]
    quote = next((str(r).strip() for r in refs if r and str(r).strip()), '')
    out = {
        'label': (_get('identifier') or _get('name') or _get('label') or ''),
        'instance_of': cls,
        'definition': '; '.join(parts),
        'quote': quote,
        'text_references': [str(r) for r in refs if r],
    }
    crit = CRITERIA.get((concept_type or '').lower())
    for k in (crit.reliance_fields if crit else ()) + _REFERENCE_FIELDS:
        v = _get(k)
        if v:
            out[k] = v
    return out


def referenced_labels(dicts: List[Dict[str, Any]]) -> set:
    """Normalized labels that the given individuals NAME in a reference field (an obligation's
    source, a capability's required_for_obligations, ...): the entities the batch rests on."""
    out = set()
    for it in dicts:
        for k in _REFERENCE_FIELDS:
            v = it.get(k)
            vals = v if isinstance(v, list) else [v]
            for x in vals:
                if x and str(x).strip():
                    out.add(_norm(str(x)))
    return out


# --- Tier 2: batched LLM judge over the ambiguous subset -----------------------

def _load_filter_template():
    """Load the editable 'individual_filter' prompt template (prompt editor -> Shared prompts ->
    Individual / type filter). A separate function so a unit test can inject a stub without a DB /
    app context. Raises (no fallback) if unseeded; _llm_classify catches and degrades to the
    deterministic tier, which is the filter's documented best-effort path."""
    from app.models.extraction_prompt_template import ExtractionPromptTemplate
    tmpl = ExtractionPromptTemplate.get_active_template(0, 'individual_filter')
    if tmpl is None:
        raise RuntimeError(
            "No 'individual_filter' prompt template in extraction_prompt_templates. "
            "Seed it: docs-internal/scripts/seed_individual_filter_template.py")
    return tmpl


def _build_prompt(individuals, flags, crit: FilterCriteria) -> str:
    blocks = []
    for i, (it, fl) in enumerate(zip(individuals, flags)):
        hint = []
        if fl["self_instance"]:
            hint.append("LABEL IS ESSENTIALLY ITS CLASS (likely a type, not an instance)")
        if fl["marker"]:
            hint.append("has a concrete instance marker -> likely a real instance")
        if fl.get("relied"):
            hint.append("the case ties it to an actor (used_by / cited_by) -> likely a real instance")
        quote = (it.get('quote') or '')
        if not quote:
            refs = it.get('text_references') or []
            quote = str(refs[0]) if isinstance(refs, list) and refs else ''
        block = (
            f"[{i}] individual: \"{(it.get('label') or it.get('identifier') or '')[:90]}\"\n"
            f"    declared class: \"{_class_ref(it)[:90]}\"\n"
            f"    detail: \"{(it.get('definition') or it.get('used_in_context') or '')[:240]}\"\n"
        )
        if quote:
            block += f"    quote: \"{quote[:200]}\"\n"
        block += f"    signals: {'; '.join(hint) or 'none'}"
        blocks.append(block)
    # The Tier-2 judge prompt is an editable DB template (prompt editor -> Shared prompts ->
    # Individual / type filter). Render it with the per-component criteria + the item blocks rather
    # than hardcoding the prose here.
    return _load_filter_template().render(
        component=crit.component, unit=crit.unit, keep_examples=crit.keep_examples,
        drop_kinds=crit.drop_kinds, items="\n\n".join(blocks))


def _llm_classify(individuals, flags, crit, client=None, model=None) -> Optional[Dict[int, bool]]:
    if not individuals:
        return {}
    try:
        if model is None:
            from model_config import ModelConfig
            model = ModelConfig.get_tier_model("default")
        from app.services.llm.factory import streaming_provider_for_client

        provider = streaming_provider_for_client(client, model)
        if provider is None:
            logger.warning("individual_filter: no streaming client; deterministic fallback")
            return None
        prompt = _build_prompt(individuals, flags, crit)
        raw = provider.stream_complete(
            messages=[{"role": "user", "content": prompt}],
            system=(f"You decide whether each {crit.component} individual is a genuine "
                    "individual (keep) or a type/wrong-component entry (drop). Strict JSON only."),
            max_tokens=2048, temperature=0.0, model=model,
        ).text
        from app.utils.llm_utils import extract_json_from_response
        data = extract_json_from_response(raw)
        if not isinstance(data, dict):
            return None
        out: Dict[int, bool] = {}
        for k, v in data.items():
            try:
                idx = int(k)
            except (TypeError, ValueError):
                continue
            if 0 <= idx < len(individuals):
                out[idx] = not (isinstance(v, str) and v.strip().lower().startswith("drop"))
        return out
    except Exception as e:
        logger.warning("individual_filter: LLM classify failed (%s); deterministic fallback", e)
        return None


# --- driver --------------------------------------------------------------------

def filter_individuals(individuals: List[Dict[str, Any]],
                       criteria: Union[str, FilterCriteria, None],
                       use_llm: bool = True, client=None, model=None,
                       depended_on=None) -> Dict[str, Any]:
    """Partition extracted individuals into kept/dropped, removing types emitted as
    instances (and wrong-component entries).

    ``criteria`` is a component name (looked up in CRITERIA), a FilterCriteria, or
    None (deterministic self-instance only, no LLM, no marker). Returns
    {"kept", "dropped": [(item, reason)], "resolver", "llm_items"}.

    Tier 1 settles the clear self-instances and clearly-marked (or relied-on) instances for
    free; Tier 2 makes ONE batched LLM call over the ambiguous remainder only (skipped when
    empty). Without the LLM, ambiguous items are kept and only self-instances drop.

    ``depended_on`` is a set of labels (any spelling) that other extracted entities rest on
    (see referenced_labels); an individual whose label is among them is kept regardless of the
    tiers (lesson L4: a dropped resource left the obligation, state, and capability that rested
    on it without a Resource node)."""
    crit = CRITERIA.get(criteria) if isinstance(criteria, str) else criteria
    if not individuals:
        return {"kept": [], "dropped": [], "resolver": None, "llm_items": 0}

    marker = crit.instance_marker if crit else None
    flags = compute_flags(individuals, marker, crit.reliance_fields if crit else ())
    clear_keep, clear_drop, ambiguous = _triage(flags)
    protected = {_norm(str(x)) for x in (depended_on or ()) if x}
    if protected:
        for i, it in enumerate(individuals):
            label = _norm(str(it.get("label") or it.get("identifier") or ""))
            if label and label in protected and i not in clear_keep:
                if i in clear_drop:
                    clear_drop.remove(i)
                if i in ambiguous:
                    ambiguous.remove(i)
                clear_keep.append(i)
                logger.info("individual_filter: %r kept, other extracted entities depend on it", label)

    verdicts = None
    if use_llm and crit and ambiguous:
        sub = [individuals[i] for i in ambiguous]
        sub_flags = [flags[i] for i in ambiguous]
        raw = _llm_classify(sub, sub_flags, crit, client=client, model=model)
        if raw is not None:
            verdicts = {ambiguous[j]: raw.get(j, True) for j in range(len(ambiguous))}
    resolver = "llm" if (ambiguous and verdicts is not None) else (
        "deterministic" if ambiguous else "deterministic-only")

    keep_idx = set(clear_keep)
    reason: Dict[int, str] = {i: "deterministic:self-instance" for i in clear_drop}
    for i in ambiguous:
        if verdicts is not None and not verdicts.get(i, True):
            reason[i] = "llm:type-or-wrong-component"
        else:
            keep_idx.add(i)

    kept, dropped = [], []
    for i, it in enumerate(individuals):
        if i in keep_idx:
            kept.append(it)
        else:
            dropped.append((it, reason.get(i, "dropped")))
            logger.info("individual_filter[%s]: dropped %r (class=%r, %s)",
                        crit.component if crit else "?",
                        (it.get("label") or it.get("identifier")), _class_ref(it),
                        reason.get(i, "dropped"))
    return {"kept": kept, "dropped": dropped, "resolver": resolver,
            "llm_items": len(ambiguous) if (verdicts is not None) else 0}
