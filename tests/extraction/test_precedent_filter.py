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


def test_flags_bare_ber_number_form():
    # "BER NN-N" without the literal "Case" keyword -- the form that slipped through
    # before the 2026-05-28 broadening (case-8 Stage-1 pilot, Finding 1).
    assert is_precedent_reference("Engineer A Environmental Impact Analyst BER 07-6")
    assert is_precedent_reference("Developer Client BER 07-6")
    assert is_precedent_reference("Cost-Refusing Client BER 84-5")
    assert is_precedent_reference("Engineer A Safety Staffing Case BER 84-5")
    assert is_precedent_reference("Engineer A BER 84-5 Cost-Driven Safety Rejection")


def test_flags_doe_placeholder_party():
    # "Engineer Doe" is exclusively a cited-precedent placeholder in NSPE opinions.
    assert is_precedent_reference("Engineer Doe Pollution Discharge Consultant")
    assert is_precedent_reference("Public Welfare Paramount Engineer Doe Pollution")
    assert is_precedent_reference("Engineer Doe Faithful Agent Limit Pollution Authority")


def test_keeps_present_case_actors():
    for label in ("Engineer A", "Attorney X", "Engineer B Forensic Expert",
                  "Public Welfare Paramount Obligation", "ENGCO Personnel",
                  # bare "BER" with no number must NOT be dropped: this is a legitimate
                  # present-case (Engineer L) capability about synthesizing precedents.
                  "Engineer L BER Precedent Synthesis",
                  # "Doe" must match as a whole word only, not inside other words.
                  "Engineer does review", "The doer of the action"):
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
