"""Phase B: three more text-pattern checks migrated onto the rules.py abstraction
(behavior-preserving). Guards the refactor of:

  1. citation_provenance_apply.classify  -> CITATION_RULES classifying RuleSet
  2. text_patterns                        -> one home for the actor/case-number regexes
  3. individual_type_filter Tier-1        -> SELF_INSTANCE_RULE named Rule

Each test asserts the migrated code returns the SAME outputs as the pre-refactor
implementation on representative inputs (no behavior change).
"""
import re

from app.services.extraction.citation_provenance_apply import classify, CITATION_RULES
from app.services.extraction import text_patterns as tp
from app.services.extraction import precedent_filter as pf
from app.services.extraction import label_generality_judge as lg
from app.services.extraction.individual_type_filter import (
    self_instance_flag,
    SELF_INSTANCE_RULE,
    _SelfInstanceCtx,
    compute_flags,
)


# === Task 1: citation provenance classify (classifying RuleSet) ==========================

# Canonical norms used for the resolution check. `classify` returns None when normalize(raw)
# is in this set; otherwise it walks CITATION_RULES.
_CANON = {"iii.1.b", "ii.4.a"}

# (input, expected category) -- captured from the pre-refactor cascade. Covers every branch
# plus the two preserved quirks: a hyphen-only "92-1" never matches the BER number branch
# (low_sp strips the hyphen), and an uppercased "III.1.b" does not resolve against the
# lowercase canonical set so it falls to the modern-section branch.
_CITATION_CASES = [
    ("III.1.b", "modern_section_no_leaf"),
    ("I.2", "modern_section_no_leaf"),
    ("I.1", "modern_section_no_leaf"),
    ("BER Case 19-3", "ber_cross_case_precedent"),
    ("Case 04-11", "ber_cross_case_precedent"),
    ("92-1", "other_unmapped"),                       # hyphen-strip quirk: not a BER number here
    ("Brooks Act", "external_law_or_regulation"),
    ("EPA regulations", "external_law_or_regulation"),
    ("QBS process", "external_law_or_regulation"),
    ("Section 2", "nspe_pre_2007_numbered"),
    ("Canon 1", "nspe_pre_2007_numbered"),
    ("Rule 3", "nspe_pre_2007_numbered"),
    ("7(a)", "nspe_pre_2007_numbered"),
    ("section 4", "nspe_pre_2007_numbered"),
    ("Confidentiality Standard", "synthesized_standard_label"),
    ("Professional Conduct Directive", "synthesized_standard_label"),
    ("NSPE Code of Ethics", "generic_nspe_no_leaf"),
    ("something weird", "other_unmapped"),
]


def test_citation_classify_matches_pre_refactor_categories():
    for raw, expected in _CITATION_CASES:
        assert classify(raw, _CANON) == expected, raw


def test_citation_classify_returns_none_when_resolvable():
    # a citation that resolves to a modern leaf is not categorized
    assert classify("iii.1.b", _CANON) is None
    assert classify("ii.4.a", _CANON) is None


def test_citation_rules_precedence_order():
    # declaration order IS the precedence; default is other_unmapped (applied in classify)
    assert [r.name for r in CITATION_RULES.rules] == [
        "modern_section_no_leaf",
        "ber_cross_case_precedent",
        "external_law_or_regulation",
        "nspe_pre_2007_numbered",
        "synthesized_standard_label",
        "generic_nspe_no_leaf",
    ]


def test_citation_classify_empty_and_none_inputs():
    # empty / None never resolves and matches no branch -> default
    assert classify("", _CANON) == "other_unmapped"
    assert classify(None, _CANON) == "other_unmapped"


# === Task 2: text_patterns is the single home for the actor/case-number regexes ==========

