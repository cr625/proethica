"""Tests for the shared precedent-case contamination filter.

The Step-1 role extractor and the Step-4 narrative pass both use this to drop
phantom actors pulled from cited precedent cases (e.g. the user-reported
"Defendant Attorney BER Case 19-3" in case 60).
"""
from app.services.extraction.precedent_filter import (
    is_precedent_reference,
    drop_precedent_entities,
)


def test_flags_precedent_actors():
    assert is_precedent_reference("Defendant Attorney BER Case 19-3")
    assert is_precedent_reference("BER Case 04-11 Situation 1 Engineer")
    assert is_precedent_reference("Case 20-1 PE Exam Disclosure")
    assert is_precedent_reference("BER Case 95-10 Title Use")


def test_keeps_present_case_actors():
    for label in ("Engineer A", "Attorney X", "Engineer B Forensic Expert",
                  "Public Welfare Paramount Obligation", "ENGCO Personnel"):
        assert not is_precedent_reference(label)


def test_none_and_empty():
    assert not is_precedent_reference(None)
    assert not is_precedent_reference("")


def test_drop_partitions_and_reports():
    class C:
        def __init__(self, label): self.label = label
    items = [C("Engineer A"), C("BER Case 19-3 Defendant"), C("Attorney X"),
             C("Case 04-11 Engineer")]
    kept, dropped = drop_precedent_entities(items, lambda c: c.label)
    assert [c.label for c in kept] == ["Engineer A", "Attorney X"]
    assert dropped == ["BER Case 19-3 Defendant", "Case 04-11 Engineer"]
