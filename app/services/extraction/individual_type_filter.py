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


# Registry of per-component criteria. Add a component by adding a row here (data),
# not by writing new filter code. Resources is the first entry.
CRITERIA: Dict[str, FilterCriteria] = {
    "resources": FilterCriteria(
        component="resources",
        unit=("a concrete, separately citable knowledge ARTIFACT: a named document, "
              "a numbered code provision, a specific precedent, or a specific "
              "published standard"),
        keep_examples='"NSPE Code of Ethics", "NSPE Code Section III.7.a", "BER Case 92-6", "ASCE 7-22"',
        drop_kinds=("a TYPE (an abstract norm/standard/practice stated only in general "
                    "terms, which is a class not an instance, including a relabeling of "
                    "its own class with a generic suffix like \"Instance\"/\"Practice\"); "
                    "or WRONG COMPONENT (an obligation, principle, duty, or constraint, "
                    "which belong to other components, not resources)"),
        instance_marker=r"(\b\d|\b(section|case|no|number|part|article|clause)\b)",
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


def compute_flags(individuals: List[Dict[str, Any]], marker: Optional[str]) -> List[Dict[str, Any]]:
    out = []
    for it in individuals:
        label = it.get("label") or it.get("identifier") or ""
        out.append({
            "self_instance": SELF_INSTANCE_RULE.test(_SelfInstanceCtx(label, _class_ref(it))),
            "marker": _has_marker(label, marker),
        })
    return out


def _triage(flags):
    clear_keep, clear_drop, ambiguous = [], [], []
    for i, fl in enumerate(flags):
        if fl["self_instance"] and not fl["marker"]:
            clear_drop.append(i)
        elif fl["marker"] and not fl["self_instance"]:
            clear_keep.append(i)
        else:
            ambiguous.append(i)
    return clear_keep, clear_drop, ambiguous


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
        blocks.append(
            f"[{i}] individual: \"{(it.get('label') or it.get('identifier') or '')[:90]}\"\n"
            f"    declared class: \"{_class_ref(it)[:90]}\"\n"
            f"    detail: \"{(it.get('definition') or it.get('used_in_context') or '')[:160]}\"\n"
            f"    signals: {'; '.join(hint) or 'none'}"
        )
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
        if client is None:
            from app.utils.llm_utils import get_llm_client
            client = get_llm_client()
        if model is None:
            from model_config import ModelConfig
            model = ModelConfig.get_claude_model("default")
        if not (hasattr(client, "messages") and hasattr(client.messages, "stream")):
            logger.warning("individual_filter: no streaming client; deterministic fallback")
            return None
        prompt = _build_prompt(individuals, flags, crit)
        chunks: List[str] = []
        from app.utils.llm_utils import direct_call_params
        with client.messages.stream(
            **direct_call_params(model, max_tokens=2048, temperature=0.0),
            system=(f"You decide whether each {crit.component} individual is a genuine "
                    "individual (keep) or a type/wrong-component entry (drop). Strict JSON only."),
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for t in stream.text_stream:
                chunks.append(t)
        from app.utils.llm_utils import extract_json_from_response
        data = extract_json_from_response("".join(chunks))
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
                       use_llm: bool = True, client=None, model=None) -> Dict[str, Any]:
    """Partition extracted individuals into kept/dropped, removing types emitted as
    instances (and wrong-component entries).

    ``criteria`` is a component name (looked up in CRITERIA), a FilterCriteria, or
    None (deterministic self-instance only, no LLM, no marker). Returns
    {"kept", "dropped": [(item, reason)], "resolver", "llm_items"}.

    Tier 1 settles the clear self-instances and clearly-marked instances for free;
    Tier 2 makes ONE batched LLM call over the ambiguous remainder only (skipped when
    empty). Without the LLM, ambiguous items are kept and only self-instances drop."""
    crit = CRITERIA.get(criteria) if isinstance(criteria, str) else criteria
    if not individuals:
        return {"kept": [], "dropped": [], "resolver": None, "llm_items": 0}

    marker = crit.instance_marker if crit else None
    flags = compute_flags(individuals, marker)
    clear_keep, clear_drop, ambiguous = _triage(flags)

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
