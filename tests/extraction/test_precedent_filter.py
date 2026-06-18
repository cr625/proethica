"""Tests for the shared precedent-case contamination filter.

The Step-1 role extractor and the Step-4 narrative pass both use this to drop
phantom actors pulled from cited precedent cases (e.g. the user-reported
"Defendant Attorney BER Case 19-3" in case 60).
"""
from app.services.extraction.precedent_filter import (
    is_precedent_reference,
    is_precedent_entity,
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


def test_flags_case_number_with_no_token():
    # "Case No. NN-N" / "BER Case No. NN-N" -- the form a clean-labeled phantom's quote
    # used ("BER Case No. 00-5 centered on ..."); added 2026-06-18 with the clean-label rule.
    assert is_precedent_reference("BER Case No. 00-5 centered on the reopening of a bridge")
    assert is_precedent_reference("Case No. 92-1")
    assert is_precedent_reference("BER No. 07-6")
    # the existing forms still match
    assert is_precedent_reference("BER Case 19-3")
    assert is_precedent_reference("Case 04-11")
    # a bare "No." with no NN-N must NOT match (e.g. a present-case "No. 3 Pump Station")
    assert not is_precedent_reference("No. 3 Pump Station Operator")


def test_clean_label_fact_dropped_when_all_quotes_precedent():
    # The motivating real case: a clean label whose sole supporting quote is precedent-only.
    assert is_precedent_entity(
        "Public Works Director",
        ["BER Case No. 00-5 centered on the reopening of a dangerous, closed bridge "
         "by a nonengineer public works director"],
        concept_type="roles")


def test_clean_label_fact_kept_with_one_present_case_quote():
    # A present-case entity that merely mentions a precedent in ONE quote is preserved,
    # because another quote attests it in the current case.
    assert not is_precedent_entity(
        "Engineer A",
        ["Unlike the engineer in BER Case 19-3, Engineer A disclosed the risk",
         "Engineer A and Engineer B presented the findings jointly"],
        concept_type="roles")


def test_clean_label_norm_kept_even_when_all_quotes_precedent():
    # Norm concepts are exempt from the clean-label rule: a cited precedent's principle /
    # obligation / constraint transfers to the present case.
    for ct in ("principles", "obligations", "constraints"):
        assert not is_precedent_entity(
            "Public Welfare Paramount",
            ["BER Case 19-3 held that public welfare is paramount"],
            concept_type=ct)


def test_marker_label_dropped_for_every_concept_type():
    # The label-marker rule applies to all types, including norms (a citation marker in the
    # label is a contamination artifact, not a transferable norm).
    assert is_precedent_entity("BER Case 19-3 Public Welfare", concept_type="principles")
    assert is_precedent_entity("Engineer Doe Obligation", concept_type="obligations")


def test_clean_label_no_quotes_is_label_only():
    # No quotes -> fall back to the label rule (no clean-label judgment, no over-drop).
    assert not is_precedent_entity("Engineer A", None, concept_type="roles")
    assert not is_precedent_entity("Engineer A", [], concept_type="roles")
    assert not is_precedent_entity("Engineer A", ["  "], concept_type="roles")


def test_drop_partitions_with_quotes_and_concept_type():
    class E:
        def __init__(self, label, quotes):
            self.label = label
            self.text_references = quotes
    items = [
        E("Engineer A", ["Engineer A disclosed the risk"]),                  # keep (clean)
        E("Public Works Director", ["BER Case No. 00-5 centered on a bridge"]),  # drop (fact)
    ]
    kept, dropped = drop_precedent_entities(
        items, lambda e: e.label,
        get_quotes=lambda e: e.text_references, concept_type="roles")
    assert [e.label for e in kept] == ["Engineer A"]
    assert dropped == ["Public Works Director"]
    # Same items as a NORM concept: the clean-label fact is kept (norm exemption).
    kept2, dropped2 = drop_precedent_entities(
        items, lambda e: e.label,
        get_quotes=lambda e: e.text_references, concept_type="principles")
    assert [e.label for e in kept2] == ["Engineer A", "Public Works Director"]
    assert dropped2 == []
