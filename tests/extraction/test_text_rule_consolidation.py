"""Phase A: text-pattern modules migrated onto the rules.py RuleSet (behavior-preserving).

Covers the two new RuleSet consumption modes (classify, collect) and asserts the migrated
field_classification + label_generality produce the same outputs as before the migration.
"""
from app.services.extraction.rules import Rule, RuleSet
from app.services.extraction.field_classification import classify, FieldKind, FIELD_RULES
from app.services.extraction.label_generality_judge import score_label, GENERALITY_RULES


# --- the generalized RuleSet methods -----------------------------------------------------

def test_ruleset_classify_returns_first_match_payload():
    rs = RuleSet("t", [
        Rule("a", "", lambda s: s.startswith("a"), payload="A"),
        Rule("b", "", lambda s: "b" in s, payload="B"),
    ])
    assert rs.classify("apple") == "A"          # first match wins
    assert rs.classify("nimble") == "B"
    assert rs.classify("xyz", default="DEF") == "DEF"


def test_ruleset_collect_returns_all_matches():
    rs = RuleSet("t", [
        Rule("len", "", lambda s: len(s) > 3, payload=1),
        Rule("vowel", "", lambda s: s[0] in "aeiou", payload=2),
    ])
    assert [r.name for r in rs.collect("apple")] == ["len", "vowel"]
    assert [r.name for r in rs.collect("by")] == []


# --- field_classification (classifying RuleSet) ------------------------------------------

def test_field_classification_precedence_and_default():
    expected = {
        "generatedAtTime": FieldKind.PROVENANCE,
        "sourceText": FieldKind.PROVENANCE,            # Text, but 'source' is not a relation
        "confidence": FieldKind.ASSESSMENT,
        "actionCount": FieldKind.DERIVED,
        "hasObligation": FieldKind.RELATION,
        "competesWith": FieldKind.RELATION,
        "fulfillsObligationText": FieldKind.CONTENT,   # demoted Text shadow of a relation
        "proeth:guidedByPrinciple": FieldKind.RELATION,  # prefix normalized off
        "option3": FieldKind.CONTENT,                  # trailing digit -> 'option' -> default
        "someNovelLiteral": FieldKind.CONTENT,
        "": FieldKind.CONTENT,
    }
    for pred, kind in expected.items():
        assert classify(pred) == kind, pred
    assert [r.name for r in FIELD_RULES.rules] == [
        "demoted_text", "provenance", "assessment", "derived", "relation"]


# --- label_generality_judge (scoring RuleSet) --------------------------------------------

def test_label_generality_scores_and_feedback():
    s, fb = score_label("ConfidentialityObligation")
    assert s == 1.0 and fb == []
    s, fb = score_label("EngineerASafetyObligation")       # actor marker -0.4
    assert abs(s - 0.6) < 1e-9 and len(fb) == 1 and "named actor" in fb[0]
    s, fb = score_label("PublicSafetyParamount")           # no head noun -0.25
    assert abs(s - 0.75) < 1e-9 and "component type" in fb[0]
    s, fb = score_label("BERCase845CostObligation")        # case number -0.4
    assert abs(s - 0.6) < 1e-9 and "case/precedent number" in fb[0]
    # variable penalty: 7 words -> -0.12*2 = -0.24
    s, fb = score_label("ConfidentialityObligationvs.ImminentPublicDangerObligation")
    assert abs(s - 0.76) < 1e-9 and "too long" in fb[0]


def test_label_generality_feedback_order_follows_rule_order():
    # a label tripping head-noun + actor should report head-noun before actor (declaration order)
    s, fb = score_label("EngineerAReviewing")  # no head noun + actor
    assert len(fb) == 2 and "component type" in fb[0] and "named actor" in fb[1]
