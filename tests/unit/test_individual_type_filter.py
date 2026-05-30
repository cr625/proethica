"""Unit tests for the multi-purpose individual/type filter.

The deterministic tier (self-instance detection + triage) is exercised directly;
the batched LLM judge is exercised with a fake streaming client. The filter is
component-agnostic: a component plugs in via a CRITERIA row (data), so these tests
also confirm an ad-hoc FilterCriteria works for a non-resource component.
"""
from app.services.extraction import individual_type_filter as f
from app.services.extraction.individual_type_filter import (
    FilterCriteria, filter_individuals, self_instance_flag, CRITERIA,
)

RES = "resources"


def test_self_instance_flag_strips_generic_suffixes():
    # the suffix-dodge: "X Instance" instance_of "X"
    assert self_instance_flag("Peer Review Conduct Standard Instance", "Peer Review Conduct Standard")
    # type words on both sides collapse to the same concept
    assert self_instance_flag("Peer Review Cooperation Obligation Instance",
                              "Peer Review Cooperation Obligation Standard")
    # genuinely different concepts are not self-instances
    assert not self_instance_flag("NSPE Code of Ethics", "Professional Code")
    assert not self_instance_flag("Peer Review Notification", "Collegial Notification Before Reporting")


def test_resources_criteria_registered():
    assert RES in CRITERIA and CRITERIA[RES].instance_marker


def test_deterministic_clear_cases_need_no_llm():
    """A self-instance with no marker drops; a marked non-self-instance keeps; neither
    needs the LLM (resolver stays deterministic-only when nothing is ambiguous)."""
    inds = [
        {"label": "Peer Review Conduct Standard Instance", "resource_class": "Peer Review Conduct Standard"},
        {"label": "NSPE Code Section III.7.a", "resource_class": "NCEESModelRules"},  # marker: digit
    ]
    res = filter_individuals(inds, RES, use_llm=False)
    kept = {i["label"] for i in res["kept"]}
    assert kept == {"NSPE Code Section III.7.a"}
    assert res["dropped"][0][1] == "deterministic:self-instance"
    assert res["resolver"] == "deterministic-only"  # no ambiguous items
    assert res["llm_items"] == 0


def test_ambiguous_kept_without_llm():
    """Without the LLM, ambiguous items (no marker, not self-instance) are kept."""
    inds = [{"label": "NSPE Code of Ethics", "resource_class": "Professional Code"}]
    res = filter_individuals(inds, RES, use_llm=False)
    assert len(res["kept"]) == 1 and not res["dropped"]
    assert res["resolver"] == "deterministic"  # ambiguous present, no llm


class _Stream:
    def __init__(self, text): self._t = text
    def __enter__(self): return self
    def __exit__(self, *a): return False
    @property
    def text_stream(self): return [self._t]


class _Client:
    def __init__(self, text):
        self.messages = type("M", (), {"stream": lambda _s, **kw: _Stream(text)})()


def test_llm_judges_only_the_ambiguous_subset():
    """Deterministic settles the clear self-instance; only the two ambiguous items
    reach the LLM, which keeps the artifact and drops the masquerading type."""
    inds = [
        {"label": "Peer Review Conduct Standard Instance", "resource_class": "Peer Review Conduct Standard"},  # clear drop
        {"label": "NSPE Code of Ethics", "resource_class": "Professional Code"},                                # ambiguous -> keep
        {"label": "Peer Review Notification Standard Instance", "resource_class": "Collegial Notification Before Reporting Standard"},  # ambiguous -> drop
    ]
    # The two ambiguous items are passed to the LLM as indices 0 and 1 (in subset order).
    client = _Client('{"0": "keep", "1": "drop"}')
    res = filter_individuals(inds, RES, use_llm=True, client=client, model="x")
    assert res["llm_items"] == 2
    kept = {i["label"] for i in res["kept"]}
    assert kept == {"NSPE Code of Ethics"}
    reasons = {i["label"]: why for i, why in res["dropped"]}
    assert reasons["Peer Review Conduct Standard Instance"] == "deterministic:self-instance"
    assert reasons["Peer Review Notification Standard Instance"] == "llm:type-or-wrong-component"


def test_filter_is_component_agnostic_via_criteria():
    """The same mechanism applies to another component by supplying a FilterCriteria;
    no resource-specific code is involved."""
    crit = FilterCriteria(
        component="obligations",
        unit="a specific obligation borne by a named party in this case",
        keep_examples='"Engineer B duty to notify Engineer A"',
        drop_kinds="an abstract obligation TYPE or a relabeling of its own class",
        instance_marker=None,
    )
    inds = [{"label": "Faithful Agent Obligation", "instance_of": "Faithful Agent Obligation"}]
    res = filter_individuals(inds, crit, use_llm=False)
    assert len(res["dropped"]) == 1  # self-instance dropped deterministically
    assert res["dropped"][0][1] == "deterministic:self-instance"
