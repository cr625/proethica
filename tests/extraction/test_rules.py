"""Tests for the general text-pattern Rule / RuleSet abstraction."""
from dataclasses import dataclass

from app.services.extraction.rules import Rule, RuleSet, RuleHit


@dataclass(frozen=True)
class Ctx:
    label: str


def _rs():
    return RuleSet(name="t", rules=[
        Rule("has_ber", "label mentions BER", lambda c: "BER" in c.label),
        Rule("has_doe", "label mentions Doe", lambda c: "Doe" in c.label),
    ])


def test_evaluate_returns_first_matching_rule_name():
    rs = _rs()
    assert rs.evaluate(Ctx("BER Case 19-3")) == "has_ber"
    assert rs.evaluate(Ctx("Engineer Doe")) == "has_doe"
    # both match -> the first declared rule wins (order is the report tiebreak)
    assert rs.evaluate(Ctx("Doe in BER Case 1-1")) == "has_ber"
    assert rs.evaluate(Ctx("Engineer L")) is None


def test_matches():
    rs = _rs()
    assert rs.matches(Ctx("BER 1-1"))
    assert not rs.matches(Ctx("clean label"))


def test_partition_splits_and_reports_hits():
    rs = _rs()
    items = ["Engineer L", "BER Case 19-3", "Engineer Doe", "Attorney X"]
    kept, hits = rs.partition(items, to_context=lambda s: Ctx(s), get_label=lambda s: s)
    assert kept == ["Engineer L", "Attorney X"]
    assert hits == [RuleHit("has_ber", "BER Case 19-3"), RuleHit("has_doe", "Engineer Doe")]


def test_empty_ruleset_keeps_everything():
    rs = RuleSet(name="empty", rules=[])
    kept, hits = rs.partition(["a", "b"], to_context=lambda s: Ctx(s))
    assert kept == ["a", "b"] and hits == []