def test_consuming_modules_import_the_shared_patterns():
    # precedent_filter and label_generality_judge use the SAME compiled objects from text_patterns
    assert pf.PRECEDENT_REF_RE is tp.PRECEDENT_REF_RE
    assert pf.GENERIC_PRECEDENT_RE is tp.GENERIC_PRECEDENT_RE
    assert pf._ENGINEER_LETTER_RE is tp._ENGINEER_LETTER_RE
    assert lg._ACTOR_RE is tp._ACTOR_RE
    assert lg._CASENUM_RE is tp._CASENUM_RE


def test_pattern_strings_are_byte_for_byte_unchanged():
    # the patterns are NOT merged or altered by the move
    assert tp.PRECEDENT_REF_RE.pattern == (
        r"\bBER\s+(?:Case\s+)?(?:No\.?\s+)?\d{2}-\d{1,2}\b"
        r"|\bCase\s+(?:No\.?\s+)?\d{2}-\d{1,2}\b"
        r"|\bDoe\b"
    )
    assert tp.PRECEDENT_REF_RE.flags & re.IGNORECASE
    assert tp.GENERIC_PRECEDENT_RE.pattern == (
        r"^\s*(?:BER\s+)?(?:Case\s+)?Precedent"
        r"(?:\s+(?:Reference|Case))?"
        r"(?:\s+(?:Resource|State|Role|Principle|Obligation|Constraint|Capability|Action|Event)s?)?"
        r"\s*$"
    )
    assert tp.GENERIC_PRECEDENT_RE.flags & re.IGNORECASE
    assert tp._ENGINEER_LETTER_RE.pattern == r"\bEngineers?\s+([A-Z])\b"
    assert tp._ACTOR_RE.pattern == (
        r"\b(Engineer|Client|Owner|Firm|Company|Contractor|Supplier)\s*[A-Z]\b|\bDoe\b"
    )
    assert tp._CASENUM_RE.pattern == r"\bBER\b|\bCase\b|\d{2,4}-\d{1,3}|\b\d{2}-\d\b"


def test_actor_and_casenum_patterns_remain_distinct():
    # The two filters' patterns are intentionally different: the generality judge's _ACTOR_RE
    # matches non-engineer actors (e.g. "Client B") that the precedent filter's _ENGINEER_LETTER_RE
    # does not. This is the reason they were NOT merged.
    assert tp._ACTOR_RE.search("Client B")
    assert not tp._ENGINEER_LETTER_RE.search("Client B")


# === Task 3: individual_type_filter Tier-1 self-instance rule ============================

_SELF_INSTANCE_CASES = [
    ("Peer Review Conduct Standard Instance", "Peer Review Conduct Standard", True),
    ("Public Safety Obligation", "Public Safety Obligation", True),       # equal after strip
    ("Bridge Inspection Report Instance", "Bridge Inspection Report", True),  # subset
    ("NSPE Code Section III.7.a", "Resource", False),                     # different concept
    ("Confidentiality Norm", "Privacy Principle", False),                 # disjoint
    ("", "Something", False),                                             # empty label
    ("Standard", "Standard", False),                                     # both strip to empty
]


def test_self_instance_rule_matches_underlying_predicate():
    for label, class_ref, expected in _SELF_INSTANCE_CASES:
        via_rule = SELF_INSTANCE_RULE.test(_SelfInstanceCtx(label, class_ref))
        assert via_rule is self_instance_flag(label, class_ref)
        assert via_rule is expected, (label, class_ref)


def test_compute_flags_uses_the_self_instance_rule():
    inds = [
        {"label": "Peer Review Conduct Standard Instance",
         "instance_of": "Peer Review Conduct Standard"},
        {"label": "BER Case 92-6", "resource_class": "Resource"},
    ]
    marker = r"(\b\d|\b(section|case|no|number|part|article|clause)\b)"
    flags = compute_flags(inds, marker)
    assert flags[0]["self_instance"] is True and flags[0]["marker"] is False
    assert flags[1]["self_instance"] is False and flags[1]["marker"] is True


def test_self_instance_rule_is_named_for_inspection():
    assert SELF_INSTANCE_RULE.name == "self_instance"
    assert SELF_INSTANCE_RULE.description
