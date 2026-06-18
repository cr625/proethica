"""Tests for the shared precedent-case contamination filter.

The Step-1 role extractor and the Step-4 narrative pass both use this to drop
phantom actors pulled from cited precedent cases (e.g. the user-reported
"Defendant Attorney BER Case 19-3" in case 60).
"""
from app.services.extraction.precedent_filter import (
    is_precedent_reference,
    is_precedent_entity,
    is_contaminated_entity,
    drop_contaminated_entities,
    present_case_actor_letters,
    is_foreign_actor_entity,
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


def test_flags_generic_precedent_placeholder():
    # The whole label is just the precedent phrase with no present-case content.
    assert is_precedent_reference("Precedent")
    assert is_precedent_reference("BER Case Precedent")
    assert is_precedent_reference("Precedent Reference")


def test_flags_generic_placeholder_with_concept_head_noun():
    # The D4 label-generality reinforcement appends the concept type to every label, turning
    # the bare placeholder into "BER Case Precedent Resource" et al. (case-8 Section-C pilot,
    # 2026-06-18). The end-anchored placeholder pattern must tolerate the trailing head noun.
    for label in ("BER Case Precedent Resource", "BER Case Precedent State",
                  "Precedent Role", "BER Precedent Resources",
                  "BER Case Precedent Reference Resource"):
        assert is_precedent_reference(label), label
    # ...but a real present-case label that merely carries "Precedent" plus other content is
    # NOT a bare placeholder and must be kept ("Synthesis" is not a concept head noun).
    for label in ("Precedent Synthesis Resource", "Engineer L BER Precedent Synthesis"):
        assert not is_precedent_reference(label), label


def test_present_case_actor_letters():
    # present-case sections name the case's own engineers (case 8 = Engineer L)
    assert present_case_actor_letters("Engineer L was retained by Client X.") == frozenset({"L"})
    assert present_case_actor_letters(
        "Engineer A and Engineer B reviewed the design.") == frozenset({"A", "B"})
    # plural "Engineers A" form is captured; bare empty text -> empty set
    assert "A" in present_case_actor_letters("Engineers A submitted the report.")
    assert present_case_actor_letters("") == frozenset()
    assert present_case_actor_letters(None) == frozenset()


def test_is_foreign_actor_entity():
    present = frozenset({"L"})
    # foreign precedent actor (case 8 = Engineer L; Engineer A is recapped from a prior BER case)
    assert is_foreign_actor_entity("Engineer A Bird Species Omission", present)
    assert is_foreign_actor_entity("Engineer A Bird Species Written Report", present)  # norm too
    # present-case actor kept
    assert not is_foreign_actor_entity("Engineer L Faithful Agent", present)
    # abstract entity with no engineer letter is untouched
    assert not is_foreign_actor_entity("Public Safety Obligation", present)
    assert not is_foreign_actor_entity("Stormwater Design Engineer", present)
    # a label naming BOTH a present and a foreign letter is kept (it involves a present actor)
    assert not is_foreign_actor_entity("Engineer L and Engineer A Joint Review", present)
    # empty present set -> cannot judge -> keep
    assert not is_foreign_actor_entity("Engineer A Bird Species Omission", frozenset())
    # "Engineer Assistant" must not be read as engineer letter "A"
    assert not is_foreign_actor_entity("Engineer Assistant Role", present)


def test_drop_contaminated_entities_foreign_actor():
    class E:
        def __init__(self, label): self.label = label
    items = [E("Engineer L Faithful Agent"), E("Engineer A Bird Species Omission"),
             E("Public Safety Obligation"), E("Engineer A Construction Safety Abandoned")]
    kept, dropped = drop_contaminated_entities(
        items, lambda e: e.label, present_letters=frozenset({"L"}))
    assert {e.label for e in kept} == {"Engineer L Faithful Agent", "Public Safety Obligation"}
    assert set(dropped) == {"Engineer A Bird Species Omission",
                            "Engineer A Construction Safety Abandoned"}
    # empty present set disables the actor rule -> keeps everything (no markers present)
    kept2, dropped2 = drop_contaminated_entities(items, lambda e: e.label, present_letters=frozenset())
    assert len(kept2) == 4 and dropped2 == []


def test_is_contaminated_entity_composes_all_rules():
    present = frozenset({"L"})
    # marker rule (any concept type)
    assert is_contaminated_entity("Defendant Attorney BER Case 19-3", present_letters=present)
    # clean-label rule (fact concept, all quotes precedent)
    assert is_contaminated_entity("Public Works Director",
                                  quotes=["BER Case No. 00-5 centered on the bridge"],
                                  concept_type="roles", present_letters=present)
    # foreign-actor rule
    assert is_contaminated_entity("Engineer A Bird Species Omission", present_letters=present)
    # clean present-case entity is kept by every rule
    assert not is_contaminated_entity("Engineer L Faithful Agent",
                                      quotes=["Engineer L was retained"],
                                      concept_type="roles", present_letters=present)


def test_none_and_empty():
    assert not is_precedent_reference(None)
    assert not is_precedent_reference("")


def test_drop_partitions_and_reports():
    class C:
        def __init__(self, label): self.label = label
    items = [C("Engineer A"), C("BER Case 19-3 Defendant"), C("Attorney X"),
             C("Case 04-11 Engineer")]
    kept, dropped = drop_contaminated_entities(items, lambda c: c.label)
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
    kept, dropped = drop_contaminated_entities(
        items, lambda e: e.label,
        get_quotes=lambda e: e.text_references, concept_type="roles")
    assert [e.label for e in kept] == ["Engineer A"]
    assert dropped == ["Public Works Director"]
    # Same items as a NORM concept: the clean-label fact is kept (norm exemption).
    kept2, dropped2 = drop_contaminated_entities(
        items, lambda e: e.label,
        get_quotes=lambda e: e.text_references, concept_type="principles")
    assert [e.label for e in kept2] == ["Engineer A", "Public Works Director"]
    assert dropped2 == []
